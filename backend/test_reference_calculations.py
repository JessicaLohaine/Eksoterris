"""Analytical checks whose expected results do not reuse production formulas."""
import math
import unittest

import numpy as np

from ranking_sensitivity import descriptor_and_catalog_scenarios
from gemini_interpreter import evidence_for, validate_selection
from science import features
from sources import Raster
from terrain_knn import TerrainKNN


class IndependentReferenceTests(unittest.TestCase):
    def test_percentile_range_on_integer_ramp(self):
        # For the integers 0..120, the 5th and 95th percentiles are 6 and 114.
        grid = np.arange(121, dtype=float).reshape(11, 11)
        self.assertEqual(features(grid)['relief_m'], 108.0)

    def test_plane_has_analytical_slope_and_zero_residual(self):
        y, x = np.indices((11, 11))
        grid = 100 + 2 * x + y
        result = features(grid, spacing=10)
        self.assertAlmostEqual(result['median_slope_deg'], math.degrees(math.atan(math.sqrt(0.05))), places=12)
        self.assertLess(result['detrended_rms_m'], 1e-10)

    def test_bilinear_surface_has_known_detrended_rms(self):
        y, x = np.indices((11, 11))
        x, y = x - 5, y - 5
        # x*y is orthogonal to intercept, x, and y on this centered grid.
        # E[x^2] = E[y^2] = 10, so RMS(4*x*y) = 4*sqrt(10*10) = 40.
        grid = 7 + 3*x - 2*y + 4*x*y
        self.assertAlmostEqual(features(grid)['detrended_rms_m'], 40.0, places=11)

    def test_missing_pixels_and_dimensions_fail(self):
        grid = np.zeros((11, 11))
        grid[0, 0] = np.nan
        with self.assertRaises(ValueError):
            features(grid)
        with self.assertRaises(ValueError):
            features(np.zeros((10, 11)))

    def test_bilinear_grid_boundary_is_exact(self):
        raster = Raster([[0, 10], [20, 30]], [0, 1], [0, 1], {})
        self.assertEqual(float(raster.sample(1, 1)), 30)
        with self.assertRaises(ValueError):
            raster.sample(1.01, 1)

    def test_hand_computed_scale_distance_and_contribution(self):
        samples = [{'id':str(i), 'features':{'a':float(2*i), 'b':float(4*i)}} for i in range(4)]
        model = TerrainKNN(('a', 'b')).fit(samples)
        np.testing.assert_allclose(model.scale, [3, 6], rtol=0, atol=1e-12)
        query = {'a':3.0, 'b':6.0}
        self.assertEqual([item[0] for item in model.query(query)], ['1', '2', '0', '3'])
        self.assertAlmostEqual(dict(model.query(query))['0'], 1.0)
        contribution = model.explain(query)['0']
        self.assertEqual(contribution['descriptors']['a']['scaled_difference'], -1.0)
        self.assertEqual(contribution['descriptors']['a']['contribution_to_squared_distance'], 0.5)
        self.assertEqual(contribution['descriptors']['b']['contribution_to_squared_distance'], 0.5)
        self.assertEqual(contribution['squared_distance'], 1.0)
        self.assertEqual(contribution['distance'], 1.0)

    def test_outside_reference_is_inconclusive_but_ranked(self):
        samples = [{'id':str(i), 'features':{'a':float(2*i), 'b':float(4*i)}} for i in range(4)]
        model = TerrainKNN(('a', 'b')).fit(samples)
        result = model.range_diagnostics({'a':7.0, 'b':6.0})
        self.assertEqual(result['status'], 'insufficient_catalog_evidence')
        self.assertEqual(result['outside_features'], ['a'])
        self.assertEqual(result['descriptors']['a']['earth_max'], 6.0)
        self.assertEqual(result['descriptors']['b']['position'], 'within')
        self.assertEqual(model.query({'a':7.0, 'b':6.0})[0][0], '2')
        self.assertEqual(model.range_diagnostics({'a':3.0, 'b':6.0})['status'], 'within_observed_feature_ranges')

    def test_fixed_and_refitted_calibration_are_explicit(self):
        samples = [{'id':str(i), 'features':{'a':float(2*i), 'b':float(4*i), 'c':float(i)}} for i in range(4)]
        model = TerrainKNN(('a', 'b', 'c')).fit(samples)
        report = descriptor_and_catalog_scenarios(model, samples, {'a':3.0, 'b':6.0, 'c':1.5})
        fixed = next(item for item in report['scenarios'] if item['name'] == 'exclude:0:fixed_iqr')
        refit = next(item for item in report['scenarios'] if item['name'] == 'exclude:0:refit_iqr')
        self.assertEqual(fixed['earth_iqr']['a'], 3.0)
        self.assertEqual(refit['earth_iqr']['a'], 2.0)
        self.assertEqual(fixed['winner'], '1')
        self.assertEqual(refit['winner'], '1')
        self.assertAlmostEqual(fixed['shared_candidate_spearman_rho'], 1.0)

    def test_gemini_must_include_catalog_support_evidence(self):
        names=('relief_m', 'median_slope_deg', 'detrended_rms_m')
        run={'candidates':[{'id':'earth', 'name':'Earth window', 'distance':2.0,
                            'features':dict.fromkeys(names, 1.0)}],
             'reference':{'features':dict.fromkeys(names, 3.0)},
             'sensitivity':dict.fromkeys(names, 'earth'),
             'range_diagnostics':{'interpretation':'Insufficient catalog evidence.'}}
        evidence=evidence_for(run)
        selection={'candidate_id':'earth', 'evidence_ids':['ranking','sensitivity','catalog_support'],
                   'limitation_ids':['scope','resolution','method']}
        self.assertEqual(validate_selection(selection,evidence,run),selection)
        with self.assertRaises(ValueError):
            validate_selection({**selection, 'evidence_ids':['ranking','sensitivity']},evidence,run)


if __name__ == '__main__':
    unittest.main()
