"""Local API for the Eksoterris research prototype."""
import json
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sources import DATA, srtm_catalog, srtm_granules, sample_srtm
from science import TARGETS, CANDIDATES, FEATURES, LIMITATIONS, analyze, load_run
from gemini_interpreter import GeminiResponseError, interpret, interpret_regional_evidence
from platform_results import ROOT, REPORTS, experiment_index, experiment_reference, characterization

app = FastAPI(title='Eksoterris Scientific API', version='1.0.0')
app.add_middleware(CORSMiddleware, allow_origins=[f'http://{h}:{p}' for h in ('localhost','127.0.0.1') for p in (5173,5174,5175)], allow_methods=['GET','POST'],allow_headers=['Content-Type'])
pool = ThreadPoolExecutor(max_workers=1)
jobs = {}
lock = threading.Lock()

class AnalysisRequest(BaseModel):
    target_id: str

class RegionalInterpretationRequest(BaseModel):
    reference_id: str
    evidence_id: str

@app.get('/api/health')
def health():
    return {'status':'ok','gemini_configured':bool(os.getenv('GEMINI_API_KEY')),'model':os.getenv('GEMINI_MODEL','gemini-3.5-flash-lite')}

@app.get('/api/catalog')
def catalog():
    return {'targets':list(TARGETS.values()),'earth_windows':CANDIDATES,'features':FEATURES,'limitations':LIMITATIONS}

@app.get('/api/discovery/experiments')
def discovery_experiments():
    return experiment_index()

@app.get('/api/discovery/experiments/{experiment_id}/references/{reference_id}')
def discovery_reference(experiment_id: str, reference_id: str):
    try: return experiment_reference(experiment_id, reference_id)
    except KeyError as exc: raise HTTPException(404, str(exc)) from exc

@app.get('/api/discovery/characterization')
def discovery_characterization():
    return characterization()

@app.post('/api/discovery/interpret')
def discovery_interpretation(request: RegionalInterpretationRequest):
    bundle = characterization()
    reference = bundle['comparisons']['references'].get(request.reference_id)
    if not reference or request.evidence_id not in reference['earth_context_evidence_ids']:
        raise HTTPException(422, 'This Earth region is not selected for this planetary reference.')
    try: return interpret_regional_evidence(request.reference_id, request.evidence_id, bundle)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    except GeminiResponseError as exc:
        raise HTTPException(502, 'Gemini returned an invalid evidence selection; acquired data remain available.') from exc
    except Exception as exc:
        code = getattr(exc, 'code', None)
        message = 'Gemini is temporarily unavailable; acquired data remain available.'
        if code in (401, 403): message = 'Gemini authentication or project permission failed.'
        if code == 429: message = 'Gemini quota reached. Check the project quota before retrying.'
        raise HTTPException(502, message) from exc

@app.get('/api/reports/{report_id}')
def research_report(report_id: str):
    if report_id not in REPORTS: raise HTTPException(404, 'Report not found.')
    return FileResponse(ROOT / REPORTS[report_id], media_type='text/markdown')

@app.get('/api/sources/srtm')
def srtm():
    try: return srtm_catalog()
    except Exception as exc: raise HTTPException(502, str(exc)) from exc

@app.get('/api/sources/srtm/granules')
def granules(latitude: float, longitude: float):
    try: return srtm_granules(latitude,longitude)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    except Exception as exc: raise HTTPException(502,str(exc)) from exc

@app.get('/api/sources/srtm/sample')
def srtm_sample(latitude: float, longitude: float):
    try: return sample_srtm(latitude,longitude)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    except Exception as exc: raise HTTPException(502,'SRTM download failed; check Earthdata authorization and tile availability.') from exc

def execute_job(job_id, target_id):
    jobs[job_id] = {'status':'running','target_id':target_id}
    try:
        run = analyze(target_id)
        jobs[job_id] = {'status':'completed','run_id':run['run_id'],'target_id':target_id}
    except Exception as exc:
        jobs[job_id] = {'status':'failed','error':str(exc),'target_id':target_id}

@app.post('/api/analyses', status_code=202)
def create_analysis(request: AnalysisRequest):
    if request.target_id not in TARGETS: raise HTTPException(422,'Unknown reference window.')
    with lock:
        active = next(((i,j) for i,j in jobs.items() if j['status'] in ('queued','running')),None)
        if active:
            if active[1]['target_id'] == request.target_id: return {'job_id':active[0]}
            raise HTTPException(409,'Another analysis is running; wait for it to finish.')
        if len(jobs)>50:
            jobs.clear()
        job_id = uuid.uuid4().hex
        jobs[job_id] = {'status':'queued','target_id':request.target_id}
        pool.submit(execute_job,job_id,request.target_id)
    return {'job_id':job_id}

@app.get('/api/jobs/{job_id}')
def get_job(job_id: str):
    if job_id not in jobs: raise HTTPException(404,'Job not found.')
    return jobs[job_id]

@app.get('/api/runs')
def list_runs():
    results=[]
    for path in sorted(DATA.glob('run-*.json'), key=lambda p:p.stat().st_mtime,reverse=True):
        r=json.loads(path.read_text(encoding='utf-8'))
        results.append({'run_id':r['run_id'],'target':r['reference']['name'],'target_id':r['reference']['id'],'computed_at':r['computed_at']})
    return results

@app.get('/api/runs/{run_id}')
def get_run(run_id: str):
    try: return load_run(run_id)
    except (ValueError,FileNotFoundError) as exc: raise HTTPException(404,'Run not found.') from exc

@app.get('/api/runs/{run_id}/download')
def download(run_id: str):
    get_run(run_id)
    return FileResponse(DATA/f'run-{run_id}.json',media_type='application/json',filename=f'eksoterris-{run_id}.json')

@app.post('/api/runs/{run_id}/interpret')
def interpretation(run_id: str):
    run=get_run(run_id)
    try:
        result=interpret(run)
        (DATA/f'interpretation-{run_id}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        return result
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    except GeminiResponseError as exc:
        raise HTTPException(502,'Gemini returned an invalid or incomplete evidence response; computed results remain valid.') from exc
    except Exception as exc:
        # Never return provider request headers or credentials.
        code=getattr(exc,'code',None)
        message='Gemini is temporarily unavailable; computed results remain valid.'
        if code in (401,403): message='Gemini authentication or project permission failed.'
        if code==429: message='Gemini quota reached. Check the project quota before retrying.'
        raise HTTPException(502,message) from exc

@app.get('/api/runs/{run_id}/interpretation')
def cached_interpretation(run_id: str):
    get_run(run_id)
    path=DATA/f'interpretation-{run_id}.json'
    if not path.exists(): raise HTTPException(404,'No verified Gemini interpretation has been saved.')
    return json.loads(path.read_text(encoding='utf-8'))
