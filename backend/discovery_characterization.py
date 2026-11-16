"""Shift two existing regional lattices and assess geographic support for shortlisting."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from shapely.geometry import box

from discovery_expansion import (OUTPUT as PREVIOUS, REGIONS, SIZE, WIDTH,
                                 regional_mask, regional_raster, rank_combined, write_json)
from discovery_robustness import equal_area, footprint, run_config
from science import FEATURES, TARGETS
from sources import planetary_raster
from terrestrial_discovery import MASKS, OUTPUT as FIRST_OUTPUT, sha256

OUTPUT = FIRST_OUTPUT.parent / 'terrestrial-discovery-characterization-v1'


def shifted_centers(region):
    """Half-step shift in sin(latitude) and longitude, fixed before reading ranks."""
    tile = region['tile']
    low, high = np.sin(np.radians([tile['south'] + 2, tile['north'] - 2]))
    step = (high - low) / 6
    return [{'id': f"{region['id']}-shift-r{row:02d}-c{col:02d}",
             'latitude': float(np.degrees(np.arcsin(low + (row + 0.5) * step))),
             'longitude': float(tile['west'] + 2 + col + 0.5),
             'region': region['region'],
             'coordinate_key': f"{np.degrees(np.arcsin(low + (row + 0.5) * step)):.7f},{tile['west'] + 2 + col + 0.5:.7f}"}
            for row in range(7) for col in range(7)]


def overlap_fraction(a, b):
    first, second = equal_area(footprint(a, WIDTH)), equal_area(footprint(b, WIDTH))
    intersection = first.intersection(second).area
    return float(intersection / (first.area + second.area - intersection))


def geographic_screen(candidate, masks):
    """Approximate distances inside the clipped tile, excluding artificial tile edges."""
    land, lakes, ice = (masks[name][0] for name in MASKS)
    footprint_m = equal_area(footprint(candidate, WIDTH))
    def distance(geometry):
        return float(footprint_m.distance(equal_area(geometry)) / 1000) if not geometry.is_empty else None
    tile = next((item['tile'] for item in REGIONS if item['region'] == candidate.get('region')), None)
    edge = box(tile['west'], tile['south'], tile['east'], tile['north']).boundary if tile else None
    coast = land.boundary.difference(edge.buffer(1e-9)) if edge else land.boundary
    return {'mapped_land_boundary_distance_km_approx': distance(coast),
            'mask_tile_boundary_distance_km_approx': distance(edge) if edge else None,
            'mapped_lake_distance_km_approx': distance(lakes),
            'mapped_glaciated_area_distance_km_approx': distance(ice),
            'land_footprint_covered': bool(land.covers(footprint(candidate, WIDTH))),
            'mapped_lake_intersection': bool(lakes.intersects(footprint(candidate, WIDTH))),
            'mapped_glaciated_area_intersection': bool(ice.intersects(footprint(candidate, WIDTH))),
            'distance_method': 'Spherical Lambert cylindrical equal-area approximation within the clipped tile; artificial tile edges excluded from land boundary; nearest features outside the tile are not assessed.',
            'current_ice_and_seasonal_water_status': 'unverified'}


def combined_screen(candidate, masks_by_region):
    for region in REGIONS:
        if candidate['region'] == region['region']:
            return geographic_screen(candidate, masks_by_region[region['id']])
    return {'status': 'outside_the_two_audited_regions'}


def compare_region(original, shifted, masks):
    a = {c['id']: c for c in original['catalog']}
    b = {c['id']: c for c in shifted['catalog']}
    leaders = {}
    for target in TARGETS:
        baseline = original['references'][target]
        changed = shifted['references'][target]
        x, y = baseline['ranking'][0], changed['ranking'][0]
        leaders[target] = {
            'original': {'id': x['id'], 'latitude': x['latitude'], 'longitude': x['longitude'],
                         'features': x['features'], 'distance_contributions': x['distance_explanation']['descriptors'],
                         'quality': a[x['id']]['quality'], 'geographic_screen': geographic_screen(x, masks)},
            'shifted': {'id': y['id'], 'latitude': y['latitude'], 'longitude': y['longitude'],
                        'features': y['features'], 'distance_contributions': y['distance_explanation']['descriptors'],
                        'quality': b[y['id']]['quality'], 'geographic_screen': geographic_screen(y, masks)},
            'footprint_intersection_over_union': overlap_fraction(x, y),
            'original_outside_features': baseline['range_diagnostics']['outside_features'],
            'shifted_outside_features': changed['range_diagnostics']['outside_features']}
    ranges = {}
    for name, doc in [('original', original), ('shifted', shifted)]:
        selected = [c for c in doc['catalog'] if c['status'] == 'eligible_land_topography']
        ranges[name] = {key: {'min': min(c['features'][key] for c in selected),
                              'max': max(c['features'][key] for c in selected)} for key in FEATURES}
    return {'generated': shifted['generated_count'], 'evaluated': shifted['evaluated_count'],
            'excluded': shifted['excluded_count'], 'exclusion_reasons': shifted['exclusion_reasons'],
            'original_evaluated': original['evaluated_count'],
            'original_exclusion_reasons': original['exclusion_reasons'],
            'ranges': ranges, 'earth_iqr': {'original': original['model']['earth_iqr'],
                                           'shifted': shifted['model']['earth_iqr']},
            'leaders': leaders,
            'interpretation': 'Each regional catalog has its own Earth IQR; compare ranks, coordinates and descriptors, not raw distances across catalogs.'}


def run():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    previous_combined = PREVIOUS / 'combined.json'
    old = json.loads(previous_combined.read_text(encoding='utf-8'))
    planets = {body: planetary_raster(body) for body in ('moon', 'mars')}
    shifted = []
    comparisons = {}
    regional_masks = {}
    for region in REGIONS:
        raster, source = regional_raster(region)
        masks = {name: regional_mask(name, region, '10m') for name in MASKS}
        regional_masks[region['id']] = masks
        config = {'id': region['id'] + '-shifted', 'kind': 'half_step_origin',
                  'rows': 7, 'columns': 7, 'width_m': WIDTH, 'grid_size': SIZE,
                  'mask_scale': '10m', 'tile': region['tile'],
                  'center_rule': 'sin(latitude) and longitude half-step offset from the original 7x7 lattice'}
        document = run_config(config, raster, masks, planets, source, shifted_centers(region))
        prior = json.loads((PREVIOUS / (region['id'] + '.json')).read_text(encoding='utf-8'))
        if prior['source']['sha256'] != source['sha256']:
            raise ValueError('Cannot compare changed source bytes.')
        comparisons[region['id']] = compare_region(prior, document, masks)
        write_json(OUTPUT / (region['id'] + '-shifted.json'), document)
        shifted.extend(c for c in document['catalog'] if c['status'] == 'eligible_land_topography')
    west = json.loads((FIRST_OUTPUT.parent / 'terrestrial-discovery-robustness-v1' /
                       'repeat-220-11-10m.json').read_text(encoding='utf-8'))
    combined = rank_combined([c for c in west['catalog'] if c['status'] == 'eligible_land_topography'] + shifted, planets)
    combined['comparison_baseline_sha256'] = sha256(previous_combined.read_bytes())
    combined['population'] = '26 original West Africa centers plus shifted South America and East Africa centers; recalibrated Earth IQR.'
    write_json(OUTPUT / 'combined-shifted.json', combined)
    summary = {'version': 'terrestrial-discovery-characterization-v1',
               'implementation_sha256': sha256(Path(__file__).read_bytes()),
               'preserved_original_combined_sha256': sha256(previous_combined.read_bytes()),
               'regions': comparisons,
               'combined': {'original_count': old['candidate_count'], 'shifted_count': combined['candidate_count'],
                            'references': {target: {
                                'original_first': {**{key: old['references'][target]['ranking'][0][key] for key in
                                                      ('id', 'latitude', 'longitude')},
                                                   'geographic_screen': combined_screen(
                                                       old['references'][target]['ranking'][0], regional_masks)},
                                'shifted_first': {**{key: combined['references'][target]['ranking'][0][key] for key in
                                                     ('id', 'latitude', 'longitude')},
                                                  'geographic_screen': combined_screen(
                                                      combined['references'][target]['ranking'][0], regional_masks)},
                                'original_outside': old['references'][target]['range_diagnostics']['outside_features'],
                                'shifted_outside': combined['references'][target]['range_diagnostics']['outside_features'],
                                'footprint_intersection_over_union': overlap_fraction(
                                    old['references'][target]['ranking'][0], combined['references'][target]['ranking'][0])}
                                            for target in TARGETS}},
               'scope': 'Two shifted regional grids and a separately recalibrated combined comparison; no analog validation.'}
    write_json(OUTPUT / 'summary.json', summary)
    return summary


if __name__ == '__main__':
    result = run()
    for region, info in result['regions'].items():
        print(region, info['generated'], info['evaluated'], info['excluded'])
        for target, row in info['leaders'].items():
            print(' ', target, row['original']['latitude'], row['original']['longitude'],
                  '->', row['shifted']['latitude'], row['shifted']['longitude'],
                  'IoU', row['footprint_intersection_over_union'])
    print('Combined candidate count:', result['combined']['shifted_count'])
