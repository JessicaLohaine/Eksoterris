"""Controlled regional discovery perturbations; production rankings stay untouched."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import shapefile
import shapely
from shapely.geometry import Polygon, box, shape
from shapely.ops import unary_union

from science import FEATURES, RADIUS, SPACING_M, TARGETS, coordinates
from sources import fetch, planetary_raster
from spatial_scale_experiment import sample_window, terrain_descriptors
from terrain_knn import TerrainKNN
from terrestrial_discovery import (MASKS, OUTPUT as BASE_OUTPUT, TILE, candidate_centers,
                                   earth_tile, read_mask, sha256)

OUTPUT = BASE_OUTPUT.parent / 'terrestrial-discovery-robustness-v1'
FINE_MASKS = {
    'land': ('5.1.1', 'e547d749445eaa0964aba76738090ec88f5e63c4585122170f98c67a7ea922dc'),
    'lakes': ('5.0.0', '0803a06f9c3cb4671d89b68c48b142aad9366ba40f665245e12a913fbc61722a'),
    'glaciated_areas': ('4.1.0', 'de6ff396ab7eee8cbe2146030cc29278ef67c468e5675c748b1372e241ecbbff'),
}
CONFIGS = (
    {'id': 'repeat-220-11-50m', 'kind': 'baseline_control', 'rows': 7, 'columns': 7,
     'shift': False, 'width_m': 220000, 'grid_size': 11, 'mask_scale': '50m'},
    {'id': 'shift-220-11-50m', 'kind': 'origin', 'rows': 7, 'columns': 7,
     'shift': True, 'width_m': 220000, 'grid_size': 11, 'mask_scale': '50m'},
    {'id': 'coarse-220-11-50m', 'kind': 'center_spacing', 'rows': 4, 'columns': 4,
     'shift': False, 'width_m': 220000, 'grid_size': 11, 'mask_scale': '50m'},
    {'id': 'dense-220-11-50m', 'kind': 'center_density', 'rows': 13, 'columns': 13,
     'shift': False, 'width_m': 220000, 'grid_size': 11, 'mask_scale': '50m'},
    {'id': 'extent-180-9-50m', 'kind': 'window_extent', 'rows': 7, 'columns': 7,
     'shift': False, 'width_m': 180000, 'grid_size': 9, 'mask_scale': '50m'},
    {'id': 'extent-260-13-50m', 'kind': 'window_extent', 'rows': 7, 'columns': 7,
     'shift': False, 'width_m': 260000, 'grid_size': 13, 'mask_scale': '50m'},
    {'id': 'repeat-220-11-10m', 'kind': 'mask_detail', 'rows': 7, 'columns': 7,
     'shift': False, 'width_m': 220000, 'grid_size': 11, 'mask_scale': '10m'},
    {'id': 'dense-220-11-10m', 'kind': 'dense_mask_detail', 'rows': 13, 'columns': 13,
     'shift': False, 'width_m': 220000, 'grid_size': 11, 'mask_scale': '10m'},
)


def centers(config):
    """Frozen rectangular equal-area lattice; offset is half an original step."""
    low = np.sin(np.radians(6.0))
    high = np.sin(np.radians(12.0))
    latitude_step = (high - low) / (config['rows'] - 1)
    longitude_step = 6.0 / (config['columns'] - 1)
    offset = 0.5 if config['shift'] else 0.0
    result = []
    for row in range(config['rows']):
        lat = float(np.degrees(np.arcsin(low + (row + offset) * latitude_step)))
        for col in range(config['columns']):
            lon = float((col + offset) * longitude_step)
            identifier = (f'wa-r{row:02d}-c{col:02d}' if config['kind'] == 'baseline_control'
                          else f"{config['id']}-r{row:02d}-c{col:02d}")
            result.append({'id': identifier, 'latitude': lat, 'longitude': lon,
                           'region': 'Bounded West Africa search tile',
                           'coordinate_key': f'{lat:.7f},{lon:.7f}'})
    return result


def fine_mask(name):
    version, checksum = FINE_MASKS[name]
    url = f'https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_{name}.zip'
    raw, _ = fetch(url, 'zip', magic=b'PK')
    if len(raw) > 8_000_000 or sha256(raw) != checksum:
        raise ValueError(f'Pinned 1:10m {name} mask bytes changed; review source before continuing.')
    prefix = f'ne_10m_{name}'
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if archive.read(prefix + '.VERSION.txt').decode('ascii').strip() != version:
            raise ValueError(f'Pinned 1:10m {name} mask version changed.')
        if 'WGS_1984' not in archive.read(prefix + '.prj').decode('ascii'):
            raise ValueError(f'Unexpected 1:10m {name} coordinate reference.')
        reader = shapefile.Reader(shp=io.BytesIO(archive.read(prefix + '.shp')),
                                  shx=io.BytesIO(archive.read(prefix + '.shx')),
                                  dbf=io.BytesIO(archive.read(prefix + '.dbf')))
        tile = box(TILE['west'], TILE['south'], TILE['east'], TILE['north'])
        pieces = [shape(part.__geo_interface__).intersection(tile) for part in reader.shapes()
                  if box(*part.bbox).intersects(tile)]
        geometry = unary_union([piece for piece in pieces if not piece.is_empty])
    return geometry, {'url': url, 'version': version, 'sha256': checksum,
                      'local_intersecting_features': len(pieces), 'scale': '1:10m'}


def footprint(center, width_m):
    half = width_m / 2
    axis = np.linspace(-half, half, 9)
    edges = ([(-half, y) for y in axis] + [(x, half) for x in axis]
             + [(half, y) for y in axis[::-1]] + [(x, -half) for x in axis[::-1]])
    points = [coordinates(center['latitude'], center['longitude'], x, y, RADIUS['earth'])
              for x, y in edges]
    return Polygon([(float(lon), float(lat)) for lat, lon in points])


def query_source_nodes(center, raster, width_m, grid_size):
    """Inspect all four source nodes for each of the 25 queries per grid cell."""
    spacing = width_m / grid_size
    axis = (np.arange(grid_size) - grid_size // 2) * spacing
    x, y = np.meshgrid(axis, axis)
    longitude, latitude = [], []
    for dy in (-0.4, -0.2, 0, 0.2, 0.4):
        for dx in (-0.4, -0.2, 0, 0.2, 0.4):
            lat, lon = coordinates(center['latitude'], center['longitude'],
                                   x + dx * spacing, y + dy * spacing, RADIUS['earth'])
            row = (lat - raster.lat[0]) / (raster.lat[1] - raster.lat[0])
            col = (lon - raster.lon[0]) / (raster.lon[1] - raster.lon[0])
            if (not np.isfinite(row).all() or not np.isfinite(col).all()
                    or (row < 0).any() or (col < 0).any()
                    or (row > len(raster.lat) - 1).any() or (col > len(raster.lon) - 1).any()):
                return None
            i = np.minimum(np.floor(row).astype(int), len(raster.lat) - 2)
            j = np.minimum(np.floor(col).astype(int), len(raster.lon) - 2)
            for ii, jj in ((i, j), (i + 1, j), (i, j + 1), (i + 1, j + 1)):
                longitude.append(raster.lon[jj].ravel())
                latitude.append(raster.lat[ii].ravel())
    return np.concatenate(longitude), np.concatenate(latitude)


def eligibility(center, raster, masks, width_m, grid_size):
    polygon = footprint(center, width_m)
    land, lakes, ice = (masks[name][0] for name in MASKS)
    quality = {'expected_queries': 25 * grid_size**2,
               'expected_source_node_checks': 100 * grid_size**2,
               'complete_mapped_land_footprint': bool(land.covers(polygon)),
               'mapped_inland_water_intersects': bool(lakes.intersects(polygon)),
               'mapped_glaciated_area_intersects': bool(ice.intersects(polygon)),
               'current_ice_and_seasonal_snow_status': 'not_established'}
    if polygon.is_empty or not polygon.is_valid:
        return 'invalid_footprint', quality
    if not quality['complete_mapped_land_footprint']:
        return 'mixed_land_or_ocean', quality
    if quality['mapped_inland_water_intersects']:
        return 'inland_water_intersection', quality
    if quality['mapped_glaciated_area_intersects']:
        return 'mapped_glaciated_area', quality
    nodes = query_source_nodes(center, raster, width_m, grid_size)
    if nodes is None:
        return 'insufficient_elevation_coverage', quality
    locations = shapely.points(*nodes)
    valid = (shapely.covers(land, locations) & ~shapely.intersects(lakes, locations)
             & ~shapely.intersects(ice, locations))
    quality['valid_land_node_checks'] = int(np.count_nonzero(valid))
    if not np.all(valid):
        return 'mixed_bilinear_source_nodes', quality
    return 'eligible_land_topography', quality


def equal_area(polygon):
    """Spherical Lambert cylindrical equal-area transform for this no-seam tile."""
    radius = RADIUS['earth']
    return shapely.transform(polygon, lambda coords: np.column_stack(
        (radius * np.radians(coords[:, 0]), radius * np.sin(np.radians(coords[:, 1])))))


def overlap_analysis(candidates, width_m):
    """Descriptive pairwise IoU and sensitivity to two deterministic spatial orders."""
    projected = [equal_area(footprint(c, width_m)) for c in candidates]
    pairs = []
    matrix = np.eye(len(candidates))
    for i, a in enumerate(projected):
        for j in range(i + 1, len(projected)):
            b = projected[j]
            if not a.intersects(b):
                continue
            intersection = a.intersection(b).area
            if intersection == 0:
                continue
            union = a.area + b.area - intersection
            ratio = intersection / union
            matrix[i, j] = matrix[j, i] = ratio
            pairs.append({'first': candidates[i]['id'], 'second': candidates[j]['id'],
                          'intersection_over_union': ratio,
                          'fraction_of_smaller_window': intersection / min(a.area, b.area)})
    ratios = [p['intersection_over_union'] for p in pairs]
    diagnostics = {'candidate_count': len(candidates), 'possible_pairs': len(candidates) * (len(candidates) - 1) // 2,
                   'intersecting_pairs': len(pairs),
                   'iou_distribution_intersecting': {key: float(value) for key, value in zip(
                       ('min', 'median', 'p95', 'max'),
                       (np.min(ratios), np.median(ratios), np.percentile(ratios, 95), np.max(ratios)))} if ratios else None,
                   'trial_pair_counts': {str(threshold): sum(r > threshold for r in ratios)
                                         for threshold in (0.1, 0.25, 0.5)},
                   'pairs': pairs}
    # Thinning is a diagnostic only. The trial IoU is not an eligibility rule.
    orders = {'southwest_first': list(range(len(candidates))),
              'northeast_first': list(reversed(range(len(candidates))))}
    selected = {}
    for name, order in orders.items():
        kept = []
        for i in order:
            if all(matrix[i, j] <= 0.25 for j in kept):
                kept.append(i)
        selected[name] = [candidates[i]['id'] for i in kept]
    diagnostics['trial_thinning_iou_0_25'] = selected
    return diagnostics


def run_config(config, raster, masks, planets, source, center_records=None):
    catalog = []
    for center in (centers(config) if center_records is None else center_records):
        status, quality = eligibility(center, raster, masks, config['width_m'], config['grid_size'])
        record = {**center, 'status': status, 'quality': quality}
        if status == 'eligible_land_topography':
            try:
                grid = sample_window(raster, center, 'earth', config['width_m'], config['grid_size'])
                record['features'] = terrain_descriptors(grid, config['width_m'] / config['grid_size'])
                record['source_sha256'] = source['sha256']
            except (ValueError, RuntimeError) as exc:
                record['status'] = 'insufficient_elevation_coverage'
                record['quality']['reason'] = str(exc)
        catalog.append(record)
    candidates = [c for c in catalog if c['status'] == 'eligible_land_topography']
    if len(candidates) < 2:
        raise ValueError(f"{config['id']}: insufficient complete Earth windows for IQR calibration.")
    model = TerrainKNN(FEATURES).fit(candidates)
    by_id = {c['id']: c for c in candidates}
    overlap = overlap_analysis(candidates, config['width_m'])
    references = {}
    for target_id, target in TARGETS.items():
        planet = planets[target['body']]
        grid = sample_window(planet, target, target['body'], config['width_m'], config['grid_size'])
        ref = terrain_descriptors(grid, config['width_m'] / config['grid_size'])
        explanations = model.explain(ref)
        ranking = [{'rank': rank, 'id': identifier, 'coordinate_key': by_id[identifier]['coordinate_key'],
                    'latitude': by_id[identifier]['latitude'], 'longitude': by_id[identifier]['longitude'],
                    'features': by_id[identifier]['features'], 'distance': distance,
                    'distance_explanation': explanations[identifier]}
                   for rank, (identifier, distance) in enumerate(model.query(ref), 1)]
        thinned = {}
        for order, ids in overlap['trial_thinning_iou_0_25'].items():
            if len(ids) < 2:
                thinned[order] = {'status': 'insufficient_candidates', 'selected_ids': ids}
                continue
            reduced = TerrainKNN(FEATURES).fit([by_id[identifier] for identifier in ids])
            winner = reduced.query(ref)[0][0]
            thinned[order] = {'status': 'computed', 'selected_ids': ids, 'winner_id': winner,
                              'winner_coordinate_key': by_id[winner]['coordinate_key'],
                              'earth_iqr': dict(zip(FEATURES, reduced.scale.tolist())),
                              'range_diagnostics': reduced.range_diagnostics(ref)}
        references[target_id] = {'reference': {**target, 'features': ref,
                                               'source_sha256': planet.provenance['sha256']},
                                 'range_diagnostics': model.range_diagnostics(ref),
                                 'ranking': ranking, 'trial_spatial_thinning': thinned}
    return {'configuration': config, 'source': source,
            'masks': {name: masks[name][1] for name in MASKS},
            'catalog': catalog, 'generated_count': len(catalog), 'evaluated_count': len(candidates),
            'excluded_count': len(catalog) - len(candidates),
            'exclusion_reasons': dict(Counter(c['status'] for c in catalog if c['status'] != 'eligible_land_topography')),
            'model': model.metadata(), 'overlap': overlap, 'references': references}


def validate_original(repeated):
    original_catalog = json.loads((BASE_OUTPUT / 'catalog.json').read_text(encoding='utf-8'))
    original_ranks = json.loads((BASE_OUTPUT / 'rankings.json').read_text(encoding='utf-8'))
    if repeated['generated_count'] != 49 or repeated['evaluated_count'] != 26:
        raise ValueError('The original discovery population changed.')
    for old, new in zip(original_catalog['candidates'], repeated['catalog']):
        if old['id'] != new['id'] or old['status'] != new['status']:
            raise ValueError(f"Original eligibility changed at {old['id']}.")
        if old['status'] == 'eligible_land_topography':
            for name in FEATURES:
                np.testing.assert_allclose(old['features'][name], new['features'][name], rtol=0, atol=1e-8)
    for target_id in TARGETS:
        old = original_ranks['references'][target_id]
        new = repeated['references'][target_id]
        for name in FEATURES:
            np.testing.assert_allclose(old['reference']['features'][name], new['reference']['features'][name],
                                       rtol=0, atol=1e-8)
        if [r['id'] for r in old['ranking']] != [r['id'] for r in new['ranking']]:
            raise ValueError(f'Original ranking order changed for {target_id}.')
        for a, b in zip(old['ranking'], new['ranking']):
            np.testing.assert_allclose(a['distance'], b['distance'], rtol=0, atol=1e-8)
    return {'catalog_sha256': sha256((BASE_OUTPUT / 'catalog.json').read_bytes()),
            'rankings_sha256': sha256((BASE_OUTPUT / 'rankings.json').read_bytes()),
            'maximum_accepted_numerical_difference': 1e-8,
            'status': 'reproduced_without_changing_original_files'}


def compare_masks(repeated, fine):
    old = {c['coordinate_key']: c for c in repeated['catalog']}
    changed = [{'coordinate_key': c['coordinate_key'], 'latitude': c['latitude'],
                'longitude': c['longitude'], 'fifty_m_status': old[c['coordinate_key']]['status'],
                'ten_m_status': c['status']}
               for c in fine['catalog'] if c['status'] != old[c['coordinate_key']]['status']]
    return {'changed_count': len(changed), 'changed_centers': changed,
            'note': 'Agreement between map scales does not establish ground-truth coastline, lake or current ice status.'}


def write_json(path, content):
    path.write_text(json.dumps(content, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')


def run():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    raster, source = earth_tile()
    masks = {'50m': {name: read_mask(name) for name in MASKS},
             '10m': {name: fine_mask(name) for name in MASKS}}
    planets = {body: planetary_raster(body) for body in ('moon', 'mars')}
    summaries = []
    repeated, fine, dense_coarse, dense_fine = None, None, None, None
    for config in CONFIGS:
        document = run_config(config, raster, masks[config['mask_scale']], planets, source)
        if config['kind'] == 'baseline_control':
            repeated = document
            baseline = validate_original(repeated)
        if config['kind'] == 'mask_detail':
            fine = document
        if config['kind'] == 'center_density':
            dense_coarse = document
        if config['kind'] == 'dense_mask_detail':
            dense_fine = document
        write_json(OUTPUT / (config['id'] + '.json'), document)
        summaries.append({'id': config['id'], 'kind': config['kind'],
                          'generated': document['generated_count'], 'evaluated': document['evaluated_count'],
                          'excluded': document['excluded_count'],
                          'exclusion_reasons': document['exclusion_reasons'],
                          'intersecting_pairs': document['overlap']['intersecting_pairs'],
                          'trial_pair_counts': document['overlap']['trial_pair_counts'],
                          'thinned_counts': {key: len(ids) for key, ids in
                                             document['overlap']['trial_thinning_iou_0_25'].items()},
                          'winners': {key: {'id': value['ranking'][0]['id'],
                                            'latitude': value['ranking'][0]['latitude'],
                                            'longitude': value['ranking'][0]['longitude'],
                                            'outside_features': value['range_diagnostics']['outside_features'],
                                            'largest_numerical_contributor': value['ranking'][0]['distance_explanation']['largest_numerical_contributor'],
                                            'thinning': {order: item.get('winner_coordinate_key') for order, item
                                                         in value['trial_spatial_thinning'].items()}}
                                      for key, value in document['references'].items()}})
    summary = {'version': 'terrestrial-discovery-robustness-v1',
               'implementation_sha256': sha256(Path(__file__).read_bytes()),
               'baseline': baseline, 'source': source,
               'mask_scale_comparison': {'original_grid': compare_masks(repeated, fine),
                                         'dense_grid': compare_masks(dense_coarse, dense_fine)},
               'experiments': summaries,
               'scope': 'Bounded regional perturbations; neither a global search nor validated analog discovery.',
               'interpretation': 'Nearest rank is relative; different Earth IQR calibrations prohibit direct distance comparisons.'}
    write_json(OUTPUT / 'summary.json', summary)
    return summary


if __name__ == '__main__':
    report = run()
    for item in report['experiments']:
        print(item['id'], item['generated'], item['evaluated'], item['excluded'],
              {target: data['id'] for target, data in item['winners'].items()})
    print('Mask classifications changed:',
          {key: value['changed_count'] for key, value in report['mask_scale_comparison'].items()})
