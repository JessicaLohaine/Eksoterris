"""Analytical controls for the independent complete-window validator."""
import math
import unittest

import numpy as np
try:
    import rasterio
    from rasterio.transform import Affine
except ImportError:
    rasterio = None
    Affine = None

from independent_window_validation import (
    CONFIGURATIONS, descriptors, interpolate_north_up, local_positions,
    percentile_linear,
)


@unittest.skipUnless(rasterio is not None, 'Optional Rasterio/GDAL is unavailable.')
class IndependentWindowValidationTests(unittest.TestCase):
    def test_bilinear_and_node_registration(self):
        z = np.array([[10., 20.], [30., 50.]])
        transform = Affine.translation(-.5, 1.5) @ Affine.scale(1, -1)
        self.assertAlmostEqual(float(interpolate_north_up(z, transform, .75, .25)), 18.125)
        self.assertEqual(float(interpolate_north_up(z, transform, 1., 0.)), 10.)
        self.assertEqual(float(interpolate_north_up(z, transform, 0., 1.)), 50.)
        with self.assertRaisesRegex(ValueError, 'outside'):
            interpolate_north_up(z, transform, .5, 1.01)

    def test_periodic_longitude_and_missing_source(self):
        z = np.array([[10.,20.,30.,40.],[50.,60.,70.,80.]])
        transform = Affine.translation(0, 1) @ Affine.scale(90, -1)
        self.assertEqual(float(interpolate_north_up(z,transform,.5,0,periodic=True)), 25.)
        self.assertEqual(float(interpolate_north_up(z,transform,.5,360,periodic=True)),25.)
        z[0,0] = -32768
        with self.assertRaisesRegex(ValueError, 'NoData'):
            interpolate_north_up(z,transform,.5,0,periodic=True,nodata=-32768)

    def test_known_percentiles_slope_and_residual(self):
        z = np.arange(25.).reshape(5,5)
        self.assertAlmostEqual(percentile_linear(z,5),1.2)
        self.assertAlmostEqual(percentile_linear(z,95),22.8)
        plane = descriptors(z,1000)
        self.assertAlmostEqual(plane['relief_m'],21.6)
        self.assertAlmostEqual(plane['median_slope_deg'],math.degrees(math.atan(math.sqrt(26)/1000)),places=12)
        self.assertLess(plane['detrended_rms_m'],1e-12)
        y,x = np.indices((5,5))
        surface = 10 + 3*(x-2)*(y-2)
        self.assertAlmostEqual(descriptors(surface,20000)['detrended_rms_m'],6.)
        with self.assertRaises(ValueError):
            descriptors(np.full((5,5),np.nan),20000)

    def test_spherical_locations_and_all_grid_dimensions(self):
        for width,size in CONFIGURATIONS:
            lat,lon=local_positions(0,0,6371008.8,width,size)
            self.assertEqual(lat.shape,(25,size,size))
            self.assertAlmostEqual(float(lat[12,size//2,size//2]),0.,places=12)
            self.assertAlmostEqual(float(lon[12,size//2,size//2]),0.,places=12)
            self.assertAlmostEqual(float(lon[14,size//2,-1]),
                math.degrees((width/2-.1*width/size)/6371008.8),places=10)
        lat,lon=local_positions(0,179.99,6371008.8,220000,11)
        self.assertTrue(np.any(lon < -179))
        self.assertTrue(np.isfinite(lat).all())

    def test_complete_cached_windows_when_sources_are_available(self):
        from sources import DATA
        if not (DATA/'spatial-scale-report.json').exists():
            self.skipTest('The previous verified scale report is not cached.')
        from independent_window_validation import run_validation
        result=run_validation()
        self.assertEqual(len(result['comparisons']),55)
        self.assertEqual(len(result['rankings']),20)
        self.assertEqual(sum(item['sample_comparison']['expected_queries'] for item in result['comparisons'].values()),122375)
        for item in result['comparisons'].values():
            check=item['sample_comparison']
            self.assertEqual(check['valid_queries'],check['expected_queries'])
            self.assertTrue(check['within_derived_numerical_envelope'])
            self.assertLessEqual(item['grid_maximum_absolute_difference_m'],check['maximum_absolute_difference_m'])
            for feature in ('relief_m','median_slope_deg','detrended_rms_m'):
                self.assertTrue(math.isfinite(item['descriptors'][feature]['independent']))
        for item in result['rankings'].values():
            self.assertEqual(item['winner'],item['production_winner'])
            self.assertEqual([candidate['id'] for candidate in item['ranking']],item['production_ranking'])
            self.assertEqual(item['independent_outside_features'],item['production_outside_features'])


if __name__=='__main__':
    unittest.main()
