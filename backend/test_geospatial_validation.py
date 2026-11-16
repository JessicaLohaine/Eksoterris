"""Independent coordinate and interpolation controls with hand-derived expectations."""
import math
import csv
import hashlib
import json
import struct
import unittest
from unittest.mock import patch

import numpy as np

from science import RADIUS, coordinates, window
from sources import DATA, MARS_BASE, MOON_BASE, Raster, earth_raster, planetary_raster
from terrain_quality import assess_quality


class GeospatialReferenceTests(unittest.TestCase):
    def test_planetary_pixel_centers_and_named_feature_controls(self):
        # A 720 x 1440, 4-pixel/degree, north-up cell grid has its first
        # source center at 89.875 N, 0.125 E and its last at 89.875 S, 359.875 E.
        lat = -89.875 + np.arange(720) / 4
        lon = 0.125 + np.arange(1440) / 4
        controls = (
            # USGS Planetary Names: Tycho (-43.30, -11.22) and Gale (-5.44, 137.70).
            (-43.30, -11.22, 533, 1395),
            (-5.44, 137.70, 381, 550),
            # Cell centers adjacent to the anti-meridian and the northern edge.
            (89.875, -0.125, 0, 1439),
        )
        for latitude, longitude, north_up_row, col in controls:
            with self.subTest(latitude=latitude, longitude=longitude):
                ascending_row = 719 - north_up_row
                self.assertLessEqual(abs(lat[ascending_row] - latitude), 0.125)
                self.assertLessEqual(abs(((lon[col] - longitude + 180) % 360) - 180), 0.125)
        self.assertEqual((lat[0], lat[-1], lon[0], lon[-1]),
                         (-89.875, 89.875, 0.125, 359.875))

    def test_terrestrial_badwater_coordinate_in_grid_registration(self):
        # NPS location: 36.229805 N, 116.767413 W. NOAA's grid-registered
        # 1 arc-minute nodes in the cached Death Valley subset begin here.
        south, west = 34.25, -119.28333333333333
        latitude = south + 119 / 60
        longitude = west + 151 / 60
        self.assertAlmostEqual(latitude, 36.233333333333334)
        self.assertAlmostEqual(longitude, -116.76666666666667)
        self.assertLess(abs(latitude - 36.229805), 1 / 120)
        self.assertLess(abs(longitude + 116.767413), 1 / 120)

    def test_bilinear_and_periodic_interpolation_on_an_analytical_grid(self):
        values = np.array([[10 * r + c for c in range(4)] for r in range(4)])
        raster = Raster(values, [-0.375, -0.125, 0.125, 0.375],
                        [0.125, 0.375, 0.625, 0.875], {}, True)
        self.assertEqual(float(raster.sample(0, 0.5)), 16.5)
        self.assertEqual(float(raster.sample(-0.125, 0)), 11.5)
        self.assertEqual(float(raster.sample(-0.125, 1)), 11.5)
        self.assertEqual(float(raster.sample(0.375, 0.875)), 33.0)
        with self.assertRaises(ValueError):
            raster.sample(0.5, 0.5)

    def test_nonperiodic_edges_and_missing_values(self):
        raster = Raster([[1, 3], [5, 7]], [0, 1], [0, 1], {})
        self.assertEqual(float(raster.sample(1, 1)), 7)
        with self.assertRaises(ValueError):
            raster.sample(0.5, 1.001)
        with self.assertRaises(ValueError):
            Raster([[0, np.nan], [2, 3]], [0, 1], [0, 1], {})

    def test_planetary_missing_sentinel_is_not_a_valid_interpolation_cell(self):
        label = ('LINES = 720\nLINE_SAMPLES = 1440\nMAP_RESOLUTION = 4\n'
                 'SAMPLE_BITS = 16\nSAMPLE_TYPE = MSB_INTEGER\n'
                 'POSITIVE_LONGITUDE_DIRECTION = EAST\n'
                 'WESTERNMOST_LONGITUDE = 0\nEASTERNMOST_LONGITUDE = 360\n')
        raw = np.zeros((720, 1440), dtype='>i2')
        raw[0, 0] = -32768
        def fixture(url, extension):
            if extension == 'lbl':
                return label.encode('ascii'), {'sha256':'label'}
            return raw.tobytes(), {'sha256':'image'}
        with patch('sources.fetch', side_effect=fixture), self.assertRaisesRegex(ValueError, 'Missing PDS pixels'):
            planetary_raster('mars')

    def test_spherical_window_distance_and_latitude_dependence(self):
        radius = RADIUS['earth']
        equator_lat, equator_lon = coordinates(0, 0, 20000, 0, radius)
        high_lat, high_lon = coordinates(60, 0, 20000, 0, radius)
        # An equatorial 20 km arc is 20,000 / (2*pi*R) of a complete circle.
        expected = 360 * 20000 / (2 * math.pi * radius)
        self.assertAlmostEqual(float(equator_lat), 0, places=12)
        self.assertAlmostEqual(float(equator_lon), expected, places=11)
        self.assertGreater(float(high_lon), expected * 1.99)
        self.assertLess(float(high_lat), 60)
        lat_north, lon_north = coordinates(0, 0, 0, 100000, radius)
        self.assertAlmostEqual(float(lat_north), 5 * expected, places=11)
        self.assertAlmostEqual(float(lon_north), 0, places=11)

    def test_window_center_and_sampling_footprint(self):
        # A constant analytical surface remains constant under bilinear
        # sampling and the 25 subcell means; the returned sample locations
        # independently expose the 100 km centers and 108 km outer samples.
        raster = Raster(np.full((5, 5), 17), [-2, -1, 0, 1, 2],
                        [-2, -1, 0, 1, 2], {})
        grid, (latitudes, longitudes) = window(raster, {'latitude':0, 'longitude':0},
                                               'earth', include_coordinates=True)
        self.assertEqual(grid.shape, (11, 11))
        self.assertEqual(latitudes.shape, (25, 11, 11))
        np.testing.assert_array_equal(grid, np.full((11, 11), 17))
        self.assertAlmostEqual(float(latitudes[12, 5, 5]), 0, places=12)
        self.assertAlmostEqual(float(longitudes[12, 5, 5]), 0, places=12)
        expected_outer = 360 * 108000 / (2 * math.pi * RADIUS['earth'])
        self.assertAlmostEqual(float(longitudes[14, 5, 10]), expected_outer, places=10)
        self.assertAlmostEqual(float(latitudes[22, 10, 5]), expected_outer, places=10)

    def test_mola_counts_describe_source_support_without_changing_elevation(self):
        raster = Raster([[1, 2], [3, 4]], [0, 1], [0.25, 0.75],
                        {'title':'Synthetic MOLA', 'pixels_per_degree':4, 'datum':'areoid'}, True)
        positions = (np.array([[[0.5]]]), np.array([[[0.5]]]))
        source = {'image':{'sha256':'synthetic'}, 'label':{'sha256':'synthetic-label'}}
        with patch('terrain_quality.mola_observation_counts', return_value=(np.array([[1, 0], [2, 3]]), source)):
            result = assess_quality({'body':'mars'}, raster, np.array([[2.5]]), positions)
        coverage = result['observation_coverage']
        self.assertEqual(coverage['source_bins_touched'], 4)
        self.assertEqual(coverage['bins_with_at_least_one_shot'], 3)
        self.assertEqual(coverage['bins_with_no_shots'], 1)
        self.assertEqual(coverage['status'], 'includes_zero_count_source_bins')
        with patch('terrain_quality.mola_observation_counts', return_value=None):
            without_optional_layer = assess_quality({'body':'mars'}, raster, np.array([[2.5]]), positions)
        self.assertNotIn('observation_coverage', without_optional_layer)
        self.assertIn('not processed', without_optional_layer['quality_layer_status'])

    def test_real_planetary_bytes_match_independent_source_indices(self):
        controls = ((MOON_BASE, 'LDEM_4.IMG', 'moon', 533, 1395, '<h', 0.5),
                    (MARS_BASE, 'megt90n000cb.img', 'mars', 381, 550, '>h', 1.0))
        for base, name, body, north_row, col, encoding, scale in controls:
            with self.subTest(body=body):
                path = DATA / (hashlib.sha256((base + name).encode()).hexdigest() + '.img')
                if not path.exists():
                    self.skipTest('The official planetary IMG is not in the local cache.')
                with path.open('rb') as handle:
                    handle.seek(2 * (north_row * 1440 + col))
                    raw_value = struct.unpack(encoding, handle.read(2))[0]
                latitude = 90 - (north_row + 0.5) / 4
                longitude = (col + 0.5) / 4
                raster = planetary_raster(body)
                self.assertEqual(float(raster.sample(latitude, longitude)), raw_value * scale)
                self.assertEqual(float(raster.z[719 - north_row, col]), raw_value * scale)

    def test_real_earth_grid_node_matches_independent_csv_row(self):
        # The official NPS Badwater coordinate falls inside the previously
        # acquired Death Valley ETOPO1 subset, with 241 x 299 grid nodes.
        if not any('etopo180.csv' in json.loads(path.read_text(encoding='utf-8'))['url']
                   and '34.25000' in json.loads(path.read_text(encoding='utf-8'))['url']
                   for path in DATA.glob('*.meta.json')):
            self.skipTest('The Death Valley ETOPO1 subset is not in the local cache.')
        raster = earth_raster(36.25, -116.8)
        url = raster.provenance['url']
        path = DATA / (hashlib.sha256(url.encode()).hexdigest() + '.csv')
        with path.open(newline='', encoding='utf-8') as handle:
            reader = csv.reader(handle)
            next(reader)
            next(reader)
            for _ in range(119 * 299 + 151):
                next(reader)
            latitude, longitude, elevation = map(float, next(reader))
        self.assertEqual(raster.z.shape, (241, 299))
        self.assertAlmostEqual(latitude, 36.233333333333334, places=10)
        self.assertAlmostEqual(longitude, -116.76666666666667, places=10)
        self.assertAlmostEqual(float(raster.sample(latitude, longitude)), elevation, places=7)


if __name__ == '__main__':
    unittest.main()
