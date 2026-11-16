"""Optional GDAL/Rasterio cross-check of the exact cached planetary IMG bytes."""
from __future__ import annotations

import hashlib
import json
import math
import shutil

import numpy as np

from science import TARGETS
from sources import DATA, MARS_BASE, MOON_BASE, planetary_raster


PRODUCTS = {
    'moon': {'base': MOON_BASE, 'name': 'LDEM_4', 'label_extension': '.LBL',
             'image_extension': '.IMG', 'radius_m': 1737400.0, 'height_scale': 0.5,
             'gdal_options': {}},
    'mars': {'base': MARS_BASE, 'name': 'megt90n000cb', 'label_extension': '.lbl',
             'image_extension': '.img', 'radius_m': 3396000.0, 'height_scale': 1.0,
             'gdal_options': {'PDS_SampleProjOffset_Shift': '-0.5',
                              'PDS_LineProjOffset_Shift': '-0.5'}},
}


def prepare_pds_files(product):
    """Place checksum-identical cached bytes under names required by detached labels."""
    directory = DATA / 'validation-pds'
    directory.mkdir(exist_ok=True)
    for extension, cache_extension in ((product['label_extension'], '.lbl'),
                                       (product['image_extension'], '.img')):
        url = product['base'] + product['name'] + extension
        cache_key = hashlib.sha256(url.encode()).hexdigest()
        source = DATA / (cache_key + cache_extension)
        manifest = DATA / (cache_key + '.meta.json')
        if not source.exists() or not manifest.exists():
            raise FileNotFoundError(f'Official PDS source is absent from the cache: {url}')
        expected = json.loads(manifest.read_text(encoding='utf-8'))['sha256']
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError('PDS source checksum does not match its acquisition manifest.')
        target = directory / (product['name'] + extension)
        if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            shutil.copyfile(source, target)
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise ValueError('Detached-label validation copy differs from cached source bytes.')
    return directory / (product['name'] + product['label_extension'])


def verify():
    """Compare GDAL raw pixels, map registration and bilinear GDAL samples."""
    import rasterio
    from affine import Affine
    from rasterio.warp import Resampling, reproject

    result = {'decoder': f'Rasterio {rasterio.__version__} / GDAL {rasterio.__gdal_version__}',
              'products': {}, 'controls': {}}
    for body, product in PRODUCTS.items():
        label = prepare_pds_files(product)
        existing = planetary_raster(body)
        with rasterio.Env(**product['gdal_options']):
            with rasterio.open(label) as dataset:
                source = dataset.read(1)
                if dataset.driver != 'PDS' or source.shape != (720, 1440):
                    raise ValueError('The independent PDS decoder returned unexpected dimensions.')
                if np.count_nonzero(source == dataset.nodata):
                    raise ValueError('The independent PDS decoder found NoData in the current IMG.')
                # Direct compare of every pixel after the explicitly documented
                # vertical scaling. The LOLA label's radius offset is excluded
                # because the application's quantity is height, not radius.
                maximum_pixel_difference = float(np.max(np.abs(source[::-1].astype(float) * product['height_scale'] - existing.z)))
                if maximum_pixel_difference != 0:
                    raise AssertionError('GDAL and the production decoder disagree on source pixels.')
                result['products'][body] = {
                    'product_id': product['name'], 'source_label': str(label),
                    'driver': dataset.driver, 'dimensions': [dataset.height, dataset.width],
                    'gdal_options': product['gdal_options'], 'crs': dataset.crs.to_wkt() if dataset.crs else None,
                    'transform': tuple(dataset.transform)[:6], 'bounds_m': list(dataset.bounds),
                    'nodata': dataset.nodata, 'nodata_pixel_count': int(np.count_nonzero(source == dataset.nodata)),
                    'raw_scale': dataset.scales[0], 'raw_offset': dataset.offsets[0],
                    'maximum_source_pixel_difference_m': maximum_pixel_difference,
                    'image_sha256': existing.provenance['sha256']}
                for target_id, target in TARGETS.items():
                    if target['body'] != body:
                        continue
                    radius = product['radius_m']
                    x = radius * math.radians((target['longitude'] % 360) - 180)
                    y = radius * math.radians(target['latitude'])
                    row, column = dataset.index(x, y)
                    pixel_x, pixel_y = rasterio.transform.xy(dataset.transform, row, column)
                    position = {'latitude': math.degrees(pixel_y / radius),
                                'longitude_east_0_360': (180 + math.degrees(pixel_x / radius)) % 360}
                    raw_value = int(source[row, column])
                    current_value = float(existing.z[719 - row, column])
                    gd_height = raw_value * product['height_scale']
                    bilinear_raw = np.zeros((1, 1), dtype=np.float64)
                    reproject(rasterio.band(dataset, 1), bilinear_raw,
                              src_transform=dataset.transform, src_crs=dataset.crs,
                              dst_transform=Affine(1, 0, x - 0.5, 0, -1, y + 0.5),
                              dst_crs=dataset.crs, resampling=Resampling.bilinear)
                    independent_sample = float(bilinear_raw[0, 0] * product['height_scale'])
                    current_sample = float(existing.sample(target['latitude'], target['longitude']))
                    result['controls'][target_id] = {
                        'requested_latitude': target['latitude'],
                        'requested_longitude': target['longitude'],
                        'north_up_row': row, 'column': column,
                        'gdal_pixel_center': position,
                        'raw_digital_number': raw_value,
                        'gdal_pixel_height_m': gd_height,
                        'production_pixel_height_m': current_value,
                        'pixel_value_difference_m': current_value - gd_height,
                        'gdal_bilinear_height_m': independent_sample,
                        'production_bilinear_height_m': current_sample,
                        'bilinear_difference_m': current_sample - independent_sample}
    (DATA / 'independent-decoder-report.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    report = verify()
    for name, control in report['controls'].items():
        print(name, control['north_up_row'], control['column'],
              control['pixel_value_difference_m'], control['bilinear_difference_m'])
