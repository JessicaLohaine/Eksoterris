"""Two predeclared regional terrain strata, generated centers, and a combined exploratory catalog."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from urllib.parse import quote

import numpy as np
import shapefile
from shapely.geometry import box, shape
from shapely.ops import unary_union

from discovery_robustness import FINE_MASKS, OUTPUT as ROBUST_OUTPUT, run_config
from science import FEATURES, TARGETS
from sources import ETOPO, Raster, fetch, planetary_raster
from terrain_knn import TerrainKNN
from terrestrial_discovery import MASKS, OUTPUT as FIRST_OUTPUT, sha256

OUTPUT = FIRST_OUTPUT.parent / 'terrestrial-discovery-expansion-v1'
REGIONS = (
    {'id': 'south-america-elevation-gradient', 'region': 'South American west-central elevation gradient',
     'tile': {'south': -26, 'north': -16, 'west': -73, 'east': -63},
     'selection_reason': 'A different continent and southern latitude with strong regional relief variation; tile bounds are fixed before candidate ranking.'},
    {'id': 'east-africa-inland-water-gradient', 'region': 'East African inland elevation and water gradient',
     'tile': {'south': -4, 'north': 6, 'west': 30, 'east': 40},
     'selection_reason': 'A second continent and equatorial latitude with regional relief and mapped inland water; tile bounds are fixed before candidate ranking.'},
)
REGIONAL_SOURCE_SHA256 = {
    'south-america-elevation-gradient': '41ad976256e29290387d14807efc2729b7f105304f8333debd3a27ea163637ef',
    'east-africa-inland-water-gradient': '66f67b42d611a2bf69a0dd38c7fb7ecf93b54096bb27b47e5d7c07311ae10172',
}
SIZE = 11
WIDTH = 220000


def regional_centers(region):
    tile = region['tile']
    low, high = np.sin(np.radians([tile['south'] + 2, tile['north'] - 2]))
    latitudes = np.degrees(np.arcsin(np.linspace(low, high, 7)))
    longitudes = np.linspace(tile['west'] + 2, tile['east'] - 2, 7)
    return [{'id': f"{region['id']}-r{row:02d}-c{col:02d}",
             'latitude': float(lat), 'longitude': float(lon), 'region': region['region'],
             'coordinate_key': f'{lat:.7f},{lon:.7f}'}
            for row, lat in enumerate(latitudes) for col, lon in enumerate(longitudes)]


def regional_raster(region):
    tile = region['tile']
    query = f"altitude[({tile['south']}):1:({tile['north']})][({tile['west']}):1:({tile['east']})]"
    url = ETOPO + '?' + quote(query, safe='(),:')
    raw, meta = fetch(url, 'csv')
    if sha256(raw) != REGIONAL_SOURCE_SHA256[region['id']]:
        raise ValueError(f"Pinned ETOPO1 source bytes changed for {region['id']}.")
    if len(raw) > 20_000_000 or raw.splitlines()[:2] != [b'latitude,longitude,altitude',
                                                        b'degrees_north,degrees_east,m']:
        raise ValueError(f"Invalid regional ETOPO1 response for {region['id']}.")
    values = np.loadtxt(io.BytesIO(raw), delimiter=',', skiprows=2)
    if values.shape != (601**2, 3):
        raise ValueError(f"Unexpected ETOPO1 grid size for {region['id']}.")
    lat = np.linspace(tile['south'], tile['north'], 601)
    lon = np.linspace(tile['west'], tile['east'], 601)
    expected_lat, expected_lon = np.meshgrid(lat, lon, indexing='ij')
    if (not np.allclose(values[:, 0], expected_lat.ravel(), rtol=0, atol=1e-9)
            or not np.allclose(values[:, 1], expected_lon.ravel(), rtol=0, atol=1e-9)):
        raise ValueError(f"ETOPO1 coordinates changed for {region['id']}.")
    elevation = values[:, 2].reshape(601, 601)
    if not np.isfinite(elevation).all() or np.any(elevation == 32767):
        raise ValueError(f"ETOPO1 region contains missing data for {region['id']}.")
    source = {'url': url, 'sha256': sha256(raw), 'bytes': len(raw),
              'title': 'NOAA ETOPO1 Ice Surface via NOAA/AOML ERDDAP',
              'citation': 'https://doi.org/10.7289/V5C8276M',
              'registration': 'grid nodes, one arc-minute', 'unit': 'm'}
    if meta['sha256'] != source['sha256']:
        raise ValueError('The cached source manifest and bytes disagree.')
    return Raster(elevation, lat, lon, source), source


def regional_mask(name, region, scale):
    """Verify the same archived Natural Earth bytes before clipping to a regional tile."""
    version, checksum = (FINE_MASKS if scale == '10m' else MASKS)[name]
    prefix = f'ne_{scale}_{name}'
    url = f'https://naturalearth.s3.amazonaws.com/{scale}_physical/{prefix}.zip'
    raw, _ = fetch(url, 'zip', magic=b'PK')
    if len(raw) > 8_000_000 or sha256(raw) != checksum:
        raise ValueError(f'Pinned {scale} {name} mask has changed.')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if archive.read(prefix + '.VERSION.txt').decode('ascii').strip() != version:
            raise ValueError(f'Pinned {scale} {name} version has changed.')
        if 'WGS_1984' not in archive.read(prefix + '.prj').decode('ascii'):
            raise ValueError(f'Unexpected {scale} {name} coordinate reference.')
        reader = shapefile.Reader(shp=io.BytesIO(archive.read(prefix + '.shp')),
                                  shx=io.BytesIO(archive.read(prefix + '.shx')),
                                  dbf=io.BytesIO(archive.read(prefix + '.dbf')))
        tile = region['tile']
        extent = box(tile['west'], tile['south'], tile['east'], tile['north'])
        pieces = [shape(part.__geo_interface__).intersection(extent) for part in reader.shapes()
                  if box(*part.bbox).intersects(extent)]
        geometry = unary_union([part for part in pieces if not part.is_empty])
    return geometry, {'url': url, 'sha256': checksum, 'version': version,
                      'scale': f'1:{scale}', 'local_intersecting_features': len(pieces)}


def rank_combined(earth, planets):
    if len(earth) < 2 or len({c['id'] for c in earth}) != len(earth):
        raise ValueError('The combined generated catalog is insufficient or has duplicate IDs.')
    model = TerrainKNN(FEATURES).fit(earth)
    by_id = {c['id']: c for c in earth}
    references = {}
    from spatial_scale_experiment import sample_window, terrain_descriptors
    for target_id, target in TARGETS.items():
        raster = planets[target['body']]
        ref = terrain_descriptors(sample_window(raster, target, target['body'], WIDTH, SIZE), WIDTH / SIZE)
        explanation = model.explain(ref)
        references[target_id] = {'reference': {**target, 'features': ref,
                                               'source_sha256': raster.provenance['sha256']},
                                 'range_diagnostics': model.range_diagnostics(ref),
                                 'ranking': [{'rank': rank, 'id': identifier,
                                              'coordinate_key': by_id[identifier]['coordinate_key'],
                                              'latitude': by_id[identifier]['latitude'],
                                              'longitude': by_id[identifier]['longitude'],
                                              'region': by_id[identifier]['region'],
                                              'features': by_id[identifier]['features'],
                                              'quality': by_id[identifier]['quality'],
                                              'distance': distance,
                                              'distance_explanation': explanation[identifier]}
                                             for rank, (identifier, distance) in enumerate(model.query(ref), 1)]}
    return {'model': model.metadata(), 'references': references,
            'candidate_count': len(earth), 'candidates': earth,
            'caution': 'A joint ranking is relative to this generated catalog and its own Earth IQR; it cannot be compared numerically with other catalogs or establish analog validity.'}


def write_json(path, content):
    path.write_text(json.dumps(content, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')


def run():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    original = json.loads((FIRST_OUTPUT / 'catalog.json').read_text(encoding='utf-8'))
    robust = json.loads((ROBUST_OUTPUT / 'repeat-220-11-10m.json').read_text(encoding='utf-8'))
    if original['evaluated_count'] != robust['evaluated_count'] or len(robust['catalog']) != 49:
        raise ValueError('The original West Africa candidate set must be validated before combining regions.')
    planets = {body: planetary_raster(body) for body in ('moon', 'mars')}
    documents = []
    mask_comparisons = {}
    for region in REGIONS:
        raster, source = regional_raster(region)
        centers = regional_centers(region)
        config = {'id': region['id'], 'kind': 'regional_expansion', 'rows': 7, 'columns': 7,
                  'shift': False, 'width_m': WIDTH, 'grid_size': SIZE, 'mask_scale': '10m',
                  'tile': region['tile'], 'selection_reason': region['selection_reason']}
        masks = {scale: {name: regional_mask(name, region, scale) for name in MASKS}
                 for scale in ('50m', '10m')}
        trial = run_config(config, raster, masks['10m'], planets, source, centers)
        coarse = run_config({**config, 'id': config['id'] + '-mask-control', 'mask_scale': '50m'},
                            raster, masks['50m'], planets, source, centers)
        a = {c['id']: c['status'] for c in coarse['catalog']}
        changes = [{'id': c['id'], 'latitude': c['latitude'], 'longitude': c['longitude'],
                    'fifty_m_status': a[c['id']], 'ten_m_status': c['status']}
                   for c in trial['catalog'] if a[c['id']] != c['status']]
        mask_comparisons[region['id']] = {'changed_count': len(changes), 'changed_centers': changes,
                                          'fifty_m_exclusion_reasons': coarse['exclusion_reasons'],
                                          'ten_m_exclusion_reasons': trial['exclusion_reasons'],
                                          'fifty_m_winners': {key: value['ranking'][0]['coordinate_key'] for key, value in coarse['references'].items()},
                                          'ten_m_winners': {key: value['ranking'][0]['coordinate_key'] for key, value in trial['references'].items()}}
        write_json(OUTPUT / (region['id'] + '.json'), trial)
        documents.append(trial)
    generated_earth = [c for c in robust['catalog'] if c['status'] == 'eligible_land_topography']
    for document in documents:
        generated_earth.extend(c for c in document['catalog'] if c['status'] == 'eligible_land_topography')
    combined = rank_combined(generated_earth, planets)
    combined['source_provenance'] = {'west_africa': robust['source'],
                                     **{doc['configuration']['id']: doc['source'] for doc in documents}}
    combined['mask_provenance'] = {'west_africa': robust['masks'],
                                   **{doc['configuration']['id']: doc['masks'] for doc in documents}}
    combined['original_catalog_sha256'] = sha256((FIRST_OUTPUT / 'catalog.json').read_bytes())
    combined['original_rankings_sha256'] = sha256((FIRST_OUTPUT / 'rankings.json').read_bytes())
    write_json(OUTPUT / 'combined.json', combined)
    summary = {'version': 'terrestrial-discovery-expansion-v1',
               'implementation_sha256': sha256(Path(__file__).read_bytes()),
               'region_selection': [{**region, 'generated_center_count': 49} for region in REGIONS],
               'regions': [{ 'id': d['configuration']['id'], 'generated': d['generated_count'],
                             'evaluated': d['evaluated_count'], 'excluded': d['excluded_count'],
                             'exclusion_reasons': d['exclusion_reasons'], 'source': d['source']}
                           for d in documents],
               'mask_scale_comparison': mask_comparisons,
               'combined_count': combined['candidate_count'],
               'combined_winners': {target: {'id': item['ranking'][0]['id'],
                                             'latitude': item['ranking'][0]['latitude'],
                                             'longitude': item['ranking'][0]['longitude'],
                                             'region': item['ranking'][0]['region'],
                                             'outside_features': item['range_diagnostics']['outside_features']}
                                    for target, item in combined['references'].items()},
               'scope': 'Three selected bounded regional tiles, with generated centers; not a global scan.'}
    write_json(OUTPUT / 'summary.json', summary)
    return summary


if __name__ == '__main__':
    result = run()
    for item in result['regions']:
        print(item['id'], item['generated'], item['evaluated'], item['excluded'], item['source']['sha256'])
    print('Combined catalog:', result['combined_count'])
    for target, winner in result['combined_winners'].items():
        print(target, winner)
