"""Synthetic eligibility and catalog integration checks for bounded discovery."""
import json
import unittest

import numpy as np
from shapely.geometry import GeometryCollection, box

from science import CANDIDATES, FEATURES, TARGETS
from sources import Raster
from terrain_knn import TerrainKNN
from terrestrial_discovery import OUTPUT, candidate_centers, eligibility, footprint


class DiscoveryTest(unittest.TestCase):
    def setUp(self):
        self.center = {'id': 'synthetic', 'latitude': 9.0, 'longitude': 3.0}
        lat = np.linspace(4, 14, 601)
        lon = np.linspace(-2, 8, 601)
        self.raster = Raster(np.ones((601, 601)), lat, lon, {})
        self.land = box(-2, 4, 8, 14)
        self.empty = GeometryCollection()

    def test_deterministic_equal_area_centers_are_not_baseline_sites(self):
        first, second = candidate_centers(), candidate_centers()
        self.assertEqual(first, second)
        self.assertEqual(len(first), 49)
        self.assertEqual(len({c['id'] for c in first}), 49)
        self.assertFalse({c['id'] for c in first} & {c['id'] for c in CANDIDATES})
        latitudes = [first[row * 7]['latitude'] for row in range(7)]
        self.assertTrue(np.allclose(np.diff(np.sin(np.radians(latitudes))),
                                    np.diff(np.sin(np.radians(latitudes)))[0]))
        self.assertEqual([c['longitude'] for c in first[:7]], list(range(7)))

    def test_complete_land_window_and_source_neighbors(self):
        status, quality = eligibility(self.center, self.raster, self.land, self.empty, self.empty)
        self.assertEqual(status, 'eligible_land_topography')
        self.assertEqual(quality['expected_queries'], 3025)
        self.assertEqual(quality['valid_land_node_checks'], 12100)
        self.assertTrue(self.land.covers(footprint(self.center)))

    def test_coast_lake_and_mapped_glacier_exclusions(self):
        coast = box(-2, 4, 3, 14)
        self.assertEqual(eligibility(self.center, self.raster, coast, self.empty, self.empty)[0],
                         'mixed_land_or_ocean')
        feature = box(2.9, 8.9, 3.1, 9.1)
        self.assertEqual(eligibility(self.center, self.raster, self.land, feature, self.empty)[0],
                         'inland_water_intersection')
        self.assertEqual(eligibility(self.center, self.raster, self.land, self.empty, feature)[0],
                         'mapped_glaciated_area')

    def test_missing_source_coverage_is_excluded(self):
        limited = Raster(np.ones((13, 13)), np.linspace(8.9, 9.1, 13),
                         np.linspace(2.9, 3.1, 13), {})
        self.assertEqual(eligibility(self.center, limited, self.land, self.empty, self.empty)[0],
                         'insufficient_elevation_coverage')
        with self.assertRaisesRegex(ValueError, 'missing elevation'):
            Raster(np.full((2, 2), np.nan), [0, 1], [0, 1], {})

    def test_saved_discovery_catalog_integrates_all_references(self):
        catalog_file, ranking_file = OUTPUT / 'catalog.json', OUTPUT / 'rankings.json'
        if not catalog_file.exists() or not ranking_file.exists():
            self.skipTest('Generate the bounded discovery catalog before artifact validation.')
        catalog = json.loads(catalog_file.read_text(encoding='utf-8'))
        rankings = json.loads(ranking_file.read_text(encoding='utf-8'))
        eligible = [c for c in catalog['candidates'] if c['status'] == 'eligible_land_topography']
        self.assertEqual(catalog['generated_count'], 49)
        self.assertEqual(catalog['evaluated_count'], len(eligible))
        self.assertEqual(catalog['excluded_count'], 49 - len(eligible))
        self.assertEqual(set(rankings['references']), set(TARGETS))
        model = TerrainKNN(FEATURES).fit(eligible)
        for item in rankings['references'].values():
            listed = item['ranking']
            self.assertEqual(len(listed), len(eligible))
            self.assertEqual({r['id'] for r in listed}, {c['id'] for c in eligible})
            self.assertFalse({r['id'] for r in listed} & {c['id'] for c in CANDIDATES})
            self.assertEqual([r['id'] for r in listed],
                             [identifier for identifier, _ in model.query(item['reference']['features'])])
            for result in listed:
                self.assertTrue(np.isfinite(result['distance']))
                self.assertEqual(set(result['distance_explanation']['descriptors']), set(FEATURES))
                self.assertAlmostEqual(sum(v['contribution_to_squared_distance'] for v in
                                           result['distance_explanation']['descriptors'].values()),
                                       result['distance'] ** 2, places=9)


if __name__ == '__main__':
    unittest.main()
