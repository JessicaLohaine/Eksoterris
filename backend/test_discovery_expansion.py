"""Predeclared regional center generation and combined-result integrity."""
import json
import unittest

import numpy as np

from discovery_expansion import OUTPUT, REGIONS, regional_centers
from science import CANDIDATES, FEATURES, TARGETS
from terrestrial_discovery import OUTPUT as FIRST_OUTPUT, sha256


class RegionalExpansionTest(unittest.TestCase):
    def test_predeclared_tiles_generate_unique_nonbaseline_centers(self):
        ids = set()
        for region in REGIONS:
            tile = region['tile']
            centers = regional_centers(region)
            self.assertEqual(len(centers), 49)
            self.assertEqual(centers, regional_centers(region))
            latitudes = [centers[row * 7]['latitude'] for row in range(7)]
            self.assertTrue(np.allclose(np.diff(np.sin(np.radians(latitudes))),
                                        np.diff(np.sin(np.radians(latitudes)))[0]))
            for center in centers:
                self.assertTrue(tile['south'] + 1 < center['latitude'] < tile['north'] - 1)
                self.assertTrue(tile['west'] + 1 < center['longitude'] < tile['east'] - 1)
                self.assertNotIn(center['id'], ids)
                self.assertTrue(all((center['latitude'], center['longitude']) !=
                                    (old['latitude'], old['longitude']) for old in CANDIDATES))
                ids.add(center['id'])

    def test_saved_regional_and_combined_outputs(self):
        path = OUTPUT / 'combined.json'
        if not path.exists():
            self.skipTest('Execute the bounded regional expansion first.')
        combined = json.loads(path.read_text(encoding='utf-8'))
        summary = json.loads((OUTPUT / 'summary.json').read_text(encoding='utf-8'))
        self.assertEqual(combined['original_catalog_sha256'], sha256((FIRST_OUTPUT / 'catalog.json').read_bytes()))
        self.assertEqual(combined['original_rankings_sha256'], sha256((FIRST_OUTPUT / 'rankings.json').read_bytes()))
        self.assertEqual(set(combined['references']), set(TARGETS))
        self.assertEqual(len(summary['regions']), 2)
        ids = [c['id'] for c in combined['candidates']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 26 + sum(region['evaluated'] for region in summary['regions']))
        self.assertFalse(set(ids) & {c['id'] for c in CANDIDATES})
        for target in combined['references'].values():
            ranking = target['ranking']
            self.assertEqual(len(ranking), len(ids))
            self.assertEqual(set(r['id'] for r in ranking), set(ids))
            self.assertEqual([r['distance'] for r in ranking], sorted(r['distance'] for r in ranking))
            self.assertEqual(set(target['range_diagnostics']['descriptors']), set(FEATURES))
        for region in REGIONS:
            local = json.loads((OUTPUT / (region['id'] + '.json')).read_text(encoding='utf-8'))
            self.assertEqual(local['generated_count'], 49)
            self.assertEqual(local['evaluated_count'] + local['excluded_count'], 49)
            self.assertEqual(set(local['references']), set(TARGETS))


if __name__ == '__main__':
    unittest.main()
