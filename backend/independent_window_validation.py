"""Independent GDAL/CSV reconstruction of every regional terrain query.

Only the comparison stage imports production calculations. Expected grids,
descriptors, calibration, and ranks are derived from separately decoded data.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from contextlib import ExitStack

import numpy as np
try:
    import rasterio
    from rasterio.io import MemoryFile
    from rasterio.transform import Affine
except ImportError:
    rasterio = None
    MemoryFile = None
    Affine = None

from independent_decoder import PRODUCTS, prepare_pds_files
from sources import DATA

RADII = {'earth': 6371008.8, 'moon': 1737400.0, 'mars': 3396000.0}
DESCRIPTORS = ('relief_m', 'median_slope_deg', 'detrended_rms_m')
CONFIGURATIONS = ((220000, 11), (220000, 7), (220000, 5), (180000, 9), (260000, 13))


def local_positions(latitude, longitude, radius, width, size):
    """Spherical exponential map in local east/north tangent coordinates."""
    spacing = width / size
    axis = (np.arange(size) - size // 2) * spacing
    grid_x, grid_y = np.meshgrid(axis, axis)
    lat0, lon0 = map(math.radians, (latitude, longitude))
    radial = np.array([math.cos(lat0) * math.cos(lon0),
                       math.cos(lat0) * math.sin(lon0), math.sin(lat0)])
    east = np.array([-math.sin(lon0), math.cos(lon0), 0])
    north = np.cross(radial, east)
    positions = []
    for dy in (-.4, -.2, 0, .2, .4):
        for dx in (-.4, -.2, 0, .2, .4):
            x, y = grid_x + dx * spacing, grid_y + dy * spacing
            angle = np.hypot(x, y) / radius
            sine_over_radius = np.sinc(angle / math.pi) / radius
            point = (np.cos(angle)[..., None] * radial +
                     sine_over_radius[..., None] * (x[..., None] * east + y[..., None] * north))
            lat = np.degrees(np.arctan2(point[..., 2], np.hypot(point[..., 0], point[..., 1])))
            lon = np.degrees(np.arctan2(point[..., 1], point[..., 0]))
            positions.append((lat, lon))
    return np.array([p[0] for p in positions]), np.array([p[1] for p in positions])


def interpolate_north_up(values, transform, latitudes, longitudes, *, periodic=False, nodata=None):
    """Bilinear interpolation of rasterio-decoded pixels in pixel-center space."""
    z = np.asarray(values, dtype=np.float64)
    lon = np.mod(longitudes, 360) if periodic else np.asarray(longitudes)
    col_corner, row_corner = ~transform @ (lon, latitudes)
    col = np.asarray(col_corner) - .5
    row = np.asarray(row_corner) - .5
    if periodic:
        col %= z.shape[1]
    # Floating-point edge noise must not be mistaken for missing coverage.
    edge_tolerance = 16 * np.finfo(float).eps * max(z.shape)
    if np.any(row < -edge_tolerance) or np.any(row > z.shape[0]-1+edge_tolerance) or (
        not periodic and (np.any(col < -edge_tolerance) or np.any(col > z.shape[1]-1+edge_tolerance))
    ):
        raise ValueError('Sample outside independently decoded source coverage.')
    row = np.clip(row, 0, z.shape[0]-1)
    if not periodic:
        col = np.clip(col, 0, z.shape[1]-1)
    i = np.minimum(np.floor(row).astype(int), z.shape[0]-2)
    j = np.floor(col).astype(int)
    if not periodic:
        j = np.minimum(j, z.shape[1]-2)
    k = (j + 1) % z.shape[1]
    fy, fx = row-i, col-j
    v00, v01, v10, v11 = z[i, j], z[i, k], z[i+1, j], z[i+1, k]
    if nodata is not None and np.any((v00 == nodata) | (v01 == nodata) | (v10 == nodata) | (v11 == nodata)):
        raise ValueError('A bilinear source neighborhood contains NoData.')
    if not np.isfinite(np.stack((v00, v01, v10, v11))).all():
        raise ValueError('A bilinear source neighborhood contains missing values.')
    return v00 + fx * (v01-v00) + fy * (v10-v00) + fx * fy * (v11-v10-v01+v00)


def percentile_linear(values, percent):
    ordered = np.sort(np.asarray(values, dtype=float).ravel())
    index = (len(ordered)-1) * percent / 100
    lower = int(math.floor(index))
    return float(ordered[lower] + (index-lower) * (ordered[int(math.ceil(index))]-ordered[lower]))


def descriptors(grid, spacing):
    z = np.asarray(grid, dtype=float)
    if z.ndim != 2 or z.shape[0] != z.shape[1] or z.shape[0] < 5 or spacing <= 0 or not np.isfinite(z).all():
        raise ValueError('Descriptors require a complete finite square grid.')
    gx = (z[1:-1, 2:] - z[1:-1, :-2]) / (2*spacing)
    gy = (z[2:, 1:-1] - z[:-2, 1:-1]) / (2*spacing)
    slope = np.degrees(np.arctan(np.sqrt(gx*gx + gy*gy)))
    axis = np.arange(z.shape[0], dtype=float) - (z.shape[0]-1)/2
    xx, yy = np.meshgrid(axis, axis)
    intercept = float(np.mean(z))
    bx = float(np.sum(xx*z) / np.sum(xx*xx))
    by = float(np.sum(yy*z) / np.sum(yy*yy))
    residual = z - intercept - bx*xx - by*yy
    return {'relief_m': percentile_linear(z, 95) - percentile_linear(z, 5),
            'median_slope_deg': float(np.median(slope)),
            'detrended_rms_m': float(np.sqrt(np.mean(residual*residual)))}


def open_earth(candidate, source_hash, stack):
    """Read original NOAA CSV by provenance hash and georeference its nodes."""
    matches = []
    for manifest in DATA.glob('*.meta.json'):
        info = json.loads(manifest.read_text(encoding='utf-8'))
        if info.get('sha256') == source_hash and 'etopo180.csv' in info.get('url', ''):
            matches.append((manifest, info))
    if len(matches) != 1:
        raise ValueError(f'Expected exactly one NOAA source manifest for {candidate}.')
    manifest, info = matches[0]
    # The manifest filename is HASH.meta.json, not HASH.csv.
    raw = manifest.with_name(manifest.name[:-10] + '.csv')
    if hashlib.sha256(raw.read_bytes()).hexdigest() != source_hash:
        raise ValueError('NOAA CSV checksum mismatch.')
    with raw.open(newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ['latitude', 'longitude', 'altitude']:
            raise ValueError('Unexpected NOAA CSV fields.')
        units = next(reader)
        if list(units.values()) != ['degrees_north', 'degrees_east', 'm']:
            raise ValueError('Unexpected NOAA CSV coordinate/elevation units.')
        triples = [(float(row['latitude']), float(row['longitude']), float(row['altitude'])) for row in reader]
    lats = np.unique([p[0] for p in triples]); lons = np.unique([p[1] for p in triples])
    if len(triples) != len(lats)*len(lons) or len(lats)<2 or len(lons)<2:
        raise ValueError('NOAA CSV has incomplete node coverage.')
    lat_step = float(np.median(np.diff(lats))); lon_step = float(np.median(np.diff(lons)))
    if not (np.allclose(np.diff(lats), lat_step, rtol=0, atol=1e-8) and
            np.allclose(np.diff(lons), lon_step, rtol=0, atol=1e-8) and
            math.isclose(lat_step, 1/60, abs_tol=1e-8) and math.isclose(lon_step, 1/60, abs_tol=1e-8)):
        raise ValueError('Unexpected NOAA ETOPO1 node spacing.')
    grid = np.full((len(lats), len(lons)), np.nan)
    for lat, lon, height in triples:
        i = int(round((lats[-1]-lat)/lat_step)); j = int(round((lon-lons[0])/lon_step))
        if not np.isnan(grid[i, j]):
            raise ValueError('Duplicate NOAA grid node.')
        grid[i, j] = height
    if not np.isfinite(grid).all():
        raise ValueError('NOAA grid includes invalid values.')
    transform = Affine.translation(lons[0]-lon_step/2, lats[-1]+lat_step/2) @ Affine.scale(lon_step, -lat_step)
    memory = stack.enter_context(MemoryFile())
    with memory.open(driver='GTiff', width=len(lons), height=len(lats), count=1, dtype='float64',
                     crs='EPSG:4326', transform=transform) as dataset:
        dataset.write(grid, 1)
    dataset = stack.enter_context(memory.open())
    if dataset.width != len(lons) or dataset.height != len(lats) or dataset.crs.to_epsg() != 4326:
        raise ValueError('Independent NOAA georeferencing failed.')
    decoded = dataset.read(1)
    if not np.array_equal(decoded,grid):
        raise AssertionError('Rasterio did not preserve every NOAA CSV elevation node.')
    # The production reader derives its axis step from the first two CSV nodes;
    # a GeoTIFF affine uses the median step. Decimal CSV rounding makes these
    # definitions differ slightly across a large subset.
    lat_axis_error = np.max(np.abs((lats[0]+np.arange(len(lats))*(lats[1]-lats[0])) -
                                   (lats[0]+np.arange(len(lats))*lat_step)))
    lon_axis_error = np.max(np.abs((lons[0]+np.arange(len(lons))*(lons[1]-lons[0])) -
                                   (lons[0]+np.arange(len(lons))*lon_step)))
    horizontal_contrast = float(np.max(np.abs(np.diff(grid,axis=1))))
    vertical_contrast = float(np.max(np.abs(np.diff(grid,axis=0))))
    return decoded, dataset.transform, None, {'sha256':source_hash, 'shape':[len(lats),len(lons)],
        'node_spacing_degrees':[lat_step,lon_step], 'node_bounds':[float(lats[0]),float(lats[-1]),float(lons[0]),float(lons[-1])],
        'node_registration':'CSV latitude/longitude values are raster pixel centers', 'units':'m',
        'first_two_node_spacing_degrees':[float(lats[1]-lats[0]),float(lons[1]-lons[0])],
        'maximum_axis_drift_degrees':[float(lat_axis_error),float(lon_axis_error)],
        'maximum_adjacent_pixel_contrast_m':[vertical_contrast,horizontal_contrast]}


def compare_samples(expected, actual, lat_expected, lon_expected, lat_actual, lon_actual):
    delta = expected - actual
    flat = np.argsort(np.abs(delta).ravel())[-3:][::-1]
    examples = []
    for index in flat:
        subcell, row, col = np.unravel_index(int(index), delta.shape)
        examples.append({'subcell':int(subcell),'row':int(row),'column':int(col),
                         'latitude':float(lat_expected[subcell,row,col]),
                         'longitude':float(lon_expected[subcell,row,col]),
                         'independent_m':float(expected[subcell,row,col]),
                         'production_m':float(actual[subcell,row,col]),
                         'difference_m':float(delta[subcell,row,col])})
    longitude_delta = (lon_expected-lon_actual+180)%360-180
    return {'expected_queries':int(expected.size), 'valid_queries':int(np.isfinite(expected).sum()),
            'maximum_absolute_difference_m':float(np.max(np.abs(delta))),
            'mean_absolute_difference_m':float(np.mean(np.abs(delta))),
            'root_mean_squared_difference_m':float(np.sqrt(np.mean(delta*delta))),
            'maximum_latitude_disagreement_degrees':float(np.max(np.abs(lat_expected-lat_actual))),
            'maximum_longitude_disagreement_degrees':float(np.max(np.abs(longitude_delta))),
            'largest_differences':examples}


def grid_support(grid, latitudes, longitudes, spacing):
    """Locate cells supporting numerical extrema; these are not causal attributions."""
    size=grid.shape[0]
    center_lat=latitudes[12];center_lon=longitudes[12]
    gx=(grid[1:-1,2:]-grid[1:-1,:-2])/(2*spacing)
    gy=(grid[2:,1:-1]-grid[:-2,1:-1])/(2*spacing)
    slopes=np.degrees(np.arctan(np.hypot(gx,gy)))
    axis=np.arange(size)-(size-1)/2
    xx,yy=np.meshgrid(axis,axis)
    residual=grid-grid.mean()-(xx*grid).sum()/(xx*xx).sum()*xx-(yy*grid).sum()/(yy*yy).sum()*yy
    def detail(row,col,value):
        return {'row':int(row),'column':int(col),'latitude':float(center_lat[row,col]),
                'longitude':float(center_lon[row,col]),'value':float(value)}
    profiles={}
    for label,quantile in (('p5',5),('p95',95)):
        target=percentile_linear(grid,quantile)
        row,col=np.unravel_index(int(np.argmin(np.abs(grid-target))),grid.shape)
        profiles[label]={'percentile_value_m':target,'nearest_cell':detail(row,col,grid[row,col])}
    row,col=np.unravel_index(int(np.argmax(slopes)),slopes.shape)
    profiles['steepest_interior_cell']=detail(row+1,col+1,slopes[row,col])
    row,col=np.unravel_index(int(np.argmax(np.abs(residual))),residual.shape)
    profiles['largest_plane_residual_cell']=detail(row,col,residual[row,col])
    return profiles


def run_validation():
    """Cross-check every input window and all five configurations."""
    if rasterio is None:
        raise RuntimeError('Optional Rasterio is required for independent window validation.')
    # Catalog identifiers and centers are configuration, not expected science.
    from science import CANDIDATES, TARGETS, coordinates, features, window
    from spatial_scale_experiment import sample_window, terrain_descriptors
    from sources import earth_raster, planetary_raster
    from terrain_knn import TerrainKNN

    previous = json.loads((DATA/'spatial-scale-report.json').read_text(encoding='utf-8'))
    result = {'version':'independent-window-v1','decoder':f'Rasterio {rasterio.__version__} / GDAL {rasterio.__gdal_version__}',
              'sources':previous['sources'],'earth_metadata':{},'planetary_metadata':{},'configurations':{},
              'comparisons':{},'rankings':{}}
    with ExitStack() as stack:
        rasters = {}
        for body in ('moon','mars'):
            product = PRODUCTS[body]
            stack.enter_context(rasterio.Env(**product['gdal_options']))
            dataset = stack.enter_context(rasterio.open(prepare_pds_files(product)))
            data = dataset.read(1).astype(float)*product['height_scale']
            # Use angular pixel-center registration stated by the PDS label;
            # also retain the GDAL affine map to quantify its rounded MAP_SCALE.
            angular = Affine.translation(0, 90) @ Affine.scale(.25,-.25)
            scaled_nodata = dataset.nodata*product['height_scale'] if dataset.nodata is not None else None
            rasters[body] = (data, angular, scaled_nodata, True)
            result['planetary_metadata'][body] = {'driver':dataset.driver,'shape':list(data.shape),
                'gdal_affine':tuple(dataset.transform)[:6], 'label_angular_affine':tuple(angular)[:6],
                'raw_scale':dataset.scales[0], 'raw_offset':dataset.offsets[0],
                'nodata':dataset.nodata, 'image_sha256':previous['sources'][body]}
        for candidate in CANDIDATES:
            earth_data = open_earth(candidate['id'],previous['sources']['earth'][candidate['id']],stack)
            rasters[candidate['id']] = (*earth_data[:3], False)
            result['earth_metadata'][candidate['id']] = earth_data[3]
        production = {'moon':planetary_raster('moon'), 'mars':planetary_raster('mars')}
        production.update({c['id']:earth_raster(c['latitude'],c['longitude']) for c in CANDIDATES})
        for width,size in CONFIGURATIONS:
            name = next(c['id'] for c in previous['configurations'] if c['width_m']==width and c['grid_size']==size)
            spacing = width/size
            result['configurations'][name]={'width_m':width,'grid_size':size,'spacing_m':spacing}
            windows = {}
            for target in list(TARGETS.values())+CANDIDATES:
                identifier=target['id']; body=target.get('body','earth')
                source_id=body if body!='earth' else identifier
                data,transform,nodata,periodic=rasters[source_id]
                lat,lon=local_positions(target['latitude'],target['longitude'],RADII[body],width,size)
                expected=interpolate_north_up(data,transform,lat,lon,periodic=periodic,nodata=nodata)
                if not np.isfinite(expected).all():
                    raise ValueError(f'Invalid independent samples: {name}/{identifier}')
                axis=(np.arange(size)-size//2)*spacing
                x,y=np.meshgrid(axis,axis)
                prod_lat=[];prod_lon=[];actual=[]
                for dy in (-.4,-.2,0,.2,.4):
                    for dx in (-.4,-.2,0,.2,.4):
                        a,b=coordinates(target['latitude'],target['longitude'],x+dx*spacing,y+dy*spacing,RADII[body])
                        prod_lat.append(a);prod_lon.append(b)
                        actual.append(production[source_id].sample(a,b))
                actual=np.asarray(actual)
                prod_lat=np.asarray(prod_lat);prod_lon=np.asarray(prod_lon)
                sample_check=compare_samples(expected,actual,lat,lon,prod_lat,prod_lon)
                # Bound the value difference using the actual disagreement in
                # fractional pixel positions and source-neighbor contrasts.
                if body=='earth':
                    metadata=result['earth_metadata'][identifier]
                    lat_min,lat_max,lon_min,_=metadata['node_bounds']
                    original_dlat,original_dlon=metadata['first_two_node_spacing_degrees']
                    producer_row=(data.shape[0]-1)-(prod_lat-lat_min)/original_dlat
                    producer_col=(prod_lon-lon_min)/original_dlon
                else:
                    producer_row=(89.875-prod_lat)/.25
                    producer_col=((prod_lon%360)-.125)/.25 % data.shape[1]
                independent_col_corner,independent_row_corner=~transform @ (lon%360 if periodic else lon,lat)
                independent_row=np.asarray(independent_row_corner)-.5
                independent_col=np.asarray(independent_col_corner)-.5
                row_error=float(np.max(np.abs(producer_row-independent_row)))
                col_difference=np.abs(producer_col-independent_col)
                col_error=float(np.max(np.minimum(col_difference,data.shape[1]-col_difference) if periodic else col_difference))
                contrast_row=float(np.max(np.abs(np.diff(data,axis=0))))
                contrast_col=float(np.max(np.abs(np.diff(data,axis=1))))
                # The additive term bounds accumulated binary64 arithmetic;
                # it is not a scientific measurement-error or analog threshold.
                envelope=(row_error*contrast_row+col_error*contrast_col+
                          128*np.finfo(float).eps*float(np.max(np.abs(data))))
                sample_check['maximum_fractional_pixel_disagreement']={'row':row_error,'column':col_error}
                sample_check['source_adjacent_pixel_contrast_m']={'row':contrast_row,'column':contrast_col}
                sample_check['derived_numerical_envelope_m']=envelope
                sample_check['within_derived_numerical_envelope']=bool(sample_check['maximum_absolute_difference_m']<=envelope)
                independent_grid=np.mean(expected,axis=0)
                production_grid=window(production[source_id],target,body) if size==11 and width==220000 else sample_window(production[source_id],target,body,width,size)
                if not np.allclose(production_grid,np.mean(actual,axis=0),rtol=0,atol=1e-8):
                    raise AssertionError('Production grid is inconsistent with its 25 queries.')
                independent_features=descriptors(independent_grid,spacing)
                production_features=features(production_grid) if size==11 and width==220000 else terrain_descriptors(production_grid,spacing)
                descriptor_check={key:{'production':float(production_features[key]),
                    'independent':independent_features[key],
                    'absolute_difference':abs(independent_features[key]-production_features[key]),
                    'relative_difference':(abs(independent_features[key]-production_features[key])/abs(production_features[key])
                                           if abs(production_features[key])>1e-12 else None)} for key in DESCRIPTORS}
                windows[identifier]={'features':independent_features,'grid':independent_grid}
                result['comparisons'][name+'/'+identifier]={'body':body,'sample_comparison':sample_check,
                    'grid_maximum_absolute_difference_m':float(np.max(np.abs(independent_grid-production_grid))),
                    'descriptors':descriptor_check,
                    'supporting_grid_cells':grid_support(independent_grid,lat,lon,spacing)}
            for target_id in TARGETS:
                reference=windows[target_id]['features']
                earth={c['id']:windows[c['id']]['features'] for c in CANDIDATES}
                scale={key:percentile_linear([row[key] for row in earth.values()],75)-
                           percentile_linear([row[key] for row in earth.values()],25) for key in DESCRIPTORS}
                if any(v<=0 for v in scale.values()):
                    raise ValueError('Independent Earth calibration has zero dispersion.')
                ranked=sorted(((candidate,math.sqrt(sum(((earth[candidate][key]-reference[key])/scale[key])**2
                    for key in DESCRIPTORS)/len(DESCRIPTORS))) for candidate in earth), key=lambda pair:(pair[1],pair[0]))
                previous_scenario=next(s for s in previous['targets'][target_id] if s['name']==name)
                prod_ranking=previous_scenario['ranking']
                discrepancies={entry['id']:float(dict(ranked)[entry['id']]-entry['distance']) for entry in prod_ranking}
                independent_outside=[key for key in DESCRIPTORS if not min(row[key] for row in earth.values())<=reference[key]<=max(row[key] for row in earth.values())]
                comparison={'winner':ranked[0][0],'ranking':[{'id':k,'distance':v} for k,v in ranked],
                    'earth_iqr':scale,'production_winner':previous_scenario['winner'],
                    'production_ranking':[r['id'] for r in prod_ranking],
                    'distance_differences_metrical':discrepancies,
                    'independent_outside_features':independent_outside,
                    'production_outside_features':previous_scenario['range_diagnostics']['outside_features']}
                # Hold the original Earth IQR fixed to isolate descriptor effects.
                original_iqr=previous['targets'][target_id][0]['earth_iqr']
                fixed=sorted(((candidate,math.sqrt(sum(((earth[candidate][key]-reference[key])/original_iqr[key])**2
                    for key in DESCRIPTORS)/len(DESCRIPTORS))) for candidate in earth),key=lambda pair:(pair[1],pair[0]))
                comparison['fixed_baseline_iqr_winner']=fixed[0][0]
                comparison['fixed_baseline_iqr_ranking']=[k for k,_ in fixed]
                comparison['first_second_distance_gap']=ranked[1][1]-ranked[0][1]
                result['rankings'][name+'/'+target_id]=comparison
    output=DATA/'independent-window-report.json'
    output.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    return result


if __name__=='__main__':
    report=run_validation()
    for config in report['configurations']:
        checks=[v for key,v in report['comparisons'].items() if key.startswith(config+'/')]
        print(config,len(checks),max(v['sample_comparison']['maximum_absolute_difference_m'] for v in checks))
        for target in ('moon-tranquillitatis','moon-tycho','mars-jezero','mars-gale'):
            rank=report['rankings'][config+'/'+target]
            print(' ',target,rank['winner'],rank['production_winner'])
