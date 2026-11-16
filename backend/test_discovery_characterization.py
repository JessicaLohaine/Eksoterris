"""Shifted-center geometry, geographic screening, and saved comparison integrity."""
import json
import unittest

import numpy as np
from shapely.geometry import GeometryCollection, box

from discovery_characterization import (OUTPUT, geographic_screen, overlap_fraction,
                                        shifted_centers)
from discovery_expansion import OUTPUT as PREVIOUS, REGIONS, regional_centers
from science import FEATURES, TARGETS
from terrestrial_discovery import sha256


class CharacterizationTest(unittest.TestCase):
    def test_half_step_is_deterministic_and_keeps_source_halo(self):
        for region in REGIONS:
            shifted = shifted_centers(region)
            old = regional_centers(region)
            self.assertEqual(shifted, shifted_centers(region))
            self.assertEqual(len(shifted), 49)
            self.assertEqual(len({c['coordinate_key'] for c in shifted}), 49)
            self.assertAlmostEqual(shifted[0]['longitude'] - old[0]['longitude'], 0.5)
            self.assertAlmostEqual(np.sin(np.radians(shifted[0]['latitude'])),
                                   (np.sin(np.radians(old[0]['latitude'])) +
                                    np.sin(np.radians(old[7]['latitude']))) / 2, places=14)
            for c in shifted:
                t = region['tile']
                self.assertTrue(t['south'] + 1 < c['latitude'] < t['north'] - 1)
                self.assertTrue(t['west'] + 1 < c['longitude'] < t['east'] - 1)

    def test_overlap_and_boundary_screen_on_synthetic_polygons(self):
        a = {'latitude': 0.0, 'longitude': 0.0}
        b = {'latitude': 0.0, 'longitude': 0.0}
        distant = {'latitude': 0.0, 'longitude': 5.0}
        self.assertAlmostEqual(overlap_fraction(a, b), 1.0)
        self.assertEqual(overlap_fraction(a, distant), 0.0)
        masks = {'land': (box(-3, -3, 3, 3), {}),
                 'lakes': (box(0.1, 0.1, 0.2, 0.2), {}),
                 'glaciated_areas': (GeometryCollection(), {})}
        report = geographic_screen(a, masks)
        self.assertTrue(report['land_footprint_covered'])
        self.assertTrue(report['mapped_lake_intersection'])
        self.assertEqual(report['mapped_lake_distance_km_approx'], 0)
        self.assertIsNone(report['mapped_glaciated_area_distance_km_approx'])

    def test_clipped_tile_edge_is_not_reported_as_coastline(self):
        region = REGIONS[0]
        tile = region['tile']
        masks = {'land': (box(tile['west'], tile['south'], tile['east'], tile['north']), {}),
                 'lakes': (GeometryCollection(), {}),
                 'glaciated_areas': (GeometryCollection(), {})}
        center = {'latitude': (tile['south'] + tile['north']) / 2,
                  'longitude': (tile['west'] + tile['east']) / 2,
                  'region': region['region']}
        report = geographic_screen(center, masks)
        self.assertIsNone(report['mapped_land_boundary_distance_km_approx'])
        self.assertGreater(report['mask_tile_boundary_distance_km_approx'], 0)

    def test_saved_shifted_outputs_keep_prior_combined_unchanged(self):
        path = OUTPUT / 'summary.json'
        if not path.exists():
            self.skipTest('Execute the bounded shifted experiments first.')
        summary = json.loads(path.read_text(encoding='utf-8'))
        combined = json.loads((OUTPUT / 'combined-shifted.json').read_text(encoding='utf-8'))
        self.assertEqual(summary['preserved_original_combined_sha256'],
                         sha256((PREVIOUS / 'combined.json').read_bytes()))
        self.assertEqual(set(summary['combined']['references']), set(TARGETS))
        self.assertEqual(len(combined['candidates']), summary['combined']['shifted_count'])
        self.assertEqual(len({c['id'] for c in combined['candidates']}), len(combined['candidates']))
        self.assertEqual(len(summary['regions']), 2)
        for region in REGIONS:
            name = region['id']
            document = json.loads((OUTPUT / (name + '-shifted.json')).read_text(encoding='utf-8'))
            prior = json.loads((PREVIOUS / (name + '.json')).read_text(encoding='utf-8'))
            self.assertEqual(document['source']['sha256'], prior['source']['sha256'])
            self.assertEqual(document['generated_count'], 49)
            self.assertEqual(document['generated_count'], document['evaluated_count'] + document['excluded_count'])
            self.assertEqual(set(document['references']), set(TARGETS))
            self.assertEqual(set(summary['regions'][name]['ranges']['shifted']), set(FEATURES))
            for target, comparison in summary['regions'][name]['leaders'].items():
                self.assertIn(target, TARGETS)
                self.assertGreaterEqual(comparison['footprint_intersection_over_union'], 0)
                self.assertLessEqual(comparison['footprint_intersection_over_union'], 1)
                self.assertEqual(comparison['shifted']['quality']['valid_land_node_checks'], 12100)
        for result in combined['references'].values():
            self.assertEqual(len(result['ranking']), len(combined['candidates']))
            self.assertEqual([row['distance'] for row in result['ranking']],
                             sorted(row['distance'] for row in result['ranking']))


if __name__ == '__main__':
    unittest.main()
