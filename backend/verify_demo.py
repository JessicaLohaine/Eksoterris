"""HTTP integration check using actual source bytes, possibly from the verified cache."""
import argparse
import hashlib
import json
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import numpy as np
from science import FEATURES, TARGETS, features
from terrain_knn import TerrainKNN
from sources import DATA


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8000')
    parser.add_argument('--gemini',action='store_true',help='Require a live Gemini response')
    args=parser.parse_args()
    checks=[]
    def request(path,body=None,expected=200):
        data=json.dumps(body).encode() if body is not None else None
        req=Request(args.url+path,data=data,headers={'Content-Type':'application/json'})
        try:
            with urlopen(req,timeout=180) as response:
                status=response.status; payload=json.load(response)
        except HTTPError as exc:
            status=exc.code; payload=json.load(exc)
        assert status==expected,(path,status,payload)
        return payload
    health=request('/api/health')
    assert health['status']=='ok'
    assert len(request('/api/catalog')['targets'])==4
    request('/api/analyses',{'target_id':'unknown'},422)
    request('/api/runs/invalid',expected=404)
    checks.append('API health, catalog and invalid-input handling')
    runs=[]
    baseline={'moon-tranquillitatis':('colorado-plateau',0.4354883112),
              'moon-tycho':('atacama',2.2923108590),
              'mars-jezero':('atacama',0.7217655570),
              'mars-gale':('atacama',2.2567657900)}
    for target in TARGETS:
        job=request('/api/analyses',{'target_id':target},202)
        deadline=time.monotonic()+600
        while time.monotonic()<deadline:
            state=request('/api/jobs/'+job['job_id'])
            if state['status'] in ('failed','completed'):break
            time.sleep(1)
        assert state['status']=='completed',state
        run=request('/api/runs/'+state['run_id'])
        assert len(run['candidates'])==7 and not run['excluded']
        assert run['reference']['id']==target
        reference=features(run['reference']['grid_m'])
        distances=[]
        for c in run['candidates']:
            actual=features(c['grid_m'])
            for key in FEATURES: assert np.isclose(actual[key],c['features'][key],rtol=1e-12)
            distances.append(c['distance'])
        model=TerrainKNN(FEATURES).fit(run['candidates'])
        computed=dict(model.query(reference))
        for c in run['candidates']:
            assert np.isclose(computed[c['id']],c['distance'],rtol=1e-12)
        assert run['method']['model']==model.metadata()
        assert distances==sorted(distances)
        assert run['candidates'][0]['id']==baseline[target][0]
        assert np.isclose(distances[0],baseline[target][1],rtol=0,atol=1e-7), 'Baseline distance changed; inspect source versions and methodology.'
        diagnostic=run['range_diagnostics']
        outside=[]
        for key in FEATURES:
            values=[c['features'][key] for c in run['candidates']]
            item=diagnostic['descriptors'][key]
            assert item['earth_min']==min(values) and item['earth_max']==max(values)
            if not min(values)<=reference[key]<=max(values):outside.append(key)
        assert diagnostic['outside_features']==outside
        assert (diagnostic['status']=='insufficient_catalog_evidence')==bool(outside)
        for c in run['candidates']:
            breakdown=c['distance_explanation']
            assert np.isclose(breakdown['distance'],c['distance'],rtol=1e-12)
            assert np.isclose(sum(item['contribution_to_squared_distance'] for item in breakdown['descriptors'].values()),
                              c['distance']**2,rtol=1e-12)
        report=run['sensitivity_analysis']
        assert [item['id'] for item in report['baseline']['ranking']]==[item['id'] for item in run['candidates']]
        assert len(report['scenarios'])==34 and all(item.get('winner') for item in report['scenarios'])
        assert run['data_quality']['reference']['finite_output_cells']==121
        assert run['data_quality']['earth']['finite_regional_grids']
        assert all(run['sensitivity'][name]==model.query(reference,omitted=name)[0][0] for name in FEATURES)
        for source in [run['reference']['source'],run['reference']['source']['label']]+[c['source'] for c in run['candidates']]:
            prefix=hashlib.sha256(source['url'].encode()).hexdigest()
            raw=next(p for p in DATA.glob(prefix+'.*') if not p.name.endswith('.meta.json'))
            assert hashlib.sha256(raw.read_bytes()).hexdigest()==source['sha256']
        exported=request('/api/runs/'+run['run_id']+'/download')
        assert exported==run
        print(f"PASS {target}: {run['candidates'][0]['id']} distance={distances[0]:.6f}, run={run['run_id']}",flush=True)
        checks.append(f'{target}: acquisition, checksums, feature reproduction, ranking, export')
        runs.append(run)
    cmr=request('/api/sources/srtm')
    assert cmr['collections'] and all(c['id'] for c in cmr['collections'])
    checks.append('NASA Earthdata CMR SRTMGL1 collection metadata, live or checksum-verified cached response')
    granules=request('/api/sources/srtm/granules?latitude=-24.5&longitude=-69')
    assert granules['granules'] and all(g['download_links'] for g in granules['granules'])
    assert all('data.lpdaac.earthdatacloud.nasa.gov' in url for g in granules['granules'] for url in g['download_links'])
    checks.append('SRTMGL1 v003 granule discovery and LP DAAC links, live or checksum-verified cached response')
    if args.gemini:
        assert health['gemini_configured'],'Configure GEMINI_API_KEY in the backend process first.'
        ai=request('/api/runs/'+runs[-1]['run_id']+'/interpret',{})
        assert ai['status']=='verified' and ai['provider']=='Gemini'
        assert request('/api/runs/'+runs[-1]['run_id']+'/interpretation')==ai
        checks.append('Live Gemini structured response, evidence validation and saved interpretation')
    elif not health['gemini_configured']:
        request('/api/runs/'+runs[0]['run_id']+'/interpret',{},422)
        checks.append('Missing Gemini credential fails explicitly; live Gemini remains untested')
    report={'checks':checks,'run_ids':[r['run_id'] for r in runs],'live_gemini_tested':args.gemini}
    (DATA/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
