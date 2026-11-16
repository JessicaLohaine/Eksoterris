"""Bounded, source-traceable characterization of selected discovery windows."""
from __future__ import annotations

import hashlib
import json
import re
import ssl
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import rasterio
import truststore
from rasterio.features import geometry_mask
from rasterio.windows import Window, from_bounds
from shapely.geometry import box, shape

from discovery_robustness import footprint
from discovery_expansion import OUTPUT as EXPANSION, WIDTH, write_json
from discovery_characterization import OUTPUT as SHIFTED
from sources import DATA, earth_climate, fetch

OUTPUT = Path(__file__).parent.parent / 'results' / 'regional-characterization-v1'
RAW = DATA / 'regional-characterization-v1'
JRC_BASE = ('https://s3.waw4-1.cloudferro.com/swift/v1/global-surface-water/'
            'download2024/Aggregated/VER1-5/occurrence/')
JRC_TILES = {
    '70W_20S': ('occurrence_70W_20S_v1_5_2024.tif', (-70, -30, -60, -20)),
    '70W_10S': ('occurrence_70W_10S_v1_5_2024.tif', (-70, -20, -60, -10)),
    '30E_10N': ('occurrence_30E_10N_v1_5_2024.tif', (30, 0, 40, 10)),
}
STUDIES = {
    'tranquillitatis_shared': ('south-america-elevation-gradient-r02-c04',
                               'south-america-elevation-gradient-shift-r01-c04'),
    'jezero_original': ('south-america-elevation-gradient-r05-c06',),
    'jezero_shifted': ('south-america-elevation-gradient-shift-r03-c06',),
    'east_africa_water_control': ('east-africa-inland-water-gradient-r03-c03',),
}


def selected_centers():
    """Read saved experiment coordinates instead of entering new point estimates."""
    files = (EXPANSION / 'south-america-elevation-gradient.json',
             SHIFTED / 'south-america-elevation-gradient-shifted.json',
             EXPANSION / 'east-africa-inland-water-gradient.json')
    catalogs = [json.loads(file.read_text(encoding='utf-8'))['catalog'] for file in files]
    by_id = {candidate['id']: candidate for catalog in catalogs for candidate in catalog}
    ids = {identifier for group in STUDIES.values() for identifier in group}
    if not ids.issubset(by_id) or any(by_id[key]['status'] != 'eligible_land_topography' for key in ids):
        raise ValueError('Selected centers are absent or ineligible in the saved experiments.')
    return {key: by_id[key] for key in sorted(ids)}


def tile_keys(polygon):
    """Select only published JRC 10-degree files intersecting a study polygon."""
    return [key for key, (_, bounds) in JRC_TILES.items()
            if polygon.intersection(box(*bounds)).area > 0]


def validate_tile_registration(dataset, key):
    """Check source georeferencing rather than inferring tile bounds from its name."""
    expected = JRC_TILES[key][1]
    if (dataset.crs is None or dataset.crs.to_epsg() != 4326 or dataset.count != 1 or
            dataset.width != 40000 or dataset.height != 40000 or
            not np.allclose(tuple(dataset.bounds), expected, rtol=0, atol=1e-7) or
            not np.allclose(dataset.res, (0.00025, 0.00025), rtol=0, atol=1e-10)):
        raise ValueError('JRC raster registration disagrees with the expected tile footprint.')


def acquire_tile(key):
    """Keep exact source bytes and hash; never replace a cached tile implicitly."""
    if key not in JRC_TILES:
        raise ValueError('Tile is outside the fixed bounded study.')
    RAW.mkdir(parents=True, exist_ok=True)
    filename, _ = JRC_TILES[key]
    path = RAW / filename
    manifest = RAW / (filename + '.json')
    if path.exists() or manifest.exists():
        if not path.exists() or not manifest.exists():
            raise ValueError('Incomplete tile cache; inspect it manually.')
        meta = json.loads(manifest.read_text(encoding='utf-8'))
        if hashlib.sha256(path.read_bytes()).hexdigest() != meta['sha256']:
            raise ValueError('Tile cache checksum mismatch.')
        return path, meta
    url = JRC_BASE + filename
    context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    with urlopen(Request(url, headers={'User-Agent': 'Eksoterris/1.0'}), context=context, timeout=45) as response:
        if response.status != 200 or response.headers.get('Content-Type', '').startswith('text/'):
            raise RuntimeError('JRC source did not return a GeoTIFF.')
        length = int(response.headers.get('Content-Length', '0'))
        if not 0 < length <= 80_000_000:
            raise ValueError('JRC tile exceeds the bounded 80 MB file limit.')
        digest = hashlib.sha256()
        total = 0
        with path.open('xb') as target:
            while block := response.read(1024 * 1024):
                total += len(block)
                if total > 80_000_000:
                    raise ValueError('JRC tile exceeded the download limit.')
                digest.update(block)
                target.write(block)
        if total != length:
            raise ValueError('JRC download was incomplete; inspect the unmanifested tile.')
        meta = {'product': 'EC JRC Global Surface Water v1.5, occurrence, 1984-2024',
                'url': url, 'sha256': digest.hexdigest(), 'bytes': total,
                'etag': response.headers.get('ETag'),
                'retrieved_at': datetime.now(timezone.utc).isoformat(),
                'license': 'Copernicus free use with attribution; source EC JRC/Google'}
        manifest.write_text(json.dumps(meta, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return path, meta


def count_occurrence(dataset, polygon):
    """Count unresampled JRC codes inside the actual polygon, in bounded row chunks."""
    if dataset.crs is None or dataset.crs.to_epsg() != 4326 or dataset.count != 1:
        raise ValueError('Unexpected JRC coordinate system or band count.')
    west, south, east, north = polygon.bounds
    left, bottom, right, top = dataset.bounds
    if east <= left or west >= right or north <= bottom or south >= top:
        return {'pixels': 0, 'no_data': 0, 'no_water_detected': 0, 'water_detected': 0,
                'positive_occurrence_histogram': {}}
    window = from_bounds(max(west, left), max(south, bottom), min(east, right), min(north, top), dataset.transform)
    c0, r0 = max(0, int(np.floor(window.col_off))), max(0, int(np.floor(window.row_off)))
    c1 = min(dataset.width, int(np.ceil(window.col_off + window.width)))
    r1 = min(dataset.height, int(np.ceil(window.row_off + window.height)))
    totals = {'pixels': 0, 'no_data': 0, 'no_water_detected': 0, 'water_detected': 0}
    histogram = np.zeros(101, dtype=np.int64)
    for row in range(r0, r1, 512):
        chunk = Window(c0, row, c1 - c0, min(512, r1 - row))
        values = dataset.read(1, window=chunk)
        inside = geometry_mask([polygon.__geo_interface__], values.shape,
                               dataset.window_transform(chunk), invert=True)
        selected = values[inside]
        if np.any((selected > 100) & (selected != 255)):
            raise ValueError('Unexpected JRC occurrence code outside 0-100 and 255.')
        totals['pixels'] += selected.size
        totals['no_data'] += int(np.count_nonzero(selected == 255))
        totals['no_water_detected'] += int(np.count_nonzero(selected == 0))
        totals['water_detected'] += int(np.count_nonzero((selected >= 1) & (selected <= 100)))
        histogram += np.bincount(selected[selected <= 100], minlength=101)
    totals['positive_occurrence_histogram'] = {str(i): int(value) for i, value in enumerate(histogram)
                                               if i > 0 and value > 0}
    return totals


def nasadem_catalog():
    """Discover intersecting NASADEM products without accessing protected downloads."""
    entries, queries = {}, []
    for bounds in ('-69,-24,-63,-17', '33,0,37,3'):
        query = urlencode({'short_name': 'NASADEM_HGT', 'version': '001',
                           'bounding_box': bounds, 'page_size': 100})
        raw, meta = fetch('https://cmr.earthdata.nasa.gov/search/granules.json?' + query, 'json')
        found = json.loads(raw)['feed']['entry']
        if not found or len(found) >= 100:
            raise ValueError('NASADEM catalog query is missing or truncated.')
        queries.append({'bounding_box': bounds, 'source': meta})
        entries.update({entry['title']: entry for entry in found})
    return {'queries': queries, 'granules': [{'id': entry['title'],
                                       'size_mb_reported': entry.get('granule_size'),
                                       'download_urls': [link['href'] for link in entry.get('links', [])
                                                         if link.get('rel', '').endswith('/data#') and
                                                         link.get('href', '').startswith('https://data.lpdaac.earthdatacloud.nasa.gov/')]
                                      } for entry in sorted(entries.values(), key=lambda entry: entry['title'])],
            'status': 'metadata_only; source files require Earthdata Login'}


def nasadem_intersections(polygon, catalog):
    """Reconstruct published one-degree granule footprints from CMR titles."""
    matched = []
    for granule in catalog['granules']:
        parts = re.fullmatch(r'NASADEM_HGT_([ns])(\d{2})([ew])(\d{3})', granule['id'], re.I)
        if not parts:
            raise ValueError('Unexpected NASADEM granule geographic identifier.')
        south = int(parts[2]) * (1 if parts[1].lower() == 'n' else -1)
        west = int(parts[4]) * (1 if parts[3].lower() == 'e' else -1)
        if polygon.intersection(box(west, south, west + 1, south + 1)).area > 0:
            matched.append(granule['id'])
    return sorted(matched)


def landsat_inventory(footprints):
    """Inspect one bounded USGS STAC page; scene metadata is not imagery analysis."""
    bounds = (-68.1, -23.5, -63.4, -17.9)
    query = urlencode({'bbox': ','.join(map(str, bounds)),
                       'datetime': '2024-01-01T00:00:00Z/2024-12-31T23:59:59Z',
                       'limit': 50})
    raw, provenance = fetch('https://landsatlook.usgs.gov/stac-server/collections/landsat-c2l2-sr/items?' + query, 'json')
    data = json.loads(raw)
    result = {}
    for identifier, polygon in footprints.items():
        if not identifier.startswith('south-america-'):
            continue
        scenes = []
        for feature in data.get('features', []):
            intersection = polygon.intersection(shape(feature['geometry']))
            if intersection.area > 0:
                scenes.append({'id': feature['id'],
                               'datetime': feature['properties'].get('datetime'),
                               'scene_cloud_cover_percent': feature['properties'].get('eo:cloud_cover'),
                               'footprint_intersection_fraction_approx': float(intersection.area / polygon.area),
                               'qa_pixel_asset_available': 'qa_pixel' in feature.get('assets', {})})
        result[identifier] = scenes[:3]
    return {'product': 'USGS Landsat Collection 2 Level-2 Surface Reflectance',
            'source': provenance, 'page_items': len(data.get('features', [])),
            'more_pages': any(link.get('rel') == 'next' for link in data.get('links', [])),
            'scope': 'First 50 catalog items in 2024 over a combined bbox; scene cloud fraction is not local cloud quality.',
            'intersecting_scene_examples': result,
            'status': 'metadata_only; image bands and QA not acquired'}


def run():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    centers = selected_centers()
    footprints = {key: footprint(value, WIDTH) for key, value in centers.items()}
    catalog = nasadem_catalog()
    required = sorted({key for polygon in footprints.values() for key in tile_keys(polygon)})
    source_files = {key: acquire_tile(key) for key in required}
    try:
        landsat = landsat_inventory(footprints)
    except (RuntimeError, ValueError, OSError) as exc:
        landsat = {'status': 'metadata_unavailable', 'reason': str(exc)}
    evidence = {}
    for identifier, candidate in centers.items():
        polygon = footprints[identifier]
        tiles = []
        counts = {'pixels': 0, 'no_data': 0, 'no_water_detected': 0, 'water_detected': 0}
        histogram = np.zeros(101, dtype=np.int64)
        for key in tile_keys(polygon):
            path, meta = source_files[key]
            with rasterio.open(path) as dataset:
                validate_tile_registration(dataset, key)
                values = count_occurrence(dataset, polygon)
                tiles.append({'tile': key, 'source': meta, 'raster': {
                    'crs': str(dataset.crs), 'bounds': list(dataset.bounds),
                    'width': dataset.width, 'height': dataset.height,
                    'pixel_size_degrees': list(dataset.res), 'nodata': dataset.nodata},
                    'counts': values})
                for field in counts:
                    counts[field] += values[field]
                for code, amount in values['positive_occurrence_histogram'].items():
                    histogram[int(code)] += amount
        if counts['pixels'] == 0 or counts['pixels'] != sum(counts[f] for f in ('no_data','no_water_detected','water_detected')):
            raise ValueError('Water coverage tally is incomplete.')
        if sum(histogram) != counts['water_detected']:
            raise ValueError('Positive water occurrence histogram is inconsistent.')
        climate = earth_climate(candidate['latitude'], candidate['longitude'])
        evidence[identifier] = {'latitude': candidate['latitude'], 'longitude': candidate['longitude'],
                                'status': 'regional_evidence_only', 'footprint_geojson': polygon.__geo_interface__,
                                'nasadem_intersecting_catalog_granules': nasadem_intersections(polygon, catalog),
                                'water_occurrence': {'counts': counts, 'source_tiles': tiles,
                                    'positive_occurrence_histogram': {str(i): int(v) for i, v in enumerate(histogram) if i > 0 and v > 0},
                                    'meaning': 'Historical detected surface water, not current surface dryness or a land-fraction estimate.'},
                                'climate_center_point': climate,
                                'limitations': ['NASA POWER is a coarse center-point climatology, not a footprint-wide measurement.',
                                                'JRC no-data pixels are unknown, and code zero means no water detected rather than proof of dry ground.',
                                                'No independent ice or geology layer is included.']}
    output = {'version': 'regional-characterization-v1', 'study_groups': STUDIES,
              'nasadem_catalog': catalog,
              'landsat_catalog': landsat,
              'dataset_status': {'jrc_gsw_v1_5': 'acquired_and_processed',
                                 'nasa_power': 'acquired_and_processed',
                                 'nasadem_hgt_v001': 'CMR coverage confirmed; authenticated source download not available',
                                 'geology': 'not_acquired', 'independent_ice': 'not_acquired'},
              'evidence': evidence,
              'caution': 'These data provide regional context only; no planetary analog or NASADEM elevation comparison is established.'}
    write_json(OUTPUT / 'evidence.json', output)
    write_json(OUTPUT / 'comparisons.json', comparisons(output))
    return output


def comparisons(evidence):
    """Keep Earth-only observations separate from cross-body analog claims."""
    previous = json.loads((EXPANSION / 'combined.json').read_text(encoding='utf-8'))
    shifted = json.loads((SHIFTED / 'combined-shifted.json').read_text(encoding='utf-8'))
    output = {}
    for target, groups in {'moon-tranquillitatis': ('tranquillitatis_shared',),
                           'mars-jezero': ('jezero_original', 'jezero_shifted'),
                           'moon-tycho': (), 'mars-gale': ()}.items():
        records = {}
        for name in groups:
            records[name] = []
            for identifier in STUDIES[name]:
                source = shifted if '-shift-' in identifier else previous
                analysis = source['references'][target]
                row = next(item for item in analysis['ranking'] if item['id'] == identifier)
                records[name].append({'evidence_id': identifier, 'ranking_catalog':
                                      'shifted_69' if source is shifted else 'original_64',
                                      'rank_in_separate_catalog': row['rank'],
                                      'distance_in_separate_calibration': row['distance'],
                                      'terrain_features': row['features'],
                                      'reference_features': analysis['reference']['features'],
                                      'reference_outside_earth_ranges': analysis['range_diagnostics']['outside_features']})
        output[target] = {'selected_study_groups': records,
                          'supported_similarity_claims_beyond_topography': [],
                          'supported_differences': [],
                          'earth_context_evidence_ids': [identifier for group in groups for identifier in STUDIES[group]],
                          'unknown_or_unverified': ['Independent NASADEM elevation is unavailable without Earthdata authentication.',
                                                    'Ice, lithology, mineralogy, surface process and comparable planetary environmental evidence were not measured.'],
                          'research_relevance': ('Review hydrology and land-cover at each whole window before proposing a material or operational study.'
                                                 if groups else 'No terrestrial study region endorsed: topographic extrapolation and shifted-center instability remain.'),
                          'analog_validation': 'not_established'}
    return {'version': 'regional-characterization-v1', 'references': output,
            'evidence_file': 'evidence.json',
            'interpretation': 'Earth context does not provide an independently measured Earth-Moon or Earth-Mars similarity. Original and shifted distances have different Earth IQR calibration.'}


if __name__ == '__main__':
    result = run()
    for identifier, record in result['evidence'].items():
        print(identifier, record['water_occurrence']['counts'], record['climate_center_point']['annual'])
