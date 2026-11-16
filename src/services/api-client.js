export class ApiClient {
  constructor(){this.baseUrl=import.meta.env.VITE_API_BASE_URL || '/api';}
  async request(path,options={}){
    const response=await fetch(this.baseUrl+path,{...options,headers:{'Content-Type':'application/json',...options.headers},signal:AbortSignal.timeout(180000)});
    const data=await response.json();
    if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:`Request failed (${response.status})`);
    return data;
  }
  health(){return this.request('/health');}
  catalog(){return this.request('/catalog');}
  discoveryExperiments(){return this.request('/discovery/experiments');}
  discoveryReference(experimentId, referenceId){return this.request(`/discovery/experiments/${encodeURIComponent(experimentId)}/references/${encodeURIComponent(referenceId)}`);}
  characterization(){return this.request('/discovery/characterization');}
  interpretRegion(reference_id,evidence_id){return this.request('/discovery/interpret',{method:'POST',body:JSON.stringify({reference_id,evidence_id})});}
  runs(){return this.request('/runs');}
  run(id){return this.request(`/runs/${id}`);}
  analyze(target_id){return this.request('/analyses',{method:'POST',body:JSON.stringify({target_id})});}
  job(id){return this.request(`/jobs/${id}`);}
  interpret(id){return this.request(`/runs/${id}/interpret`,{method:'POST'});}
  cachedInterpretation(id){return this.request(`/runs/${id}/interpretation`);}
  srtm(){return this.request('/sources/srtm');}
  srtmGranules(latitude,longitude){return this.request(`/sources/srtm/granules?latitude=${encodeURIComponent(latitude)}&longitude=${encodeURIComponent(longitude)}`);}
}
export const apiClient=new ApiClient();
