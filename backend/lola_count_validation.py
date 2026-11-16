"""Offline, non-production validation of the paired LOLA LDEC_4 and LDEM_4 grids."""
from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
from decimal import Decimal
from pathlib import Path

import numpy as np
import rasterio

from independent_window_validation import local_positions


DATA = Path(__file__).parent / 'data'
BASE = 'https://imbrium.mit.edu/DATA/LOLA_GDR/CYLINDRICAL/IMG/'
PRODUCTS = {
    'LDEM_4': {'label_sha256': 'b5a197b4d417e3b5e0e84f8fe15f9a1d2203b8eb5d7213236c0ffbc86e940cc6',
               'image_sha256': '972d66d7f330abca62abc21aae270661516c00dd1a881ec102b94df9563656b5'},
    'LDEC_4': {'label_sha256': 'ab220f2b95482f9d4a6e94a8714897e822492fe731aedaa1b275ba758869da13',
               'image_sha256': '10ccc1253a7adab1ecb651d26b00ef6cbfa41107fd40f8998b5ab9fa5f9ee943'},
}
WINDOWS = {
    'moon-tycho': (-43.31, -11.36),
    'moon-tranquillitatis': (0.674, 23.473),
}
CONFIGURATIONS = {
    'baseline-220km-11': (220000, 11),
    'density-220km-7': (220000, 7),
    'density-220km-5': (220000, 5),
    'extent-180km-9': (180000, 9),
    'extent-260km-13': (260000, 13),
}
REGISTRATION_FIELDS = (
    'DATA_SET_ID', 'PRODUCT_VERSION_ID', 'START_TIME', 'STOP_TIME',
    'PRODUCT_CREATION_TIME', 'PRODUCER_ID', 'INSTRUMENT_ID', 'TARGET_NAME',
    'LINES', 'LINE_SAMPLES', 'SAMPLE_TYPE', 'SAMPLE_BITS',
    'MAP_PROJECTION_TYPE', 'MAP_RESOLUTION', 'A_AXIS_RADIUS', 'B_AXIS_RADIUS',
    'C_AXIS_RADIUS', 'POSITIVE_LONGITUDE_DIRECTION', 'CENTER_LATITUDE',
    'CENTER_LONGITUDE', 'MAXIMUM_LATITUDE', 'MINIMUM_LATITUDE',
    'WESTERNMOST_LONGITUDE', 'EASTERNMOST_LONGITUDE',
    'LINE_PROJECTION_OFFSET', 'SAMPLE_PROJECTION_OFFSET',
    'COORDINATE_SYSTEM_TYPE', 'COORDINATE_SYSTEM_NAME',
)
NUMERIC_FIELDS = {
    'LINES', 'LINE_SAMPLES', 'SAMPLE_BITS', 'MAP_RESOLUTION',
    'A_AXIS_RADIUS', 'B_AXIS_RADIUS', 'C_AXIS_RADIUS', 'CENTER_LATITUDE',
    'CENTER_LONGITUDE', 'MAXIMUM_LATITUDE', 'MINIMUM_LATITUDE',
    'WESTERNMOST_LONGITUDE', 'EASTERNMOST_LONGITUDE',
    'LINE_PROJECTION_OFFSET', 'SAMPLE_PROJECTION_OFFSET',
}


def label_field(label, key):
    match = re.search(r'^\s*' + re.escape(key) + r'\s*=\s*([^\r\n]+)', label, re.M)
    if match is None:
        raise ValueError(f'Missing PDS field: {key}')
    return match.group(1).strip().split(' <')[0].strip('"')


def checked_source(product, extension):
    url = BASE + product + '.' + extension
    cache_key = hashlib.sha256(url.encode('ascii')).hexdigest()
    path = DATA / (cache_key + ('.lbl' if extension == 'LBL' else '.img'))
    manifest_path = DATA / (cache_key + '.meta.json')
    if not path.exists() or not manifest_path.exists():
        raise FileNotFoundError(f'Acquire the official product before validation: {url}')
    raw = path.read_bytes()
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    digest = hashlib.sha256(raw).hexdigest()
    expected = PRODUCTS[product]['label_sha256' if extension == 'LBL' else 'image_sha256']
    if manifest['url'] != url or manifest['sha256'] != digest or expected != digest:
        raise ValueError(f'The cached {product}.{extension} does not match its verified source identity.')
    return raw, {'url': url, 'sha256': digest, 'bytes': len(raw)}


def validate_registration(elevation_label, count_label):
    """Require exact angular registration, not equality of rounded GDAL affines."""
    for key in REGISTRATION_FIELDS:
        elevation = label_field(elevation_label, key)
        count = label_field(count_label, key)
        if (Decimal(elevation) != Decimal(count) if key in NUMERIC_FIELDS else elevation != count):
            raise ValueError(f'LOLA count/elevation labels differ in {key}.')
    if (label_field(count_label, 'PRODUCT_ID') != 'LDEC_4' or
            label_field(elevation_label, 'PRODUCT_ID') != 'LDEM_4' or
            label_field(count_label, 'NAME') != 'COUNTS' or
            label_field(count_label, 'PRODUCT_VERSION_ID') != 'V3.0' or
            label_field(count_label, 'MAP_RESOLUTION') != '4' or
            label_field(count_label, 'COORDINATE_SYSTEM_NAME') != 'MEAN EARTH/POLAR AXIS OF DE421'):
        raise ValueError('Unexpected LOLA product or angular registration.')
    # MAP_SCALE uses m/pixel in LDEM_4 and km/pixel in LDEC_4.
    if not re.search(r'^\s*MAP_SCALE\s*=\s*[\d.]+\s*<m/pix>', elevation_label, re.M) or not re.search(
            r'^\s*MAP_SCALE\s*=\s*[\d.]+\s*<km/pix>', count_label, re.M):
        raise ValueError('LOLA MAP_SCALE units do not match the expected product labels.')
    elevation_scale_m = Decimal(label_field(elevation_label, 'MAP_SCALE'))
    count_scale_m = Decimal(label_field(count_label, 'MAP_SCALE')) * 1000
    # The difference accumulated over half a 1,440-column map must remain
    # smaller than half a source pixel; this is a geometric registration check.
    if abs(elevation_scale_m-count_scale_m)*Decimal(720) >= elevation_scale_m/2:
        raise ValueError('LOLA map-scale metadata imply a potential pixel-center shift.')
    return {'matching_fields': list(REGISTRATION_FIELDS),
            'elevation_map_scale_m': float(elevation_scale_m),
            'count_map_scale_m': float(count_scale_m),
            'map_scale_difference_m_per_pixel': float(elevation_scale_m - count_scale_m)}


def pixel_center(row, col):
    if not 0 <= row < 720 or not 0 <= col < 1440:
        raise ValueError('LOLA pixel index outside the global grid.')
    return 90 - (row + .5) / 4, (col + .5) / 4


def nearest_pixel(latitude, longitude):
    if not -90 < latitude < 90 or not math.isfinite(longitude):
        raise ValueError('LOLA latitude/longitude outside pixel-center coverage.')
    return int(math.floor((90 - latitude) * 4)), int(math.floor((longitude % 360) * 4))


def bilinear_support(latitude, longitude, *, rows=720, cols=1440):
    """Return contributing source bins; counts are never bilinearly averaged."""
    y = (89.875 - float(latitude)) * 4
    x = ((float(longitude) % 360) - .125) * 4 % cols
    if not (math.isfinite(y) and math.isfinite(x)) or y < 0 or y > rows - 1:
        raise ValueError('Sample outside LOLA pixel-center latitude coverage.')
    i = min(math.floor(y), rows - 2)
    j = math.floor(x)
    fy, fx = y - i, x - j
    return {(i + dy, (j + dx) % cols) for dy, wy in ((0, 1-fy), (1, fy))
            for dx, wx in ((0, 1-fx), (1, fx)) if wy * wx > 1e-12}


def count_summary(bins, counts):
    if not bins:
        raise ValueError('No source bins support this sample.')
    ordered = sorted(bins)
    values = np.array([counts[row, col] for row, col in ordered], dtype=int)
    if np.any(values < 0):
        raise ValueError('Negative or NoData observation count needs separate interpretation.')
    minimum = ordered[int(np.argmin(values))]
    maximum = ordered[int(np.argmax(values))]
    return {'source_bins': len(ordered), 'zero_count_bins': int(np.count_nonzero(values == 0)),
            'minimum': int(values.min()), 'p5': float(np.percentile(values, 5)),
            'p25': float(np.percentile(values, 25)), 'median': float(np.median(values)),
            'p75': float(np.percentile(values, 75)), 'p95': float(np.percentile(values, 95)),
            'maximum': int(values.max()),
            'minimum_bin': {'row': minimum[0], 'column': minimum[1],
                            'latitude': pixel_center(*minimum)[0], 'longitude': pixel_center(*minimum)[1]},
            'maximum_bin': {'row': maximum[0], 'column': maximum[1],
                            'latitude': pixel_center(*maximum)[0], 'longitude': pixel_center(*maximum)[1]}}


def assert_pixel_agreement(raw_array, independent_array):
    if raw_array.shape != independent_array.shape or not np.array_equal(raw_array, independent_array):
        raise ValueError('Independent PDS decoding or raster orientation disagrees with raw pixels.')


def window_support(counts, latitude, longitude, width, size, cells):
    latitudes, longitudes = local_positions(latitude, longitude, 1737400.0, width, size)
    all_bins, cell_bins = set(), {}
    south_queries = 0
    for row in range(size):
        for col in range(size):
            bins = set()
            for index in range(25):
                lat = float(latitudes[index, row, col])
                lon = float(longitudes[index, row, col])
                south_queries += lat < -45
                bins.update(bilinear_support(lat, lon))
            cell_bins[row, col] = bins
            all_bins.update(bins)
    summaries = {}
    for kind, cell in cells.items():
        row, col = cell['row'], cell['column']
        if not (0 <= row < size and 0 <= col < size):
            raise ValueError('Saved influential cell falls outside the reconstructed grid.')
        center_lat, center_lon = float(latitudes[12, row, col]), float(longitudes[12, row, col])
        longitude_difference = (center_lon - cell['longitude'] + 180) % 360 - 180
        if abs(center_lat-cell['latitude']) > 1e-10 or abs(longitude_difference) > 1e-10:
            raise ValueError('Saved influential cell is not at the reconstructed coordinates.')
        affected = {(row, col)}
        if kind == 'steepest_interior_cell':
            if not 0 < row < size-1 or not 0 < col < size-1:
                raise ValueError('The steepest-cell gradient requires four interior neighbors.')
            affected = {(row-1, col), (row+1, col), (row, col-1), (row, col+1)}
        contributing = set().union(*(cell_bins[position] for position in affected))
        summaries[kind] = {'cell': cell, 'contributing_output_cells': [list(p) for p in sorted(affected)],
                           'count_support': count_summary(contributing, counts)}
    south = {pixel for pixel in all_bins if pixel_center(*pixel)[0] < -45}
    north = all_bins - south
    north_edge = {pixel for pixel in all_bins if pixel[0] == 539}
    south_edge = {pixel for pixel in all_bins if pixel[0] == 540}
    paired_columns = sorted({col for _, col in north_edge} & {col for _, col in south_edge})
    paired_differences = np.array([int(counts[540, col])-int(counts[539, col])
                                    for col in paired_columns], dtype=int)
    return {'queries': int(25*size*size), 'queries_south_of_45_s': int(south_queries),
            'unique_source_bins': count_summary(all_bins, counts),
            'source_bins_south_of_45_s': count_summary(south, counts) if south else None,
            'source_bins_north_of_45_s': count_summary(north, counts) if north else None,
            'source_bins_at_45_s_north_row': count_summary(north_edge, counts) if north_edge else None,
            'source_bins_at_45_s_south_row': count_summary(south_edge, counts) if south_edge else None,
            'paired_45_s_row_counts': {
                'columns': len(paired_columns),
                'median_signed_south_minus_north': float(np.median(paired_differences)),
                'median_absolute_difference': float(np.median(np.abs(paired_differences))),
                'maximum_absolute_difference': int(np.max(np.abs(paired_differences)))
            } if paired_columns else None,
            'output_cell_minimum_counts': [
                [min(int(counts[pixel]) for pixel in cell_bins[row, col]) for col in range(size)]
                for row in range(size)],
            'influential_cells': summaries}


def run_validation():
    """Read immutable cached source bytes; write only an ignored validation report."""
    sources = {}; labels = {}; arrays = {}; gdal = {}
    validation_dir = DATA / 'validation-pds'
    validation_dir.mkdir(exist_ok=True)
    for product in PRODUCTS:
        label_raw, label_meta = checked_source(product, 'LBL')
        image_raw, image_meta = checked_source(product, 'IMG')
        label = label_raw.decode('ascii')
        rows = int(label_field(label, 'LINES'))
        cols = int(label_field(label, 'LINE_SAMPLES'))
        if (rows, cols) != (720, 1440) or len(image_raw) != rows*cols*2 or (
                label_field(label, 'SAMPLE_BITS') != '16' or
                label_field(label, 'SAMPLE_TYPE') != 'LSB_INTEGER'):
            raise ValueError(f'Unsupported LOLA source format: {product}.')
        raw_array = np.frombuffer(image_raw, dtype='<i2').reshape(rows, cols)
        for extension, raw in (('LBL', label_raw), ('IMG', image_raw)):
            target = validation_dir / (product + '.' + extension)
            if not target.exists() or target.read_bytes() != raw:
                target.write_bytes(raw)
        with rasterio.open(validation_dir / (product + '.LBL')) as dataset:
            independent = dataset.read(1)
            if dataset.driver != 'PDS':
                raise ValueError(f'The independent decoder did not open {product} as PDS.')
            try:
                assert_pixel_agreement(raw_array, independent)
            except ValueError as exc:
                raise ValueError(f'NumPy and GDAL disagree on {product} pixels.') from exc
            gdal[product] = {'driver': dataset.driver, 'shape': list(independent.shape),
                             'transform': list(tuple(dataset.transform)[:6]),
                             'crs': dataset.crs.to_wkt() if dataset.crs else None,
                             'nodata': dataset.nodata,
                             'nodata_count': int(np.count_nonzero(independent == dataset.nodata)) if dataset.nodata is not None else None,
                             'scale': float(dataset.scales[0]), 'offset': float(dataset.offsets[0])}
        sources[product] = {'label': label_meta, 'image': image_meta}
        labels[product] = label
        arrays[product] = raw_array
    registration = validate_registration(labels['LDEM_4'], labels['LDEC_4'])
    elevation = arrays['LDEM_4']; counts = arrays['LDEC_4']
    if np.any(counts < 0) or np.any(elevation == -32768) or np.any(counts == -32768):
        raise ValueError('Unexpected negative counts or source NoData requires a separate mask.')
    if counts.min() != int(label_field(labels['LDEC_4'], 'MINIMUM')) or counts.max() != int(label_field(labels['LDEC_4'], 'MAXIMUM')):
        raise ValueError('Decoded count extrema disagree with the PDS label.')
    controls = {}
    for name, lat, lon in (('tycho_center', -43.31, -11.36),
                           ('tranquillitatis_center', .674, 23.473),
                           ('south_strip_edge', -45.125, 348.875),
                           ('north_strip_edge', -44.875, 348.875),
                           ('west_seam', 0.125, 359.875),
                           ('east_seam', 0.125, .125)):
        row, col = nearest_pixel(lat, lon)
        center_lat, center_lon = pixel_center(row, col)
        controls[name] = {'requested_latitude': lat, 'requested_longitude': lon,
                          'north_up_row': row, 'column': col,
                          'pixel_center_latitude': center_lat,
                          'pixel_center_longitude': center_lon,
                          'height_m': float(elevation[row, col])*.5,
                          'observations': int(counts[row, col])}
    previous = json.loads((DATA/'independent-window-report.json').read_text(encoding='utf-8'))
    if previous['sources']['moon'] != sources['LDEM_4']['image']['sha256']:
        raise ValueError('The prior window report used a different LDEM_4 elevation file.')
    windows = {}
    for name, (width, size) in CONFIGURATIONS.items():
        windows[name] = {}
        for target, (lat, lon) in WINDOWS.items():
            influence = previous['comparisons'][name+'/'+target]['supporting_grid_cells']
            cells = {key: value.get('nearest_cell', value) for key, value in influence.items()}
            windows[name][target] = window_support(counts, lat, lon, width, size, cells)
    report = {'version': 'lola-count-validation-v1', 'sources': sources,
              'registration': registration, 'gdal': gdal,
              'projected_affine_origin_difference_m': {
                  'x': gdal['LDEC_4']['transform'][2] - gdal['LDEM_4']['transform'][2],
                  'y': gdal['LDEC_4']['transform'][5] - gdal['LDEM_4']['transform'][5]},
              'whole_count_grid': {'shape': [720, 1440],
                                   'minimum': int(counts.min()), 'maximum': int(counts.max()),
                                   'zero_count_bins': int(np.count_nonzero(counts == 0))},
              'controls': controls, 'windows': windows,
              'interpretation': 'Count support per source bin only; no elevation accuracy or effective resolution is inferred.'}
    output = DATA / 'lola-count-validation-report.json'
    output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    return report


if __name__ == '__main__':
    result = run_validation()
    print('LOLA count/elevation pair:', result['sources']['LDEC_4']['image']['sha256'])
    for configuration, targets in result['windows'].items():
        for target, outcome in targets.items():
            distribution = outcome['unique_source_bins']
            print(configuration, target, distribution['source_bins'],
                  distribution['zero_count_bins'], distribution['minimum'],
                  distribution['median'], distribution['maximum'])
