"""Bounded, deterministic terrestrial window discovery outside the seven-site baseline."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from urllib.parse import quote

import numpy as np
import shapefile
import shapely
from shapely.geometry import Polygon, box, shape
from shapely.ops import unary_union

from science import FEATURES, RADIUS, SPACING_M, TARGETS, coordinates, features, window
from sources import DATA, ETOPO, Raster, fetch, planetary_raster
from terrain_knn import TerrainKNN

OUTPUT = Path(__file__).resolve().parent.parent / 'results' / 'terrestrial-discovery'
RAW_CACHE = DATA / 'discovery'
TILE = {'south': 4.0, 'north': 14.0, 'west': -2.0, 'east': 8.0}
LATITUDE_BOUNDS = (6.0, 12.0)
LATITUDE_ROWS = 7
LONGITUDE_COLUMNS = tuple(range(7))
GRID_SIZE = 11
SOURCE_FILL = 32767
SOURCE_URL = ETOPO + '?' + quote('altitude[(4):1:(14)][(-2):1:(8)]', safe='(),:')
SOURCE_SHA256 = '8e3f767b8e5246f59a8a27b68d0ce2e139bb5f5c4aea798df01ce37c905fd06f'
MASKS = {
    'land': ('4.1.0', '0b8e670cf80dce9cbebe2a193bc44ba5602758c22e1fa603980553646d7ff162'),
    'lakes': ('5.0.0', 'f28d42c286d96b57a17aac2cbeb432f8c65532c20063495711fbc64e24666df3'),
    'glaciated_areas': ('4.1.0', 'f48644b4523482501bcd380c4b7345ba574ab79b87df753447d772ea239b7daf'),
}
MASK_BASE = 'https://naturalearth.s3.amazonaws.com/50m_physical/'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def candidate_centers():
    """Uniform sin(latitude)/longitude lattice over a fixed bounded search tile."""
    lo, hi = np.sin(np.radians(LATITUDE_BOUNDS))
    latitudes = np.degrees(np.arcsin(np.linspace(lo, hi, LATITUDE_ROWS)))
    return [{'id': f'wa-r{row:02d}-c{col:02d}', 'latitude': float(lat),
             'longitude': float(lon), 'region': 'Bounded West Africa search tile'}
            for row, lat in enumerate(latitudes)
            for col, lon in enumerate(LONGITUDE_COLUMNS)]


def read_mask(name):
    version, expected_hash = MASKS[name]
    url = MASK_BASE + f'ne_50m_{name}.zip'
    cached = RAW_CACHE / f'ne_50m_{name}.zip'
    raw = cached.read_bytes() if cached.exists() else fetch(url, 'zip', magic=b'PK')[0]
    if len(raw) > 2_000_000 or sha256(raw) != expected_hash:
        raise ValueError(f'{name} mask size or source checksum changed; review the source before proceeding.')
    prefix = f'ne_50m_{name}'
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        declared = archive.read(prefix + '.VERSION.txt').decode('ascii').strip()
        if declared != version:
            raise ValueError(f'{name} mask version does not match the pinned experiment.')
        projection = archive.read(prefix + '.prj').decode('ascii')
        if 'WGS_1984' not in projection:
            raise ValueError(f'{name} mask is not declared in WGS 84 geographic coordinates.')
        reader = shapefile.Reader(
            shp=io.BytesIO(archive.read(prefix + '.shp')),
            shx=io.BytesIO(archive.read(prefix + '.shx')),
            dbf=io.BytesIO(archive.read(prefix + '.dbf')))
        tile = box(TILE['west'], TILE['south'], TILE['east'], TILE['north'])
        pieces = [shape(part.__geo_interface__).intersection(tile)
                  for part in reader.shapes() if box(*part.bbox).intersects(tile)]
        geometry = unary_union([part for part in pieces if not part.is_empty])
    return geometry, {'url': url, 'sha256': expected_hash, 'version': version,
                      'source_features': len(reader), 'local_intersecting_features': len(pieces),
                      'scale': '1:50m', 'role': name}


def earth_tile():
    raw, meta = fetch(SOURCE_URL, 'csv')
    if sha256(raw) != SOURCE_SHA256 or len(raw) > 20_000_000:
        raise ValueError('ETOPO1 regional source checksum or size changed; review before proceeding.')
    rows = raw.splitlines()
    if rows[:2] != [b'latitude,longitude,altitude', b'degrees_north,degrees_east,m']:
        raise ValueError('Unexpected ETOPO1 CSV columns or units.')
    samples = np.loadtxt(io.BytesIO(raw), delimiter=',', skiprows=2)
    axis_size = 601
    if samples.shape != (axis_size**2, 3):
        raise ValueError('ETOPO1 subset has unexpected shape.')
    latitudes = np.linspace(TILE['south'], TILE['north'], axis_size)
    longitudes = np.linspace(TILE['west'], TILE['east'], axis_size)
    expected_lat, expected_lon = np.meshgrid(latitudes, longitudes, indexing='ij')
    if not np.allclose(samples[:, 0], expected_lat.ravel(), atol=1e-9, rtol=0) or not np.allclose(
            samples[:, 1], expected_lon.ravel(), atol=1e-9, rtol=0):
        raise ValueError('ETOPO1 node registration or ordering differs from the declared grid.')
    values = samples[:, 2].reshape((axis_size, axis_size))
    if not np.isfinite(values).all() or np.any(values == SOURCE_FILL):
        raise ValueError('ETOPO1 tile includes missing values; a separate coverage strategy is required.')
    # Retrieval time is cache metadata, not part of the reproducible scientific input.
    stable_meta = {key: meta[key] for key in ('url', 'sha256', 'bytes')}
    provenance = {**stable_meta, 'title': 'NOAA ETOPO1 Ice Surface via NOAA/AOML ERDDAP',
                  'unit': 'm', 'registration': 'grid nodes, one arc-minute',
                  'citation': 'https://doi.org/10.7289/V5C8276M'}
    return Raster(values, latitudes, longitudes, provenance), provenance


def footprint(center):
    """Densified boundary of the existing nominal 220 km local square."""
    half = GRID_SIZE * SPACING_M / 2
    axis = np.linspace(-half, half, 9)
    edges = ([(-half, y) for y in axis] + [(x, half) for x in axis]
             + [(half, y) for y in axis[::-1]] + [(x, -half) for x in axis[::-1]])
    coords = [coordinates(center['latitude'], center['longitude'], x, y, RADIUS['earth'])
              for x, y in edges]
    return Polygon([(float(lon), float(lat)) for lat, lon in coords])


def source_neighbors(center, raster):
    """Return the source nodes available to every baseline bilinear query."""
    axis = np.arange(-5, 6) * SPACING_M
    x, y = np.meshgrid(axis, axis)
    neighbors = []
    for dy in (-8000, -4000, 0, 4000, 8000):
        for dx in (-8000, -4000, 0, 4000, 8000):
            lat, lon = coordinates(center['latitude'], center['longitude'], x + dx, y + dy, RADIUS['earth'])
            row = (lat - raster.lat[0]) / (raster.lat[1] - raster.lat[0])
            col = (lon - raster.lon[0]) / (raster.lon[1] - raster.lon[0])
            if not np.isfinite(row).all() or not np.isfinite(col).all() or (row < 0).any() or (col < 0).any() or (
                    row > len(raster.lat)-1).any() or (col > len(raster.lon)-1).any():
                return None
            i = np.minimum(np.floor(row).astype(int), len(raster.lat)-2)
            j = np.minimum(np.floor(col).astype(int), len(raster.lon)-2)
            for ii, jj in ((i, j), (i+1, j), (i, j+1), (i+1, j+1)):
                neighbors.append((raster.lon[jj], raster.lat[ii]))
    longitude = np.concatenate([pair[0].ravel() for pair in neighbors])
    latitude = np.concatenate([pair[1].ravel() for pair in neighbors])
    return longitude, latitude


def eligibility(center, raster, land, lakes, glaciated):
    polygon = footprint(center)
    quality = {'expected_queries': 3025, 'expected_cells': 121,
               'footprint_complete_land': bool(land.covers(polygon)),
               'inland_water_intersects': bool(lakes.intersects(polygon)),
               'mapped_glaciated_area_intersects': bool(glaciated.intersects(polygon)),
               'ice_inventory_note': 'Natural Earth glaciated areas are generalized and include some deglaciated land; no current ice-free or seasonal-snow status is established.'}
    if not polygon.is_valid or polygon.is_empty:
        return 'invalid_footprint', quality
    if not quality['footprint_complete_land']:
        return 'mixed_land_or_ocean', quality
    if quality['inland_water_intersects']:
        return 'inland_water_intersection', quality
    if quality['mapped_glaciated_area_intersects']:
        return 'mapped_glaciated_area', quality
    nodes = source_neighbors(center, raster)
    if nodes is None:
        return 'insufficient_elevation_coverage', quality
    longitude, latitude = nodes
    locations = shapely.points(longitude, latitude)
    valid = (shapely.covers(land, locations) & ~shapely.intersects(lakes, locations)
             & ~shapely.intersects(glaciated, locations))
    quality['source_node_checks'] = int(valid.size)
    quality['valid_land_node_checks'] = int(np.count_nonzero(valid))
    if not np.all(valid):
        return 'mixed_bilinear_source_nodes', quality
    return 'eligible_land_topography', quality


def write_json(path, document):
    path.write_text(json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')


def run():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    raster, earth_source = earth_tile()
    masks = {name: read_mask(name) for name in MASKS}
    centers = candidate_centers()
    catalog = []
    for center in centers:
        status, quality = eligibility(center, raster, *(masks[name][0] for name in MASKS))
        record = {**center, 'status': status, 'quality': quality}
        if status == 'eligible_land_topography':
            try:
                grid = window(raster, center, 'earth')
                record['features'] = features(grid)
                record['source_sha256'] = earth_source['sha256']
            except (ValueError, RuntimeError) as exc:
                record['status'] = 'insufficient_elevation_coverage'
                record['quality']['reason'] = str(exc)
        catalog.append(record)
    candidates = [record for record in catalog if record['status'] == 'eligible_land_topography']
    if len(candidates) < 2:
        raise RuntimeError('The generated catalog has too few complete land windows for Earth-only IQR calibration.')
    model = TerrainKNN(FEATURES).fit(candidates)
    rankings = {}
    for target_id, target in TARGETS.items():
        planet = planetary_raster(target['body'])
        reference = features(window(planet, target, target['body']))
        explanations = model.explain(reference)
        rankings[target_id] = {
            'reference': {**target, 'features': reference, 'source_sha256': planet.provenance['sha256']},
            'range_diagnostics': model.range_diagnostics(reference),
            'ranking': [{'rank': rank, 'id': identifier,
                         'latitude': next(c['latitude'] for c in candidates if c['id'] == identifier),
                         'longitude': next(c['longitude'] for c in candidates if c['id'] == identifier),
                         'region': 'Bounded West Africa search tile',
                         'features': next(c['features'] for c in candidates if c['id'] == identifier),
                         'quality': next(c['quality'] for c in candidates if c['id'] == identifier),
                         'distance': distance, 'distance_explanation': explanations[identifier]}
                        for rank, (identifier, distance) in enumerate(model.query(reference), 1)]}
    provenance = {'method': 'bounded-equal-area-lattice-v1',
                  'implementation_sha256': sha256(Path(__file__).read_bytes()),
                  'tile': TILE, 'center_latitude_bounds': LATITUDE_BOUNDS,
                  'center_longitudes_deg': LONGITUDE_COLUMNS, 'latitude_rows': LATITUDE_ROWS,
                  'center_generation': 'uniform sin(latitude) and 1-degree longitude steps',
                  'earth_source': earth_source, 'masks': {k: v[1] for k, v in masks.items()},
                  'sampling': {'window_width_m': 220000, 'cell_spacing_m': SPACING_M,
                               'grid_shape': [11, 11], 'bilinear_queries_per_cell': 25},
                  'feature_names': list(FEATURES), 'model': model.metadata(),
                  'baseline_catalog': 'Seven predefined Earth windows remain a separate production analysis.',
                  'scope_limitations': ['Bounded regional search, not global or representative of all terrestrial terrain.',
                                        'Natural Earth 1:50m mask omits small water features and has generalized shorelines.',
                                        'The glaciated-area screen is historical and cannot establish absence of seasonal snow or current ice.',
                                        'ETOPO1 grid spacing and interpolation do not establish effective terrain resolution.',
                                        'Nearest within generated windows is not a validated planetary analog.']}
    write_json(OUTPUT / 'catalog.json', {'provenance': provenance,
                                         'generated_count': len(catalog), 'evaluated_count': len(candidates),
                                         'excluded_count': len(catalog) - len(candidates), 'candidates': catalog})
    write_json(OUTPUT / 'rankings.json', {'provenance': provenance, 'references': rankings})
    return {'generated': len(catalog), 'evaluated': len(candidates),
            'excluded': len(catalog) - len(candidates),
            'winners': {key: value['ranking'][0] for key, value in rankings.items()}}


if __name__ == '__main__':
    summary = run()
    print(json.dumps({'generated': summary['generated'], 'evaluated': summary['evaluated'],
                      'excluded': summary['excluded'],
                      'winners': {key: {'id': item['id'], 'latitude': item['latitude'],
                                        'longitude': item['longitude'], 'distance': item['distance']}
                                  for key, item in summary['winners'].items()}},
                     indent=2, sort_keys=True))
