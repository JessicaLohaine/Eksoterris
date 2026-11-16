import { apiClient } from '../services/api-client.js';
import { eventBus } from '../utils/event-bus.js';

const REFERENCE_NAMES = {
  'moon-tranquillitatis': 'Moon · Mare Tranquillitatis',
  'moon-tycho': 'Moon · Tycho',
  'mars-jezero': 'Mars · Jezero',
  'mars-gale': 'Mars · Gale'
};
const FEATURE_NAMES = {
  relief_m: 'P95–P5 elevation range (m)',
  median_slope_deg: 'Median slope (°)',
  detrended_rms_m: 'Detrended RMS relief (m)'
};
const fmt = (value, digits = 3) => Number(value).toLocaleString('en-US', { maximumFractionDigits: digits });

function element(tag, className, value) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (value !== undefined) node.textContent = value;
  return node;
}
function paragraph(parent, value, className = 'science-note') {
  parent.append(element('p', className, value));
}
function link(parent, label, href) {
  const anchor = element('a', 'science-report-link', label);
  anchor.href = href;
  anchor.target = '_blank';
  anchor.rel = 'noopener noreferrer';
  parent.append(anchor);
}
function featureTable(candidate, reference, breakdown) {
  const scroll = element('div', 'science-table-scroll');
  const table = element('table', 'science-table science-breakdown-table');
  const head = element('tr');
  const headings = ['Descriptor', 'Earth', 'Reference'];
  if (breakdown) headings.push('Earth IQR', 'Scaled difference', 'Squared contribution');
  headings.forEach(label => head.append(element('th', '', label)));
  table.append(head);
  for (const [key, label] of Object.entries(FEATURE_NAMES)) {
    const part = breakdown?.descriptors?.[key];
    const row = element('tr');
    const cells = [label, fmt(candidate.features[key]), fmt(reference.features[key])];
    if (breakdown) cells.push(fmt(part.earth_iqr), fmt(part.scaled_difference), fmt(part.contribution_to_squared_distance, 4));
    cells.forEach(value => row.append(element('td', '', value)));
    table.append(row);
  }
  scroll.append(table);
  return scroll;
}

/** One panel for saved research catalogs; it does not recompute or merge their rankings. */
export function createDiscoveryPanel() {
  const root = element('section', 'info-section-card discovery-panel');
  root.id = 'discovery-panel';
  root.append(element('h3', 'info-section-title', 'Discover and investigate'));
  paragraph(root, 'Eksoterris screens measured elevation in bounded Earth regions against Moon and Mars reference windows. Generated centers are exploratory search results, not confirmed planetary analogs.');
  paragraph(root, 'Earth globe: cyan/gold marks the seven-site baseline; green/orange marks generated centers. The orange outline marks a selected analyzed footprint.');
  const experimentLabel = element('label', 'science-field-label', 'Candidate population');
  const experimentSelect = element('select', 'science-select');
  experimentSelect.setAttribute('aria-label', 'Select a separately calibrated candidate population');
  experimentLabel.append(experimentSelect);
  const referenceLabel = element('label', 'science-field-label', 'Planetary reference');
  const referenceSelect = element('select', 'science-select');
  referenceSelect.setAttribute('aria-label', 'Select planetary discovery reference');
  for (const [id, name] of Object.entries(REFERENCE_NAMES)) {
    const option = element('option', '', name); option.value = id; referenceSelect.append(option);
  }
  referenceSelect.value = 'moon-tranquillitatis';
  referenceLabel.append(referenceSelect);
  const status = element('p', 'science-status', 'Loading saved experiments.');
  status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
  const results = element('div', 'discovery-results');
  const evidence = element('div', 'discovery-evidence');
  const evidenceDetail = element('div', 'discovery-evidence-detail');
  root.append(experimentLabel, referenceLabel, status, results, evidence);
  let index = null;
  let characterized = null;
  let active = null;
  let requestNumber = 0;

  async function showEvidence(id) {
    const record = characterized?.evidence?.evidence?.[id];
    if (!record) return;
    const selectedReference = characterized.evidence.study_groups.tranquillitatis_shared.includes(id)
      ? 'moon-tranquillitatis'
      : [...characterized.evidence.study_groups.jezero_original,
        ...characterized.evidence.study_groups.jezero_shifted].includes(id) ? 'mars-jezero' : null;
    const comparison = selectedReference ? characterized.comparisons.references[selectedReference] : null;
    const selected = comparison ? Object.values(comparison.selected_study_groups).flat().find(item => item.evidence_id === id) : null;
    const desiredExperiment = selected?.ranking_catalog === 'shifted_69' ? 'shifted-69' : 'expanded-64';
    if (selectedReference && (referenceSelect.value !== selectedReference || experimentSelect.value !== desiredExperiment)) {
      referenceSelect.value = selectedReference;
      experimentSelect.value = desiredExperiment;
      await load();
    }
    evidenceDetail.replaceChildren(element('h4', '', 'Regional evidence · Earth only'));
    paragraph(evidenceDetail, `${fmt(record.latitude, 4)}°, ${fmt(record.longitude, 4)}° · analyzed 220 km footprint. The outline represents the analyzed window, not a geological boundary.`, 'science-coordinate');
    if (selected) {
      paragraph(evidenceDetail, `${selected.ranking_catalog === 'original_64' ? 'Expanded 64' : 'Shifted 69'}: rank ${selected.rank_in_separate_catalog}; distance ${fmt(selected.distance_in_separate_calibration, 4)}. These independently calibrated distances cannot be compared across catalogs.`);
      evidenceDetail.append(featureTable({ features: selected.terrain_features }, { features: selected.reference_features }));
    }
    const water = record.water_occurrence;
    const counts = water.counts;
    paragraph(evidenceDetail, `Acquired · JRC Global Surface Water occurrence (1984–2024): ${fmt(counts.water_detected, 0)} of ${fmt(counts.pixels, 0)} footprint pixels show historical water detection (${fmt(100 * counts.water_detected / counts.pixels, 3)}% of counted pixels); ${fmt(counts.no_data, 0)} no-data pixels. This is not current water coverage.`);
    const climate = record.climate_center_point.annual;
    paragraph(evidenceDetail, `Acquired · NASA POWER 2001–2025 modeled center-point climatology: T2M ${fmt(climate.T2M, 2)} °C; precipitation ${fmt(climate.PRECTOTCORR, 2)} mm/day; surface pressure ${fmt(climate.PS, 2)} kPa. Not a local surface measurement or a planetary comparison.`);
    const source = water.source_tiles[0]?.source;
    if (source?.url) link(evidenceDetail, 'JRC source tile', source.url);
    const power = record.climate_center_point.provenance;
    if (power?.url) link(evidenceDetail, 'NASA POWER source request', power.url);
    paragraph(evidenceDetail, `Source SHA-256: JRC ${source?.sha256 || 'unavailable'}; POWER ${power?.sha256 || 'unavailable'}.`, 'science-provenance');
    paragraph(evidenceDetail, 'Unavailable · NASADEM HGT/NUM/SWB elevation was not acquired (Earthdata HTTP 401); no ETOPO1–NASADEM comparison exists. Geology, mineralogy, current ice and interpreted Landsat imagery remain unverified.', 'science-caution');
    paragraph(evidenceDetail, `Scientific interpretation · ${comparison?.research_relevance || 'East African water-screening control; no planetary comparison is selected for this window.'} ${characterized.comparisons.interpretation}`);
    if (selected) {
      const aiStatus = element('p', 'science-note', 'Optional Gemini interpretation orders verified evidence; it cannot create measurements or change the ranking.');
      const aiButton = element('button', 'science-secondary', 'Explain this evidence with Gemini');
      aiButton.type = 'button';
      aiButton.addEventListener('click', async () => {
        aiButton.disabled = true; aiStatus.textContent = 'Validating Gemini evidence selection.';
        try {
          const response = await apiClient.interpretRegion(selectedReference, id);
          aiStatus.textContent = response.explanation;
        } catch (error) { aiStatus.textContent = error.message; }
        finally { aiButton.disabled = false; }
      });
      evidenceDetail.append(aiStatus, aiButton);
    }
    link(evidenceDetail, 'Read regional characterization report', '/api/reports/regional-characterization');
    eventBus.emit('discovery:focus-evidence', { id, ...record });
  }

  function render(result) {
    active = result;
    results.replaceChildren();
    const metadata = index.experiments.find(item => item.id === result.experiment_id);
    paragraph(results, `${metadata.title}. ${metadata.generated_count === null ? 'Generated centers were recorded separately by region' : `${metadata.generated_count} centers generated`}; ${metadata.eligible_count} eligible${metadata.excluded_count === null ? '' : `; ${metadata.excluded_count} excluded`}.`);
    paragraph(results, `${String(metadata.center_generation).replace(/\.+$/, '')}. NOAA ETOPO1 Ice Surface; geographic eligibility uses mapped land, lake and glaciated-area layers. Current ice and seasonal water are not established.`);
    paragraph(results, result.calibration, 'science-caution');
    const diag = result.range_diagnostics;
    paragraph(results, `Catalog support: ${diag.outside_features.length ? `Reference outside Earth ranges for ${diag.outside_features.map(key => FEATURE_NAMES[key]).join(', ')}.` : 'Reference within individual Earth descriptor ranges; joint similarity is not validated.'}`, diag.outside_features.length ? 'science-caution' : 'science-note');
    const list = element('div', 'discovery-list');
    function displayCandidate(candidate, focus) {
      const detail = results.querySelector('.discovery-selected');
      detail.replaceChildren(element('h4', '', `Rank ${candidate.rank} · generated Earth window`));
      paragraph(detail, `${candidate.region || metadata.title}; ${fmt(candidate.latitude, 4)}°, ${fmt(candidate.longitude, 4)}°. Relative nearest-neighbor distance ${fmt(candidate.distance, 4)} (unbounded, not a percentage).`);
      detail.append(featureTable(candidate, result.reference, candidate.distance_explanation));
      paragraph(detail, 'Squared contributions explain this numerical distance, not causal or scientific importance. A top rank does not validate an analog.');
      if (focus) eventBus.emit('discovery:focus-candidate', candidate);
    }
    result.ranking.slice(0, 10).forEach(candidate => {
      const button = element('button', 'candidate-row', `${candidate.rank}. ${fmt(candidate.latitude, 4)}°, ${fmt(candidate.longitude, 4)}° · distance ${fmt(candidate.distance, 4)}`);
      button.type = 'button';
      button.addEventListener('click', () => {
        results.querySelectorAll('.candidate-row').forEach(row => row.classList.remove('is-active'));
        button.classList.add('is-active');
        displayCandidate(candidate, true);
      });
      list.append(button);
    });
    results.append(element('h4', '', `${REFERENCE_NAMES[referenceSelect.value]} · top 10 of ${result.ranking.length}`), list, element('div', 'discovery-selected'));
    list.firstElementChild?.classList.add('is-active');
    if (result.ranking.length) displayCandidate(result.ranking[0], false);
    link(results, 'Read this experiment report', `/api/reports/${result.experiment_id === 'west-africa-49' ? 'discovery-initial' : result.experiment_id === 'expanded-64' ? 'discovery-expanded' : 'discovery-shifted'}`);
    paragraph(results, `Result file SHA-256: ${result.ranking_sha256}. Each experiment retains its own candidate population and Earth IQR calibration.`, 'science-provenance');
    eventBus.emit('discovery:results', { candidates: result.ranking, experimentId: result.experiment_id });
  }

  function renderStudyGroups() {
    evidence.replaceChildren(element('h4', '', 'Selected investigation windows'));
    evidenceDetail.replaceChildren();
    paragraph(evidence, 'Mare Tranquillitatis: paired overlapping South American windows. Jezero: two separate windows. Tycho and Gale: no endorsed Earth investigation region; both remain extrapolative. East Africa is a water-screening control.');
    const groupNames = {
      tranquillitatis_shared: 'Tranquillitatis · shared region',
      jezero_original: 'Jezero · original center',
      jezero_shifted: 'Jezero · shifted center',
      east_africa_water_control: 'East Africa · screening control'
    };
    for (const [group, ids] of Object.entries(characterized.evidence.study_groups)) {
      ids.forEach(id => {
        const record = characterized.evidence.evidence[id];
        const button = element('button', 'science-evidence-button', `${groupNames[group]} · ${fmt(record.latitude, 4)}°, ${fmt(record.longitude, 4)}°`);
        button.type = 'button'; button.addEventListener('click', () => showEvidence(id)); evidence.append(button);
      });
    }
    link(evidence, 'Read regional characterization report', '/api/reports/regional-characterization');
    evidence.append(evidenceDetail);
  }

  async function load() {
    if (!index) return;
    const serial = ++requestNumber;
    status.textContent = 'Loading the selected saved ranking.';
    try {
      const result = await apiClient.discoveryReference(experimentSelect.value, referenceSelect.value);
      if (serial !== requestNumber) return;
      render(result);
      renderStudyGroups();
      status.textContent = `Showing ${result.ranking.length} eligible generated candidates · saved experiment`;
    } catch (error) { if (serial === requestNumber) status.textContent = `Discovery results unavailable: ${error.message}`; }
  }
  experimentSelect.addEventListener('change', load);
  referenceSelect.addEventListener('change', load);
  eventBus.on('discovery:select-evidence', ({ id }) => showEvidence(id));
  eventBus.on('globe:ready', () => {
    if (active) eventBus.emit('discovery:results', { candidates: active.ranking, experimentId: active.experiment_id });
  });
  root.setReference = id => {
    if (!(id in REFERENCE_NAMES)) return;
    referenceSelect.value = id;
    if (index) load();
  };
  eventBus.on('profile:select', ({ profileId } = {}) => {
    if (profileId === 'moon_reference') root.setReference('moon-tranquillitatis');
    if (profileId === 'mars_reference') root.setReference('mars-jezero');
  });
  Promise.all([apiClient.discoveryExperiments(), apiClient.characterization()]).then(([manifest, evidenceData]) => {
    index = manifest; characterized = evidenceData;
    manifest.experiments.forEach(item => {
      const option = element('option', '', item.title); option.value = item.id; experimentSelect.append(option);
    });
    experimentSelect.value = 'expanded-64';
    renderStudyGroups(); load();
  }).catch(error => { status.textContent = `Saved research results unavailable: ${error.message}`; });
  return root;
}
