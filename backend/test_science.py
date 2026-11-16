import unittest
from types import SimpleNamespace
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import app
import numpy as np
from science import features, compare, coordinates, RADIUS
from sources import Raster, ScientificRedirectHandler, srtm_tile_origin
from urllib.request import Request
from gemini_interpreter import GeminiResponseError, interpret, validate_selection
from terrain_knn import TerrainKNN

class ScienceTests(unittest.TestCase):
    def test_flat_surface(self):
        f=features(np.ones((11,11))*100)
        self.assertAlmostEqual(f['relief_m'],0)
        self.assertAlmostEqual(f['median_slope_deg'],0)
        self.assertLess(f['detrended_rms_m'],1e-10)
    def test_known_planar_slope(self):
        z=np.tile(np.arange(11)*20000*0.1,(11,1))
        f=features(z)
        self.assertAlmostEqual(f['median_slope_deg'],np.degrees(np.arctan(0.1)),places=8)
        self.assertLess(f['detrended_rms_m'],1e-8)
    def test_vertical_datum_invariance(self):
        z=np.random.default_rng(12).normal(0,200,(11,11))
        distance,_=compare(features(z),features(z+1737400))
        self.assertLess(distance,1e-10)
    def test_reject_missing_values(self):
        z=np.zeros((11,11));z[5,5]=np.nan
        with self.assertRaises(ValueError):features(z)
    def test_distance_symmetry_and_bounds(self):
        a=features(np.random.default_rng(1).normal(0,300,(11,11)))
        b=features(np.random.default_rng(2).normal(0,20,(11,11)))
        self.assertEqual(compare(a,b)[0],compare(b,a)[0])
        self.assertTrue(0<=compare(a,b)[0]<=1)
        self.assertEqual(compare(a,a)[0],0)
    def test_bilinear_sample(self):
        r=Raster([[0,10],[20,30]],[0,1],[0,1],{})
        self.assertEqual(float(r.sample(.5,.5)),15)
    def test_body_radius_changes_angular_footprint(self):
        _,earth=coordinates(0,0,20000,0,RADIUS['earth'])
        _,moon=coordinates(0,0,20000,0,RADIUS['moon'])
        self.assertGreater(moon,earth)
        self.assertAlmostEqual(earth,np.degrees(20000/RADIUS['earth']))
    def test_invalid_coordinate_grid_rejected(self):
        with self.assertRaises(ValueError): Raster([[0,1],[2,3]],[1,0],[0,1],{})
    def test_longitude_wrap(self):
        r=Raster([[0,1,2,3],[0,1,2,3]],[-1,1],[45,135,225,315],{},True)
        self.assertEqual(float(r.sample(0,-45)),float(r.sample(0,315)))
        self.assertAlmostEqual(float(r.sample(0,0)),1.5)
    def test_ai_rejects_nested_values(self):
        selection={'candidate_id':'a','evidence_ids':['ranking',{}],'limitation_ids':['scope','resolution','method']}
        with self.assertRaises(ValueError): validate_selection(selection,{'ranking':'x','sensitivity':'y'},{'candidates':[{'id':'a'}]})
    def test_knn_ranking_and_earth_only_scale(self):
        samples=[{'id':'far','features':{'relief_m':100,'median_slope_deg':10,'detrended_rms_m':50}},
                 {'id':'near','features':{'relief_m':2,'median_slope_deg':1,'detrended_rms_m':3}},
                 {'id':'middle','features':{'relief_m':50,'median_slope_deg':5,'detrended_rms_m':20}}]
        model=TerrainKNN(('relief_m','median_slope_deg','detrended_rms_m')).fit(samples)
        before=model.scale.copy()
        results=model.query({'relief_m':2,'median_slope_deg':1,'detrended_rms_m':3})
        self.assertEqual(results[0],('near',0.0))
        np.testing.assert_array_equal(model.scale,before)
        self.assertEqual(model.metadata()['labels_used'],False)
    def test_knn_rejects_missing_and_zero_dispersion(self):
        with self.assertRaises(ValueError): TerrainKNN(('a',)).fit([{'id':'x','features':{'a':1}},{'id':'y','features':{'a':1}}])
        model=TerrainKNN(('a',)).fit([{'id':'x','features':{'a':1}},{'id':'y','features':{'a':2}}])
        with self.assertRaises(ValueError): model.query({'a':float('nan')})
    def test_earthdata_token_not_forwarded_to_other_hosts(self):
        request=Request('https://data.lpdaac.earthdatacloud.nasa.gov/file',headers={'Authorization':'Bearer placeholder'})
        redirected=ScientificRedirectHandler().redirect_request(request,None,302,'Found',{},'https://example.org/file')
        self.assertFalse(redirected.has_header('Authorization'))
    def test_earthdata_token_not_forwarded_over_http(self):
        request=Request('https://data.lpdaac.earthdatacloud.nasa.gov/file',headers={'Authorization':'Bearer placeholder'})
        redirected=ScientificRedirectHandler().redirect_request(request,None,302,'Found',{},'http://urs.earthdata.nasa.gov/file')
        self.assertFalse(redirected.has_header('Authorization'))
    def test_srtm_tile_origin_accepts_lp_daac_name(self):
        self.assertEqual(srtm_tile_origin('S25W070.SRTMGL1.hgt'),(-25,-70))
        self.assertEqual(srtm_tile_origin('N35W112.hgt'),(35,-112))
        with self.assertRaises(ValueError): srtm_tile_origin('N35W112.other.hgt')
    def test_gemini_rejects_malformed_provider_response(self):
        names=('relief_m','median_slope_deg','detrended_rms_m')
        run={'candidates':[{'id':'earth','name':'Earth window','features':dict.fromkeys(names,1.0),'distance':0.1}],
             'reference':{'features':dict.fromkeys(names,2.0)},
             'sensitivity':dict.fromkeys(names,'earth'),
             'limitations':['scope','resolution','method']}
        response=SimpleNamespace(candidates=[SimpleNamespace(finish_reason=SimpleNamespace(value='STOP'))],text='{"invented": 42}')
        with patch.dict('os.environ',{'GEMINI_API_KEY':'placeholder'}), patch('gemini_interpreter.genai.Client') as client:
            client.return_value.__enter__.return_value.models.generate_content.return_value=response
            with self.assertRaises(GeminiResponseError): interpret(run)
    def test_invalid_gemini_response_is_provider_failure(self):
        with patch('app.get_run',return_value={}), patch('app.interpret',side_effect=GeminiResponseError('invalid')):
            response=TestClient(app).post('/api/runs/0123456789abcdef/interpret')
        self.assertEqual(response.status_code,502)
        self.assertIn('invalid or incomplete',response.json()['detail'])
    def test_ai_cannot_change_winner(self):
        run={'candidates':[{'id':'a'}]}
        selection={'candidate_id':'invented','evidence_ids':['ranking','sensitivity'],'limitation_ids':['scope','resolution','method']}
        with self.assertRaises(ValueError): validate_selection(selection,{'ranking':'x','sensitivity':'y'},run)
    def test_ai_cannot_invent_evidence(self):
        run={'candidates':[{'id':'a'}]}
        selection={'candidate_id':'a','evidence_ids':['ranking','sensitivity','new-measurement'],'limitation_ids':['scope','resolution','method']}
        with self.assertRaises(ValueError): validate_selection(selection,{'ranking':'x','sensitivity':'y'},run)

if __name__=='__main__':unittest.main()
