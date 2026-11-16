"""API contracts for immutable experimental catalogs and Earth evidence."""

import hashlib
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app import app
from platform_results import RESULTS, characterization
from gemini_interpreter import GeminiResponseError, interpret_regional_evidence


class PlatformResultsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_experiments_keep_separate_counts_and_calibrations(self):
        response = self.client.get('/api/discovery/experiments')
        self.assertEqual(response.status_code, 200)
        manifest = response.json()
        self.assertEqual([entry['eligible_count'] for entry in manifest['experiments']], [26, 64, 69])
        self.assertEqual(manifest['experiments'][0]['generated_count'], 49)
        self.assertEqual(manifest['experiments'][0]['excluded_count'], 23)
        self.assertEqual(manifest['baseline']['kind'], 'separate production baseline')
        self.assertIn('separately', manifest['experiments'][1]['calibration'])

    def test_saved_winners_and_hashes_are_unchanged(self):
        paths = {
            'west-africa-49': 'terrestrial-discovery/rankings.json',
            'expanded-64': 'terrestrial-discovery-expansion-v1/combined.json',
            'shifted-69': 'terrestrial-discovery-characterization-v1/combined-shifted.json',
        }
        for experiment, relative in paths.items():
            raw = (RESULTS / relative).read_bytes()
            for reference in ('moon-tranquillitatis', 'moon-tycho', 'mars-jezero', 'mars-gale'):
                with self.subTest(experiment=experiment, reference=reference):
                    response = self.client.get(f'/api/discovery/experiments/{experiment}/references/{reference}')
                    self.assertEqual(response.status_code, 200)
                    result = response.json()
                    self.assertEqual(result['ranking_sha256'], hashlib.sha256(raw).hexdigest())
                    self.assertEqual(result['ranking'][0]['rank'], 1)
                    self.assertEqual(len(result['ranking']), {'west-africa-49': 26, 'expanded-64': 64, 'shifted-69': 69}[experiment])
                    self.assertEqual(result['range_diagnostics']['catalog_size'], len(result['ranking']))
                    self.assertEqual(set(result['earth_iqr']), {'relief_m', 'median_slope_deg', 'detrended_rms_m'})

    def test_unknown_experiment_and_report_rejected(self):
        self.assertEqual(self.client.get('/api/discovery/experiments/../../references/mars-jezero').status_code, 404)
        self.assertEqual(self.client.get('/api/discovery/experiments/unlisted/references/mars-jezero').status_code, 404)
        self.assertEqual(self.client.get('/api/reports/unlisted').status_code, 404)

    def test_characterization_is_real_and_marks_unavailable_data(self):
        response = self.client.get('/api/discovery/characterization')
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(len(result['evidence']['evidence']), 5)
        self.assertEqual(result['evidence']['dataset_status']['jrc_gsw_v1_5'], 'acquired_and_processed')
        self.assertIn('not available', result['evidence']['dataset_status']['nasadem_hgt_v001'])
        self.assertEqual(result['comparisons']['references']['moon-tycho']['analog_validation'], 'not_established')
        self.assertEqual(self.client.get('/api/reports/regional-characterization').status_code, 200)

    def test_regional_interpretation_requires_selection_and_optional_key(self):
        payload = {'reference_id': 'moon-tranquillitatis',
                   'evidence_id': 'south-america-elevation-gradient-r02-c04'}
        wrong = self.client.post('/api/discovery/interpret', json={**payload, 'reference_id': 'moon-tycho'})
        self.assertEqual(wrong.status_code, 422)
        with patch.dict(os.environ, {'GEMINI_API_KEY': ''}):
            response = self.client.post('/api/discovery/interpret', json=payload)
        self.assertEqual(response.status_code, 422)
        self.assertIn('GEMINI_API_KEY', response.json()['detail'])

    def test_regional_gemini_only_orders_saved_facts(self):
        bundle = characterization()
        evidence_id = 'south-america-elevation-gradient-r02-c04'
        response = SimpleNamespace(
            candidates=[SimpleNamespace(finish_reason=SimpleNamespace(value='STOP'))],
            text=json.dumps({'evidence_ids': ['missing_evidence', 'screening', 'historical_water', 'modeled_climate']}),
            model_version='test-model')
        client = MagicMock()
        client.__enter__.return_value.models.generate_content.return_value = response
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'local-test-placeholder'}), patch('gemini_interpreter.genai.Client', return_value=client):
            result = interpret_regional_evidence('moon-tranquillitatis', evidence_id, bundle)
        self.assertEqual(result['provider'], 'Gemini')
        self.assertIn('1984', result['explanation'])
        self.assertIn('not establish planetary analog validity', result['limitation'])
        self.assertIn('NASADEM elevation was unavailable', result['explanation'])
        response.text = json.dumps({'evidence_ids': ['screening', 'screening', 'historical_water', 'modeled_climate']})
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'local-test-placeholder'}), patch('gemini_interpreter.genai.Client', return_value=client):
            with self.assertRaises(GeminiResponseError):
                interpret_regional_evidence('moon-tranquillitatis', evidence_id, bundle)


if __name__ == '__main__':
    unittest.main()
