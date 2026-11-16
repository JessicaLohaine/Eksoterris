"""Controlled synthetic and saved-result checks for discovery robustness."""
import json
import unittest

import numpy as np
from shapely.geometry import GeometryCollection, box

from discovery_robustness import (CONFIGS, OUTPUT, centers, eligibility, footprint,
                                  overlap_analysis, query_source_nodes)
from science import FEATURES, TARGETS
from sources import Raster
from terrestrial_discovery import OUTPUT as BASE_OUTPUT, candidate_centers, sha256


class RobustnessTest(unittest.TestCase):
    def setUp(self):
        self.center = {'id': 'a', 'latitude': 9.0, 'longitude': 3.0}
        self.empty = GeometryCollection()
        self.raster = Raster(np.ones((601, 601)), np.linspace(4, 14, 601),
                             np.linspace(-2, 8, 601), {})
        self.masks = {name: (geom, {}) for name, geom in
                      [('land', box(-2, 4, 8, 14)), ('lakes', self.empty),
                       ('glaciated_areas', self.empty)]}

    def test_center_counts_original_and_shifted(self):
        self.assertEqual([len(centers(config)) for config in CONFIGS], [49, 49, 16, 169, 49, 49, 49, 169])
        original = candidate_centers()
        for a, b in zip(centers(CONFIGS[0]), original):
            self.assertEqual(a['id'], b['id'])
            self.assertAlmostEqual(a['latitude'], b['latitude'], places=12)
            self.assertAlmostEqual(a['longitude'], b['longitude'], places=12)
        shifted = centers(CONFIGS[1])
        self.assertAlmostEqual(shifted[0]['longitude'], 0.5)
        self.assertTrue(shifted[0]['latitude'] > original[0]['latitude'])
        self.assertEqual(len({c['coordinate_key'] for c in centers(CONFIGS[3])}), 169)

    def test_window_and_query_counts_change_without_source_oversampling_claim(self):
        for width, size in [(180000, 9), (220000, 11), (260000, 13)]:
            status, quality = eligibility(self.center, self.raster, self.masks, width, size)
            self.assertEqual(status, 'eligible_land_topography')
            self.assertEqual(quality['expected_queries'], 25 * size**2)
            self.assertEqual(quality['valid_land_node_checks'], 100 * size**2)
            lon, lat = query_source_nodes(self.center, self.raster, width, size)
            self.assertEqual(len(lon), 100 * size**2)
            self.assertEqual(len(lat), 100 * size**2)
        self.assertLess(footprint(self.center, 180000).area, footprint(self.center, 220000).area)
        self.assertLess(footprint(self.center, 220000).area, footprint(self.center, 260000).area)

    def test_mask_detail_changes_eligibility_without_inventing_valid_data(self):
        coarse = eligibility(self.center, self.raster, self.masks, 220000, 11)[0]
        finer = dict(self.masks)
        finer['lakes'] = (box(2.9, 8.9, 3.1, 9.1), {})
        self.assertEqual(coarse, 'eligible_land_topography')
        self.assertEqual(eligibility(self.center, self.raster, finer, 220000, 11)[0],
                         'inland_water_intersection')
        limited = Raster(np.ones((13, 13)), np.linspace(8.9, 9.1, 13),
                         np.linspace(2.9, 3.1, 13), {})
        self.assertEqual(eligibility(self.center, limited, self.masks, 220000, 11)[0],
                         'insufficient_elevation_coverage')

    def test_overlap_is_symmetric_and_thinning_order_is_recorded(self):
        other = {'id': 'b', 'latitude': 9.0, 'longitude': 3.0}
        distant = {'id': 'c', 'latitude': 9.0, 'longitude': 6.0}
        data = overlap_analysis([self.center, other, distant], 220000)
        self.assertEqual(data['intersecting_pairs'], 1)
        self.assertAlmostEqual(data['pairs'][0]['intersection_over_union'], 1)
        self.assertEqual(data['trial_thinning_iou_0_25']['southwest_first'], ['a', 'c'])
        self.assertEqual(data['trial_thinning_iou_0_25']['northeast_first'], ['c', 'b'])

    def test_saved_experiments_preserve_original_and_cover_four_references(self):
        summary_path = OUTPUT / 'summary.json'
        if not summary_path.exists():
            self.skipTest('Execute the bounded robustness experiment first.')
        summary = json.loads(summary_path.read_text(encoding='utf-8'))
        self.assertEqual(len(summary['experiments']), len(CONFIGS))
        self.assertEqual(summary['baseline']['catalog_sha256'],
                         sha256((BASE_OUTPUT / 'catalog.json').read_bytes()))
        self.assertEqual(summary['baseline']['rankings_sha256'],
                         sha256((BASE_OUTPUT / 'rankings.json').read_bytes()))
        for config in CONFIGS:
            experiment = json.loads((OUTPUT / (config['id'] + '.json')).read_text(encoding='utf-8'))
            self.assertEqual(set(experiment['references']), set(TARGETS))
            self.assertEqual(experiment['generated_count'], len(centers(config)))
            self.assertEqual(experiment['generated_count'], experiment['evaluated_count'] + experiment['excluded_count'])
            self.assertEqual(set(experiment['model']['feature_names']), set(FEATURES))
            for item in experiment['references'].values():
                ranks = item['ranking']
                self.assertEqual(len(ranks), experiment['evaluated_count'])
                self.assertEqual(len({r['coordinate_key'] for r in ranks}), len(ranks))
                self.assertEqual([r['distance'] for r in ranks], sorted(r['distance'] for r in ranks))
                self.assertEqual(set(item['range_diagnostics']['descriptors']), set(FEATURES))


if __name__ == '__main__':
    unittest.main()
