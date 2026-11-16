"""Reproducible regional terrain screening; no learned or calibrated analog score."""
from __future__ import annotations
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from sources import DATA, earth_raster, planetary_raster, earth_climate
from terrain_knn import TerrainKNN
from ranking_sensitivity import descriptor_and_catalog_scenarios, summarize_ranking
from terrain_quality import assess_quality, earth_quality

METHOD_VERSION = 'regional-topography-knn-v3'
SPACING_M = 20000.0
RADIUS = {'earth':6371008.8, 'moon':1737400.0, 'mars':3396000.0}
TARGETS = {
    'moon-tranquillitatis': {'id':'moon-tranquillitatis','name':'Mare Tranquillitatis regional window','body':'moon','latitude':0.674,'longitude':23.473},
    'moon-tycho': {'id':'moon-tycho','name':'Tycho regional window','body':'moon','latitude':-43.31,'longitude':-11.36},
    'mars-jezero': {'id':'mars-jezero','name':'Jezero regional window','body':'mars','latitude':18.38,'longitude':77.58},
    'mars-gale': {'id':'mars-gale','name':'Gale regional window','body':'mars','latitude':-5.4,'longitude':137.8},
}
CANDIDATES = [
    {'id':'atacama','name':'Atacama Desert, Chile','latitude':-24.5,'longitude':-69.0},
    {'id':'death-valley','name':'Death Valley region, United States','latitude':36.25,'longitude':-116.8},
    {'id':'colorado-plateau','name':'Colorado Plateau, United States','latitude':38.0,'longitude':-110.0},
    {'id':'pilbara','name':'Pilbara, Australia','latitude':-22.5,'longitude':119.0},
    {'id':'sahara','name':'Central Sahara, Algeria','latitude':24.5,'longitude':10.0},
    {'id':'ladakh','name':'Ladakh region, India','latitude':34.0,'longitude':78.0},
    {'id':'tibetan-plateau','name':'Tibetan Plateau, China','latitude':32.0,'longitude':85.0},
]
FEATURES = {'relief_m':'P95–P5 elevation range (m)', 'median_slope_deg':'Median regional slope (degrees)',
            'detrended_rms_m':'RMS elevation after plane removal (m)'}
LIMITATIONS = [
    'Exploratory topographic ranking within seven preselected terrestrial windows; not a global discovery or validated analog classification.',
    'All rasters are bilinearly sampled and averaged over 20 km cells on a spherical local grid; fine craters and rover-scale terrain are unresolved.',
    'Distances use three correlated relief descriptors with equal contribution. This transparent baseline is not scientifically calibrated.',
    'Elevation datums differ. Absolute mean elevation is displayed for context and excluded from the distance.',
    'No inference about geology, mineralogy, atmospheric equivalence, habitability or mission safety is supported.',
    'Raster interpolation and differing native resolution introduce uncertainty; no formal confidence interval is estimated.',
]


def coordinates(lat, lon, x, y, radius):
    """Spherical azimuthal-equidistant inverse mapping (not a planar lat/lon grid)."""
    distance = np.hypot(x, y) / radius
    bearing = np.arctan2(x, y)
    lat0, lon0 = np.radians(lat), np.radians(lon)
    phi = np.arcsin(np.sin(lat0)*np.cos(distance) + np.cos(lat0)*np.sin(distance)*np.cos(bearing))
    lam = lon0 + np.arctan2(np.sin(bearing)*np.sin(distance)*np.cos(lat0), np.cos(distance)-np.sin(lat0)*np.sin(phi))
    return np.degrees(phi), (np.degrees(lam)+180)%360-180


def window(raster, location, body, spacing=SPACING_M, include_coordinates=False):
    axis = np.arange(-5, 6) * spacing
    x, y = np.meshgrid(axis, axis)
    patches = []
    positions = []
    # 25 equally weighted subcell samples approximate the common cell area mean.
    for dy in np.array((-8000, -4000, 0, 4000, 8000)) * spacing / SPACING_M:
        for dx in np.array((-8000, -4000, 0, 4000, 8000)) * spacing / SPACING_M:
            lat, lon = coordinates(location['latitude'], location['longitude'], x+dx, y+dy, RADIUS[body])
            patches.append(raster.sample(lat, lon))
            if include_coordinates:
                positions.append((lat, lon))
    z = np.mean(patches, axis=0)
    if include_coordinates:
        return z, (np.stack([lat for lat, _ in positions]),
                   np.stack([lon for _, lon in positions]))
    return z


def features(z, spacing=SPACING_M):
    z = np.asarray(z, dtype=float)
    if z.shape != (11, 11) or not np.isfinite(z).all():
        raise ValueError('A complete finite 11x11 regional elevation grid is required.')
    gy, gx = np.gradient(z, spacing)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    y, x = np.indices(z.shape)
    design = np.column_stack((np.ones(z.size), x.ravel(), y.ravel()))
    fit = design @ np.linalg.lstsq(design, z.ravel(), rcond=None)[0]
    return {'relief_m':float(np.percentile(z,95)-np.percentile(z,5)),
            'median_slope_deg':float(np.median(slope[1:-1,1:-1])),
            'detrended_rms_m':float(np.sqrt(np.mean((z.ravel()-fit)**2))),
            'mean_elevation_m':float(z.mean()), 'valid_cells':int(z.size)}


def compare(a, b):
    components = {}
    for k in FEATURES:
        denominator = abs(a[k]) + abs(b[k])
        components[k] = abs(a[k]-b[k])/denominator if denominator > 1e-9 else 0.0
    return float(np.mean(list(components.values()))), components


def spatial_sensitivity(target, planet, earth_rasters, candidates, baseline, reference):
    """Perturb all centers together, or the common window width, with unchanged raw rasters."""
    scenarios = []
    directions = (('east_20km', 20000, 0), ('west_20km', -20000, 0),
                  ('north_20km', 0, 20000), ('south_20km', 0, -20000))
    variants = [(f'center:{scope}:{direction}', dx, dy, SPACING_M, scope)
                for scope in ('joint', 'reference_only', 'earth_only') for direction, dx, dy in directions]
    variants += [('window:198km', 0, 0, 18000.0, 'joint'), ('window:242km', 0, 0, 22000.0, 'joint')]
    for name, dx, dy, spacing, scope in variants:
        shifted = {'joint':'all Earth and reference centers', 'reference_only':'only the planetary reference center',
                   'earth_only':'only the Earth centers'}[scope]
        assumption = (f'Shift {shifted} by 20 km {name.split(":")[-1].split("_")[0]}; '
                      'retain 220 km windows and refit Earth IQR.' if dx or dy else
                      f'Use 11 cells at {spacing/1000:g} km spacing, a {11*spacing/1000:g} km window, and refit Earth IQR.')
        try:
            def moved(location, body):
                if not (dx or dy):
                    return location
                lat, lon = coordinates(location['latitude'], location['longitude'], dx, dy, RADIUS[body])
                return {**location, 'latitude':float(lat), 'longitude':float(lon)}
            reference_center = moved(target, target['body']) if scope != 'earth_only' else target
            query = features(window(planet, reference_center, target['body'], spacing), spacing)
            terrestrial = [{**c, 'features':features(window(earth_rasters[c['id']], moved(c, 'earth') if scope != 'reference_only' else c, 'earth', spacing), spacing)}
                           for c in candidates]
            variant_model = TerrainKNN(FEATURES).fit(terrestrial)
            scenario = summarize_ranking(name, assumption, variant_model.query(query), baseline)
            scenario.update(status='available', earth_iqr=dict(zip(FEATURES, variant_model.scale.tolist())),
                            center_shift_m={'east':dx, 'north':dy, 'scope':scope}, window_width_m=11*spacing,
                            reference_features={key:query[key] for key in FEATURES})
        except (ValueError, RuntimeError) as exc:
            scenario = {'name':name, 'status':'unavailable', 'assumption_changed':assumption,
                        'reason':str(exc)}
        scenarios.append(scenario)
    return scenarios


def analyze(target_id):
    target = TARGETS[target_id]
    planet = planetary_raster(target['body'])
    reference_grid, sampling_coordinates = window(planet, target, target['body'], include_coordinates=True)
    reference = {**target, 'features':features(reference_grid), 'grid_m':reference_grid.tolist(), 'source':planet.provenance}
    candidates, failures, earth_rasters = [], [], {}
    def process(c):
        raster = earth_raster(c['latitude'], c['longitude'])
        grid = window(raster, c, 'earth')
        stats = features(grid)
        return {**c, 'features':stats,
                'grid_m':grid.tolist(), 'source':raster.provenance}, raster
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(process,c):c for c in CANDIDATES}
        for future in as_completed(futures):
            try:
                candidate, raster = future.result()
                candidates.append(candidate)
                earth_rasters[candidate['id']] = raster
            except Exception as exc:
                failures.append({'id':futures[future]['id'], 'error':str(exc)})
    if len(candidates) < 2:
        raise RuntimeError('Insufficient valid Earth windows for ranking: ' + json.dumps(failures))
    model = TerrainKNN(FEATURES).fit(candidates)
    distances = dict(model.query(reference['features']))
    explanations = model.explain(reference['features'])
    range_diagnostics = model.range_diagnostics(reference['features'])
    for c in candidates:
        c['distance'] = distances[c['id']]
        c['distance_explanation'] = explanations[c['id']]
    candidates.sort(key=lambda c:(c['distance'], c['id']))
    for rank, c in enumerate(candidates,1):
        c['rank'] = rank
    # Leave-one-descriptor-out searches reveal dependence on feature selection.
    sensitivity = {}
    for omitted in FEATURES:
        sensitivity[omitted] = model.query(reference['features'], omitted=omitted)[0][0]
    baseline = model.query(reference['features'])
    sensitivity_analysis = descriptor_and_catalog_scenarios(model, candidates, reference['features'])
    sensitivity_analysis['scenarios'].extend(spatial_sensitivity(target, planet, earth_rasters, candidates, baseline, reference))
    data_quality = {'reference':assess_quality(target, planet, reference_grid, sampling_coordinates),
                    'earth':earth_quality(candidates)}
    coverage = data_quality['reference'].get('observation_coverage')
    sensitivity_analysis['quality_scenarios'] = ({
        'status':'no_effect',
        'assumption_changed':'Exclude bilinear source bins with no recorded MOLA shots.',
        'reason':'Every source bin touched by this reference has at least one recorded shot; the filtered grid is identical to the baseline. Shot counts do not calibrate elevation uncertainty.',
        'winner':baseline[0][0],
        'ranking':[{'rank':rank, 'id':identifier, 'distance':distance}
                   for rank, (identifier, distance) in enumerate(baseline, 1)],
        'distance_change_from_baseline':{identifier:0.0 for identifier, _ in baseline}}
        if coverage and coverage['bins_with_no_shots'] == 0 else {
        'status':'unavailable',
        'reason':'No defensible common per-cell quality filter is established for the current inputs; a LOLA strip warning alone is not a mask, and MOLA counts may be missing or include zero-shot source bins.'})
    try:
        climate = earth_climate(candidates[0]['latitude'], candidates[0]['longitude'])
    except Exception as exc:
        climate = {'status':'unavailable','error':str(exc)}
    implementation = hashlib.sha256(b''.join(Path(__file__).with_name(name).read_bytes() for name in
                                ('science.py','sources.py','terrain_knn.py','ranking_sensitivity.py','terrain_quality.py'))).hexdigest()
    fingerprint = {'method':METHOD_VERSION,'implementation_sha256':implementation,
                   'target':target,'reference':planet.provenance['sha256'],
                   'label':planet.provenance['label']['sha256'], 'radii_m':RADIUS,
                   'candidate_centers':CANDIDATES, 'spacing_m':SPACING_M,
                   'sources':{c['id']:c['source']['sha256'] for c in candidates},
                   'climate':climate.get('provenance',{}).get('sha256')}
    run_id = hashlib.sha256(json.dumps(fingerprint,sort_keys=True).encode()).hexdigest()[:16]
    result = {'run_id':run_id,'computed_at':datetime.now(timezone.utc).isoformat(),'method_version':METHOD_VERSION,
              'method':{'name':'Unsupervised terrain KNN using Earth-fitted robust feature scales',
                        'formula':model.metadata()['distance'],
                        'range':'Nonnegative and unbounded','lower_is_closer':True,'not_a_probability':True,
                        'cell_spacing_m':SPACING_M,'window_width_m':220000,'grid_shape':[11,11],
                        'features':FEATURES,'subsamples_per_cell':25,'model':model.metadata()},
              'reproducibility':{'inputs':fingerprint,'numpy_version':np.__version__},
              'reference':reference,'candidates':candidates,'excluded':failures,
              'range_diagnostics':range_diagnostics,
              'sensitivity':sensitivity,'sensitivity_analysis':sensitivity_analysis,
              'data_quality':data_quality,'winner_climate':climate,'limitations':LIMITATIONS}
    (DATA / f'run-{run_id}.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    return result


def load_run(run_id):
    if not isinstance(run_id,str) or len(run_id)!=16 or any(c not in '0123456789abcdef' for c in run_id):
        raise ValueError('Invalid run identifier.')
    return json.loads((DATA/f'run-{run_id}.json').read_text(encoding='utf-8'))
