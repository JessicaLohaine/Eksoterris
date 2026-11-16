"""Synthetic registration controls and raw-byte checks for LOLA count validation."""
import hashlib
import unittest

import numpy as np

from lola_count_validation import (
    BASE, DATA, REGISTRATION_FIELDS, assert_pixel_agreement,
    bilinear_support, count_summary, nearest_pixel, pixel_center,
    run_validation, validate_registration,
)


def synthetic_label(product, *, row_offset='359.5', column_offset='719.5',
                    longitude_direction='EAST', scale='7580.84'):
    values = {key: '0' if key in {
        'LINES', 'LINE_SAMPLES', 'SAMPLE_BITS', 'MAP_RESOLUTION',
        'A_AXIS_RADIUS', 'B_AXIS_RADIUS', 'C_AXIS_RADIUS', 'CENTER_LATITUDE',
        'CENTER_LONGITUDE', 'MAXIMUM_LATITUDE', 'MINIMUM_LATITUDE',
        'WESTERNMOST_LONGITUDE', 'EASTERNMOST_LONGITUDE',
        'LINE_PROJECTION_OFFSET', 'SAMPLE_PROJECTION_OFFSET'} else 'X'
        for key in REGISTRATION_FIELDS}
    values.update(DATA_SET_ID='LRO-L-LOLA-4-GDR-V1.0', PRODUCT_VERSION_ID='V3.0',
                  LINES='720', LINE_SAMPLES='1440', SAMPLE_TYPE='LSB_INTEGER',
                  SAMPLE_BITS='16', MAP_RESOLUTION='4',
                  LINE_PROJECTION_OFFSET=row_offset,
                  SAMPLE_PROJECTION_OFFSET=column_offset,
                  POSITIVE_LONGITUDE_DIRECTION=longitude_direction,
                  COORDINATE_SYSTEM_NAME='MEAN EARTH/POLAR AXIS OF DE421')
    return '\n'.join(f'{key} = "{value}"' for key, value in values.items()) + (
        f'\nPRODUCT_ID = "{product}"\nNAME = "COUNTS"\nMAP_SCALE = {scale} <'+
        ('km/pix>' if product == 'LDEC_4' else 'm/pix>'))


class LolaCountSyntheticTests(unittest.TestCase):
    def test_matching_labels_and_one_pixel_shifts(self):
        elevation = synthetic_label('LDEM_4')
        count = synthetic_label('LDEC_4', scale='7.580837606')
        result = validate_registration(elevation, count)
        self.assertAlmostEqual(result['map_scale_difference_m_per_pixel'], .002394, places=9)
        with self.assertRaisesRegex(ValueError, 'potential pixel-center shift'):
            validate_registration(elevation, synthetic_label('LDEC_4', scale='8.0'))
        with self.assertRaisesRegex(ValueError, 'units'):
            validate_registration(elevation, count.replace('<km/pix>', '<m/pix>'))
        for changed in (synthetic_label('LDEC_4', row_offset='360.5', scale='7.580837606'),
                        synthetic_label('LDEC_4', column_offset='720.5', scale='7.580837606'),
                        synthetic_label('LDEC_4', longitude_direction='WEST', scale='7.580837606')):
            with self.assertRaisesRegex(ValueError, 'differ'):
                validate_registration(elevation, changed)

    def test_pixel_centers_orientation_and_wrapping(self):
        self.assertEqual(pixel_center(0, 0), (89.875, .125))
        self.assertEqual(pixel_center(719, 1439), (-89.875, 359.875))
        self.assertEqual(pixel_center(539, 1395), (-44.875, 348.875))
        self.assertEqual(pixel_center(540, 1395), (-45.125, 348.875))
        self.assertEqual(nearest_pixel(-43.31, -11.36), (533, 1394))
        self.assertEqual(nearest_pixel(.674, 383.473), (357, 93))
        self.assertEqual(nearest_pixel(0, -0.125), (360, 1439))
        self.assertEqual(nearest_pixel(0, 359.875), (360, 1439))
        with self.assertRaises(ValueError):
            pixel_center(720, 0)
        with self.assertRaises(ValueError):
            nearest_pixel(90, 0)

    def test_bilinear_source_bins_and_seam(self):
        self.assertEqual(bilinear_support(89.875, .125), {(0, 0)})
        self.assertEqual(bilinear_support(-44.875, 348.875), {(539, 1395)})
        self.assertEqual(bilinear_support(0, 0),
                         {(359, 1439), (359, 0), (360, 1439), (360, 0)})
        self.assertEqual(bilinear_support(0, 360), bilinear_support(0, 0))
        with self.assertRaisesRegex(ValueError, 'outside'):
            bilinear_support(90, 0)

    def test_orientation_shifts_and_byte_order_fail_independent_pixel_check(self):
        raw = np.array([[1, 256, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]], dtype='<i2')
        assert_pixel_agreement(raw, raw.copy())
        for changed in (np.flipud(raw), np.fliplr(raw), np.roll(raw, 1, axis=0),
                        np.roll(raw, 1, axis=1), raw.byteswap()):
            with self.assertRaisesRegex(ValueError, 'disagrees'):
                assert_pixel_agreement(raw, changed)

    def test_zero_count_is_reported_and_nodata_is_rejected(self):
        counts = np.array([[0, 9], [5, 4]])
        summary = count_summary({(0, 0), (0, 1), (1, 0)}, counts)
        self.assertEqual((summary['source_bins'], summary['zero_count_bins']), (3, 1))
        self.assertEqual((summary['minimum'], summary['median'], summary['maximum']), (0, 5, 9))
        counts[0, 0] = -32768
        with self.assertRaisesRegex(ValueError, 'NoData'):
            count_summary({(0, 0)}, counts)

    def test_exact_cached_pair_with_independent_raw_byte_controls(self):
        count_url = BASE + 'LDEC_4.IMG'
        elevation_url = BASE + 'LDEM_4.IMG'
        count_path = DATA / (hashlib.sha256(count_url.encode()).hexdigest()+'.img')
        elevation_path = DATA / (hashlib.sha256(elevation_url.encode()).hexdigest()+'.img')
        if not count_path.exists() or not elevation_path.exists() or not (DATA/'independent-window-report.json').exists():
            self.skipTest('The official LOLA pair and prior window validation are not cached.')
        report = run_validation()
        self.assertEqual(report['whole_count_grid']['zero_count_bins'], 0)
        self.assertEqual(report['whole_count_grid']['minimum'], 64)
        self.assertEqual(report['gdal']['LDEC_4']['shape'], [720, 1440])
        count_bytes = count_path.read_bytes()
        elevation_bytes = elevation_path.read_bytes()
        for target, row, col in (('tycho_center', 533, 1394),
                                 ('tranquillitatis_center', 357, 93),
                                 ('west_seam', 359, 1439), ('east_seam', 359, 0)):
            control = report['controls'][target]
            offset = 2 * (row * 1440 + col)
            expected_count = int.from_bytes(count_bytes[offset:offset+2], 'little', signed=True)
            expected_height = int.from_bytes(elevation_bytes[offset:offset+2], 'little', signed=True) / 2
            self.assertEqual((control['north_up_row'], control['column']), (row, col))
            self.assertEqual(control['observations'], expected_count)
            self.assertEqual(control['height_m'], expected_height)
        for configuration in report['windows'].values():
            for target in configuration.values():
                self.assertGreater(target['unique_source_bins']['source_bins'], 0)
                self.assertEqual(target['unique_source_bins']['zero_count_bins'], 0)


if __name__ == '__main__':
    unittest.main()
