import { eventBus } from '../utils/event-bus.js';
import { apiClient } from '../services/api-client.js';
import { createDiscoveryPanel } from './discovery-panel.js';

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}
const number = (value, digits=2) => Number(value).toLocaleString('en-US',{maximumFractionDigits:digits});

function terrainCanvas(grid, title) {
  const box=el('figure','terrain-preview');
  const canvas=el('canvas'); canvas.width=220; canvas.height=220;
  canvas.setAttribute('aria-label', title + ', relative elevation heatmap');
  const values=grid.flat(), low=Math.min(...values), high=Math.max(...values);
  const ctx=canvas.getContext('2d');
  grid.forEach((row,y)=>row.forEach((v,x)=>{
    const t=(v-low)/(high-low||1);
    ctx.fillStyle=`hsl(${215-180*t} 65% ${25+40*t}%)`;
    ctx.fillRect(x*20,(10-y)*20,20,20);
  }));
  box.append(canvas,el('figcaption','',title),el('small','',`${number(low)} to ${number(high)} m · independent color scale`));
  return box;
}

export function createRightInformationPanel() {
  const aside=el('aside','region-right-panel'); aside.id='right-information-panel';
  aside.setAttribute('aria-label','Scientific analysis and candidate ranking');
  const header=el('header','info-panel-header');
  header.append(el('span','info-platform-tag','PLANETARY ANALOG RESEARCH'),el('h1','info-platform-title','Eksoterris'),el('p','info-platform-subtitle','Real elevation data · reproducible regional screening'));
  const select=el('select','science-select'); select.setAttribute('aria-label','Planetary reference window');
  const runButton=el('button','science-primary','Compare Earth windows'); runButton.type='button'; runButton.disabled=true;
  const status=el('p','science-status','Connecting to scientific backend…'); status.setAttribute('role','status'); status.setAttribute('aria-live','polite');
  header.append(select,runButton,status);
  const body=el('div','info-panel-scroll-body science-body');
  const discovery=createDiscoveryPanel();
  body.append(el('p','science-note','Select a lunar or Martian reference. The baseline engine compares seven predefined Earth regions. The separate discovery section below explores geographically generated candidates.'),discovery);
  aside.append(header,body);
  let currentRun=null, busy=false;
  function section(title) { const node=el('section','info-section-card');node.append(el('h3','info-section-title',title));return node; }
  function showCandidate(candidate) {
    const detail=body.querySelector('#candidate-detail'); if (!detail) return;
    detail.replaceChildren(el('h3','info-section-title',candidate.name));
    detail.append(el('p','science-coordinate',`${candidate.latitude.toFixed(4)}°, ${candidate.longitude.toFixed(4)}° · Earth WGS84 geographic center`));
    const table=el('table','science-table');
    const head=el('tr'); ['Descriptor','Earth','Reference'].forEach(t=>head.append(el('th','',t)));table.append(head);
    Object.entries(currentRun.method.features).forEach(([key,label])=>{
      const row=el('tr'); row.append(el('td','',label),el('td','',number(candidate.features[key],3)),el('td','',number(currentRun.reference.features[key],3)));table.append(row);
    });detail.append(table);
    if(candidate.distance_explanation){
      const breakdown=candidate.distance_explanation;
      detail.append(el('p','science-note',`Distance ${number(breakdown.distance,4)}; largest numerical contribution: ${currentRun.method.features[breakdown.largest_numerical_contributor]}. Contributions describe this formula, not scientific or causal importance.`));
      const expander=el('details','science-breakdown');expander.append(el('summary','','Show IQR scaling and squared-distance contributions'));
      const scroll=el('div','science-table-scroll');const parts=el('table','science-table science-breakdown-table');
      const columns=el('tr');['Descriptor','Earth','Reference','Earth IQR','Scaled Earth − reference','Contribution to distance²'].forEach(label=>columns.append(el('th','',label)));parts.append(columns);
      Object.entries(breakdown.descriptors).forEach(([key,item])=>{
        const row=el('tr');[currentRun.method.features[key],number(item.earth,3),number(item.reference,3),number(item.earth_iqr,3),number(item.scaled_difference,3),number(item.contribution_to_squared_distance,4)].forEach(value=>row.append(el('td','',value)));parts.append(row);
      });scroll.append(parts);expander.append(scroll,el('p','science-note',`Sum of contributions = ${number(breakdown.squared_distance,4)}; its square root is the displayed distance.`));detail.append(expander);
    }
    const maps=el('div','terrain-pair');maps.append(terrainCanvas(candidate.grid_m,'Earth window'),terrainCanvas(currentRun.reference.grid_m,'Reference window'));detail.append(maps);
    detail.append(el('p','science-note','Maps share a 220 km footprint and 20 km cell spacing. Elevation colors use separate ranges.'));
    body.querySelectorAll('[data-candidate]').forEach(n=>n.classList.toggle('is-active',n.dataset.candidate===candidate.id));
  }
  function render(run) {
    currentRun=run;body.replaceChildren(); select.value=run.reference.id;
    discovery.setReference(run.reference.id);
    const ref=section('Seven-site baseline · reference & method');
    const methodSummary = run.method.model
      ? `${run.method.model.algorithm}. Standardized distance: lower is closer; values are unbounded, not probabilities or validated geological analogy scores.`
      : `${run.method.name}. Legacy result; its distance is defined in the saved method metadata and is not directly comparable with KNN runs.`;
    ref.append(el('p','',run.reference.name),el('p','science-note',`${run.reference.latitude.toFixed(3)}°, ${run.reference.longitude.toFixed(3)}° · ${run.reference.source.title}`),el('p','science-note',methodSummary));body.append(ref);
    const support=section('Catalog support');
    support.append(el('p','science-note',`First place means nearest among ${run.candidates.length} available Earth windows. It is not evidence of a validated planetary analog.`));
    if(run.range_diagnostics){
      const diagnostic=run.range_diagnostics;
      support.append(el('p',diagnostic.outside_features.length?'science-caution':'science-note',diagnostic.interpretation));
      Object.entries(diagnostic.descriptors).forEach(([key,item])=>{
        support.append(el('p','science-note',`${run.method.features[key]}: reference ${number(item.reference,3)}; observed Earth range ${number(item.earth_min,3)}–${number(item.earth_max,3)} (${item.position}).`));
      });
    }else support.append(el('p','science-caution','This older saved run has no catalog-range diagnostic. Recompute it before interpreting first place.'));
    body.append(support,discovery);
    const rankings=section('Seven predefined Earth windows');
    run.candidates.forEach(c=>{
      const button=el('button','candidate-row'); button.type='button';button.dataset.candidate=c.id;
      button.append(el('span','candidate-rank',String(c.rank)),el('span','candidate-name',c.name),el('strong','candidate-distance',c.distance.toFixed(4)));
      button.addEventListener('click',()=>{showCandidate(c);eventBus.emit('science:focus-candidate',c);});rankings.append(button);
    });body.append(rankings);
    const detail=section('Candidate details');detail.id='candidate-detail';body.append(detail);showCandidate(run.candidates[0]);
    const sensitivity=section('Sensitivity check');
    Object.entries(run.sensitivity).forEach(([key,id])=>sensitivity.append(el('p','science-note',`Without ${run.method.features[key]}: ${run.candidates.find(c=>c.id===id)?.name || id} ranks first.`)));body.append(sensitivity);
    if(run.sensitivity_analysis){
      const report=run.sensitivity_analysis;
      sensitivity.append(el('p','science-note','Scenario rankings test selected assumptions; winner frequency is not a probability. Distances under different feature subsets are not directly comparable.'));
      const scenarios=el('details','science-breakdown');scenarios.append(el('summary','',`Inspect ${report.scenarios.length} descriptor, catalog and window scenarios`));
      report.scenarios.forEach(s=>{
        const item=el('details','science-scenario');item.append(el('summary','',`${s.name}: ${s.winner || 'unavailable'}${s.top_three_overlap_count===undefined?'':` · top-three overlap ${s.top_three_overlap_count}/${s.top_three_comparison_size}`}`));
        item.append(el('p','science-note',s.assumption_changed));
        if(s.status==='unavailable')item.append(el('p','science-caution',s.reason));
        else item.append(el('p','science-note',`Full ranking: ${s.ranking.map(r=>`${r.rank}. ${r.id} (${number(r.distance,4)})`).join('; ')}. Spearman on shared candidates: ${s.shared_candidate_spearman_rho===null?'undefined':number(s.shared_candidate_spearman_rho,3)}. Distance changes from baseline: ${Object.entries(s.distance_change_from_baseline).map(([id,v])=>`${id} ${v>=0?'+':''}${number(v,4)}`).join('; ')}.`));
        scenarios.append(item);
      });sensitivity.append(scenarios);
      if(report.quality_scenarios?.status==='unavailable')sensitivity.append(el('p','science-note',`Quality perturbation unavailable: ${report.quality_scenarios.reason}`));
      if(report.quality_scenarios?.status==='no_effect')sensitivity.append(el('p','science-note',`MOLA shot-support check: ${report.quality_scenarios.reason}`));
    }
    if(run.data_quality){
      const quality=section('Source quality and scale');
      quality.append(el('p','science-note',`${run.data_quality.reference.product}: native equatorial grid spacing ~${number(run.data_quality.reference.native_grid_spacing_km_at_equator,2)} km. ${run.data_quality.reference.coverage_note}`));
      run.data_quality.reference.warnings.forEach(message=>quality.append(el('p','science-note',message)));
      const coverage=run.data_quality.reference.observation_coverage;
      if(coverage)quality.append(el('p','science-note',`MOLA source-bin observations: ${coverage.bins_with_at_least_one_shot}/${coverage.source_bins_touched} sampled bins contain at least one shot; ${coverage.bins_with_no_shots} have no shots. This does not measure elevation uncertainty or validate interpolated output cells.`));
      quality.append(el('p','science-note',`${run.data_quality.earth.product}: ${run.data_quality.earth.effective_resolution}`));body.append(quality);
    }
    const ai=section('Evidence-based AI interpretation');
    const aiText=el('p','science-note','Gemini selects computed evidence identifiers. Response validation does not establish scientific analog validity.');
    const aiButton=el('button','science-secondary','Explain with Gemini');aiButton.type='button';
    aiButton.addEventListener('click',async()=>{
      aiButton.disabled=true;aiText.textContent='Requesting and validating Gemini evidence selections…';
      try { const result=await apiClient.interpret(run.run_id);aiText.textContent=result.explanation;ai.append(el('small','science-note',`Validated ${result.provider} response · ${result.model}`)); }
      catch(e) { aiText.textContent=e.message; }
      finally { aiButton.disabled=false; }
    });ai.append(aiText,aiButton);body.append(ai);
    apiClient.cachedInterpretation(run.run_id).then(result=>{if(currentRun?.run_id===run.run_id)aiText.textContent=`Saved validated Gemini selection: ${result.explanation}`;}).catch(()=>{});
    if(run.winner_climate.annual){
      const climate=section('NASA POWER · top candidate context');
      for(const [key,value] of Object.entries(run.winner_climate.annual)){
        const p=run.winner_climate.provenance.parameters[key];
        climate.append(el('p','science-note',`${p?.longname||key}: ${number(value)} ${p?.units||''}`));
      }climate.append(el('p','science-note','Earth climatology only; not used in the planetary distance.'));body.append(climate);
    }
    const sources=section('Sources & reproducibility');
    const provenance=[run.reference.source,...run.candidates.map(c=>c.source)];
    if(run.winner_climate.provenance)provenance.push(run.winner_climate.provenance);
    provenance.forEach(p=>{
      const item=el('details','source-record');item.append(el('summary','',p.title));
      const a=el('a','', 'Open exact source request');a.href=p.url;a.target='_blank';a.rel='noopener noreferrer';
      item.append(a,el('p','science-note',p.note||p.datum||''),el('code','source-checksum',`SHA256 ${p.sha256}`),el('small','',`Retrieved ${p.retrieved_at}`));sources.append(item);
    });
    const download=el('a','science-secondary','Download reproducible result (JSON)');download.href=`/api/runs/${run.run_id}/download`;sources.append(download);
    const catalogBtn=el('button','science-secondary','Inspect NASA SRTM catalog');catalogBtn.type='button';
    catalogBtn.addEventListener('click',async()=>{catalogBtn.disabled=true;try{
      const [catalog,granules]=await Promise.all([apiClient.srtm(),apiClient.srtmGranules(run.candidates[0].latitude,run.candidates[0].longitude)]);
      sources.append(el('p','science-note',`${catalog.collections.map(c=>c.title).join('; ')}. ${granules.granules.length} SRTMGL1 tiles found near the top candidate. Links require Earthdata Login for download; the current KNN uses NOAA ETOPO1.`));
      granules.granules.forEach(g=>{const a=el('a','science-note',g.title);a.href=g.download_links[0]||'#';a.target='_blank';a.rel='noopener noreferrer';sources.append(a);});
    }catch(e){sources.append(el('p','science-note',e.message));}finally{catalogBtn.disabled=false;}});sources.append(catalogBtn);
    sources.append(el('small','science-note',`Run ${run.run_id} · ${run.method_version} · computed ${run.computed_at}`));body.append(sources);
    const limitations=section('Scope & limitations');const list=el('ul','science-limitations');run.limitations.forEach(t=>list.append(el('li','',t)));limitations.append(list);
    if(run.excluded.length)limitations.append(el('p','science-note',`${run.excluded.length} windows could not be evaluated; see the exported error details.`));body.append(limitations);
    eventBus.emit('science:results',run);
  }
  runButton.addEventListener('click',async()=>{
    if(busy)return;busy=true;runButton.disabled=true;select.disabled=true;
    status.textContent='Acquiring official elevation files and computing regional features…';
    try {
      const job=await apiClient.analyze(select.value);
      for(let attempt=0;attempt<450;attempt++){
        await new Promise(resolve=>setTimeout(resolve,2000));
        const state=await apiClient.job(job.job_id);
        if(state.status==='failed')throw new Error(state.error);
        if(state.status==='completed'){const run=await apiClient.run(state.run_id);render(run);status.textContent=`Completed · ${run.candidates.length} Earth windows · real data`;return;}
      }throw new Error('Analysis is still running. Reload later to inspect saved runs.');
    }catch(e){status.textContent=e.message;}finally{busy=false;runButton.disabled=false;select.disabled=false;}
  });
  select.addEventListener('change',()=>{
    discovery.setReference(select.value);
    status.textContent='Reference selected. Compare Earth windows to update the seven-site baseline.';
  });
  eventBus.on('science:select-candidate',({id})=>{const c=currentRun?.candidates.find(c=>c.id===id);if(c)showCandidate(c);});
  eventBus.on('globe:ready',()=>{if(currentRun)eventBus.emit('science:results',currentRun);});
  eventBus.on('profile:select',({profileId})=>{if(busy)return;if(profileId==='moon_reference')select.value='moon-tranquillitatis';if(profileId==='mars_reference')select.value='mars-jezero';});
  (async()=>{
    try {
      const [catalog,health,runs]=await Promise.all([apiClient.catalog(),apiClient.health(),apiClient.runs()]);
      catalog.targets.forEach(t=>{const o=el('option','',t.name);o.value=t.id;select.append(o);});select.value='mars-jezero';runButton.disabled=false;
      status.textContent=health.gemini_configured?'Backend connected · Gemini configured':'Backend connected · start it with GEMINI_API_KEY to enable AI';
      if(runs.length){render(await apiClient.run(runs[0].run_id));status.textContent='Showing a saved computation from verified source files. Recompute to repeat the pipeline.';}
    }catch(e){status.textContent=`Backend unavailable. Start start-backend.ps1. ${e.message}`;}
  })();
  return aside;
}
