"""Analytical controls for the optional scale and independent PDS checks."""
import math
import hashlib
import unittest

import numpy as np

from science import RADIUS
from sources import Raster
from spatial_scale_experiment import CONFIGURATIONS, sample_window, terrain_descriptors


class SpatialScaleExperimentTests(unittest.TestCase):
    def test_configurations_separate_density_from_extent(self):
        baseline, density7, density5, extent9, extent13 = CONFIGURATIONS
        self.assertEqual((baseline['grid_size'], baseline['width_m']), (11, 220000))
        self.assertEqual((density7['width_m'], density5['width_m']), (220000, 220000))
        self.assertEqual((extent9['width_m'], extent13['width_m']), (180000, 260000))
        self.assertEqual((extent9['width_m'] / extent9['grid_size'],
                          extent13['width_m'] / extent13['grid_size']), (20000, 20000))

    def test_analytical_plane_at_seven_cells(self):
        y, x = np.indices((7, 7))
        z = 100 + 2 * x + 3 * y
        result = terrain_descriptors(z, 1000)
        # Sorted low values begin 0, 2, 3, 4. Index 2.4 interpolates to 3.4;
        # symmetry around 15 gives the 95th percentile as 26.6.
        self.assertAlmostEqual(result['relief_m'], 23.2)
        self.assertAlmostEqual(result['median_slope_deg'],
                               math.degrees(math.atan(math.sqrt(13) / 1000)), places=12)
        self.assertLess(result['detrended_rms_m'], 1e-10)

    def test_detrended_rms_on_five_cell_synthetic_surface(self):
        y, x = np.indices((5, 5))
        x, y = x - 2, y - 2
        # E[x^2] = E[y^2] = 2; 3xy is orthogonal to the fitted plane.
        z = 8 + x - 2 * y + 3 * x * y
        self.assertAlmostEqual(terrain_descriptors(z, 20000)['detrended_rms_m'], 6.0)

    def test_multiple_densities_keep_nominal_width_and_reject_missing_edges(self):
        raster = Raster(np.full((11, 11), 17), np.arange(-5, 6), np.arange(-5, 6), {})
        center = {'latitude': 0, 'longitude': 0}
        for size in (5, 7, 11):
            with self.subTest(size=size):
                grid, (lat, lon) = sample_window(raster, center, 'earth', 220000, size, True)
                self.assertEqual(grid.shape, (size, size))
                self.assertEqual(lat.shape, (25, size, size))
                np.testing.assert_array_equal(grid, np.full((size, size), 17))
                self.assertAlmostEqual(float(lon[14, size // 2, -1]),
                                       math.degrees((110000 - 0.1 * 220000 / size) / RADIUS['earth']), places=9)
        small = Raster(np.ones((3, 3)), [-0.1, 0, 0.1], [-0.1, 0, 0.1], {})
        with self.assertRaisesRegex(ValueError, 'outside source coverage'):
            sample_window(small, center, 'earth', 220000, 7)
        with self.assertRaises(ValueError):
            sample_window(raster, center, 'earth', 220000, 4)
        with self.assertRaises(ValueError):
            terrain_descriptors(np.full((5, 5), np.nan), 20000)

    def test_identical_configuration_is_reproducible(self):
        latitudes = np.arange(-5, 6, dtype=float)
        longitudes = np.arange(-5, 6, dtype=float)
        z = np.add.outer(latitudes ** 2, longitudes)
        raster = Raster(z, latitudes, longitudes, {})
        center = {'latitude': 0, 'longitude': 0}
        first = sample_window(raster, center, 'earth', 220000, 11)
        second = sample_window(raster, center, 'earth', 220000, 11)
        np.testing.assert_array_equal(first, second)
        self.assertEqual(terrain_descriptors(first, 20000), terrain_descriptors(second, 20000))

    def test_independent_gdal_on_exact_cached_img_when_available(self):
        try:
            import rasterio
        except ImportError:
            self.skipTest('Optional Rasterio/GDAL validation environment is unavailable.')
        from independent_decoder import PRODUCTS, verify
        from sources import DATA
        for product in PRODUCTS.values():
            for extension, cache_extension in ((product['label_extension'], '.lbl'),
                                               (product['image_extension'], '.img')):
                key = hashlib.sha256((product['base'] + product['name'] + extension).encode()).hexdigest()
                if not (DATA / (key + cache_extension)).exists():
                    self.skipTest('The official planetary label and IMG pairs have not been cached.')
        report = verify()
        self.assertIn('GDAL', report['decoder'])
        for body in ('moon', 'mars'):
            self.assertEqual(report['products'][body]['dimensions'], [720, 1440])
            self.assertEqual(report['products'][body]['maximum_source_pixel_difference_m'], 0)
            self.assertEqual(report['products'][body]['nodata_pixel_count'], 0)
        # These raw digital numbers and source indices were recorded from the
        # independent decoder, not computed by the production Raster class.
        expected = {'moon-tranquillitatis': (357, 93, -3766),
                    'moon-tycho': (533, 1394, -3717),
                    'mars-jezero': (286, 310, -2651),
                    'mars-gale': (381, 551, -893)}
        for name, (row, col, raw) in expected.items():
            actual = report['controls'][name]
            self.assertEqual((actual['north_up_row'], actual['column'], actual['raw_digital_number']), (row, col, raw))
            self.assertEqual(actual['pixel_value_difference_m'], 0)


if __name__ == '__main__':
    unittest.main()
