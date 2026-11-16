"""Independent synthetic checks for bounded regional evidence processing."""
import unittest
import json
from types import SimpleNamespace

import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from shapely.geometry import box

from region_characterization import (OUTPUT, RAW, JRC_TILES, count_occurrence,
                                     nasadem_intersections, selected_centers, tile_keys,
                                     validate_tile_registration)


class RegionalCharacterizationTest(unittest.TestCase):
    def test_saved_study_centers_and_tile_seam(self):
        centers = selected_centers()
        self.assertEqual(len(centers), 5)
        self.assertTrue(all(item['status'] == 'eligible_land_topography' for item in centers.values()))
        self.assertEqual(tile_keys(box(-66, -21, -64, -19)), ['70W_20S', '70W_10S'])
        self.assertEqual(tile_keys(box(34, 0.1, 36, 2)), ['30E_10N'])
        self.assertEqual(tile_keys(box(10, 10, 12, 12)), [])

    def test_occurrence_codes_and_polygon_rasterization(self):
        values = np.array([[0, 1, 255, 100], [0, 0, 2, 255],
                           [100, 255, 0, 0], [255, 255, 0, 1]], dtype='uint8')
        with MemoryFile() as memory:
            with memory.open(driver='GTiff', width=4, height=4, count=1, dtype='uint8',
                             crs='EPSG:4326', transform=from_origin(0, 4, 1, 1), nodata=255) as ds:
                ds.write(values, 1)
                self.assertEqual(count_occurrence(ds, box(0, 2, 2, 4)),
                                 {'pixels': 4, 'no_data': 0, 'no_water_detected': 3, 'water_detected': 1,
                                  'positive_occurrence_histogram': {'1': 1}})
                self.assertEqual(count_occurrence(ds, box(2, 2, 4, 4)),
                                 {'pixels': 4, 'no_data': 2, 'no_water_detected': 0, 'water_detected': 2,
                                  'positive_occurrence_histogram': {'2': 1, '100': 1}})
                self.assertEqual(count_occurrence(ds, box(8, 8, 9, 9))['pixels'], 0)

    def test_unexpected_code_rejected(self):
        with MemoryFile() as memory:
            with memory.open(driver='GTiff', width=2, height=2, count=1, dtype='uint8',
                             crs='EPSG:4326', transform=from_origin(0, 2, 1, 1), nodata=255) as ds:
                ds.write(np.array([[0, 101], [255, 1]], dtype='uint8'), 1)
                with self.assertRaisesRegex(ValueError, 'Unexpected JRC occurrence code'):
                    count_occurrence(ds, box(0, 0, 2, 2))

    def test_registration_rejects_misnamed_or_shifted_raster(self):
        good = SimpleNamespace(crs=rasterio.crs.CRS.from_epsg(4326), count=1,
                               width=40000, height=40000,
                               bounds=(-70, -30, -60, -20), res=(0.00025, 0.00025))
        validate_tile_registration(good, '70W_20S')
        shifted = SimpleNamespace(**{**vars(good), 'bounds': (-70, -40, -60, -30)})
        with self.assertRaisesRegex(ValueError, 'registration disagrees'):
            validate_tile_registration(shifted, '70W_20S')

    def test_nasadem_tile_intersection_is_derived_from_published_origin(self):
        catalog = {'granules': [{'id': 'NASADEM_HGT_s23w067'},
                                {'id': 'NASADEM_HGT_s24w068'},
                                {'id': 'NASADEM_HGT_s19w065'}]}
        self.assertEqual(nasadem_intersections(box(-67.5, -23.2, -66.5, -22.5), catalog),
                         ['NASADEM_HGT_s23w067', 'NASADEM_HGT_s24w068'])

    def test_saved_evidence_is_internally_consistent(self):
        path = OUTPUT / 'evidence.json'
        if not path.exists():
            self.skipTest('Run the bounded scientific acquisition first.')
        result = json.loads(path.read_text(encoding='utf-8'))
        comparisons = json.loads((OUTPUT / 'comparisons.json').read_text(encoding='utf-8'))
        self.assertEqual(len(result['evidence']), 5)
        self.assertEqual(len(comparisons['references']), 4)
        for record in result['evidence'].values():
            water = record['water_occurrence']
            self.assertEqual(water['counts']['pixels'], sum(water['counts'][name] for name in
                ('no_data', 'no_water_detected', 'water_detected')))
            self.assertEqual(water['counts']['water_detected'],
                             sum(water['positive_occurrence_histogram'].values()))
            self.assertTrue(record['nasadem_intersecting_catalog_granules'])
        for key, (name, _) in JRC_TILES.items():
            path = RAW / name
            if path.exists():
                with rasterio.open(path) as dataset:
                    validate_tile_registration(dataset, key)


if __name__ == '__main__':
    unittest.main()
