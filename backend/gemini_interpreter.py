"""Gemini selects verified evidence; server renders all factual statements.

Free-form model prose never becomes a scientific result. The model cannot change
the ranking, coordinates, measurements or sources in this protocol.
"""
import json
import os
from google import genai
from science import FEATURES


class GeminiResponseError(RuntimeError):
    """The provider response did not satisfy the evidence contract."""


def evidence_for(run):
    winner, reference = run['candidates'][0], run['reference']
    evidence = {}
    for key, label in FEATURES.items():
        value, ref = winner['features'][key], reference['features'][key]
        direction = 'lower than' if value < ref else 'higher than' if value > ref else 'equal to'
        evidence[key] = f"{label}: {winner['name']} has {value:.3f}, {direction} the reference value {ref:.3f}."
    evidence['ranking'] = f"{winner['name']} ranks first among {len(run['candidates'])} evaluated Earth windows in an unsupervised nearest-neighbor search, with standardized distance {winner['distance']:.4f} (lower is closer; not a probability)."
    stable = all(v == winner['id'] for v in run['sensitivity'].values())
    evidence['sensitivity'] = ('The top candidate remains first in all leave-one-feature-out comparisons.' if stable else 'The top candidate changes when a descriptor is omitted; the ranking is sensitive to the feature selection.')
    if run.get('range_diagnostics'):
        evidence['catalog_support'] = run['range_diagnostics']['interpretation']
    return evidence


def validate_selection(selection, evidence, run):
    if not isinstance(selection, dict) or set(selection) != {'candidate_id','evidence_ids','limitation_ids'}:
        raise ValueError('Unexpected Gemini response fields.')
    if selection['candidate_id'] != run['candidates'][0]['id']:
        raise ValueError('Gemini attempted to change the computed winner.')
    ids = selection['evidence_ids']
    if not isinstance(ids,list) or not 2 <= len(ids) <= len(evidence) or any(not isinstance(i,str) for i in ids) or len(set(ids)) != len(ids) or any(i not in evidence for i in ids):
        raise ValueError('Gemini cited invalid evidence.')
    if 'ranking' not in ids or 'sensitivity' not in ids:
        raise ValueError('Required ranking and sensitivity evidence missing.')
    if run.get('range_diagnostics') and 'catalog_support' not in ids:
        raise ValueError('Required catalog support evidence missing.')
    if selection['limitation_ids'] != ['scope','resolution','method']:
        raise ValueError('Required limitations missing.')
    return selection


def interpret(run):
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not key:
        raise ValueError('GEMINI_API_KEY is not configured in the backend process. Start the backend from the terminal containing the key.')
    evidence = evidence_for(run)
    schema = {'type':'object','properties':{
        'candidate_id':{'type':'string','enum':[run['candidates'][0]['id']]},
        'evidence_ids':{'type':'array','items':{'type':'string','enum':list(evidence)},'minItems':2,'maxItems':len(evidence)},
        'limitation_ids':{'type':'array','items':{'type':'string','enum':['scope','resolution','method']}}},
        'required':['candidate_id','evidence_ids','limitation_ids'],'additionalProperties':False}
    prompt = ('You help explain a reproducible planetary topography screening in English. '
              'Select and order the most useful supplied evidence IDs to explain the computed winner. '
              'Always include ranking, sensitivity, and catalog_support if supplied. Include limitation_ids exactly in order: scope, resolution, method. '
              'No measurements may be inferred. Your selections will be validated and the backend will render the supplied sentences.\n'
              + json.dumps({'winner':run['candidates'][0]['id'],'evidence':evidence,'limitations':run['limitations'][:3]}))
    with genai.Client(api_key=key, http_options={'timeout':45000}) as client:
        response = client.models.generate_content(model=os.getenv('GEMINI_MODEL','gemini-3.5-flash-lite'),
            contents=prompt, config={'response_mime_type':'application/json','response_json_schema':schema})
    if not response.candidates or getattr(response.candidates[0].finish_reason, 'value', None) != 'STOP' or not response.text:
        raise GeminiResponseError('Gemini did not return a complete structured response.')
    try:
        selection = validate_selection(json.loads(response.text), evidence, run)
    except (ValueError, TypeError) as exc:
        raise GeminiResponseError('Gemini returned an invalid evidence selection.') from exc
    result = {'status':'verified','provider':'Gemini','model':response.model_version,'selection':selection,
              'explanation':' '.join(evidence[i] for i in selection['evidence_ids']),
              'limitations':run['limitations'][:3], 'run_id':run['run_id'],
              'source_ids':[run['reference']['source']['id'],run['candidates'][0]['source']['id']],
              'validation':'Only existing evidence identifiers accepted; all displayed facts rendered by the backend.',
              'usage':response.usage_metadata.model_dump(exclude_none=True) if response.usage_metadata else {}}
    return result


def interpret_regional_evidence(reference_id, evidence_id, bundle):
    """Let Gemini order only verified regional facts; the backend writes the prose."""
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not key:
        raise ValueError('GEMINI_API_KEY is not configured in the backend process.')
    comparison = bundle['comparisons']['references'].get(reference_id)
    record = bundle['evidence']['evidence'].get(evidence_id)
    if not comparison or evidence_id not in comparison['earth_context_evidence_ids'] or not record:
        raise ValueError('This region is not selected for that planetary reference.')
    study = next((item for items in comparison['selected_study_groups'].values()
                  for item in items if item['evidence_id'] == evidence_id), None)
    if not study:
        raise ValueError('No saved topographic study supports this region.')
    counts = record['water_occurrence']['counts']
    annual = record['climate_center_point']['annual']
    facts = {
        'screening': (f"The Earth window at {record['latitude']:.4f}°, {record['longitude']:.4f}° "
                      f"ranked {study['rank_in_separate_catalog']} in the {study['ranking_catalog']} topographic catalog. "
                      'The ranking is relative and cannot validate a planetary analog.'),
        'historical_water': (f"JRC Global Surface Water 1984–2024 detected historical water at "
                             f"{counts['water_detected']} of {counts['pixels']} sampled footprint pixels; "
                             f"{counts['no_data']} pixels were no-data. Historical occurrence does not establish current water coverage."),
        'modeled_climate': (f"NASA POWER 2001–2025 modeled center-point climatology reports annual "
                            f"air temperature {annual['T2M']:.2f} °C, precipitation {annual['PRECTOTCORR']:.2f} mm/day, "
                            f"and surface pressure {annual['PS']:.2f} kPa. These are not local surface measurements."),
        'missing_evidence': ('NASADEM elevation was unavailable after Earthdata HTTP 401; geology, mineralogy, '
                             'current ice and interpreted Landsat imagery remain unverified. No measured '
                             'planetary environmental equivalence follows from these Earth-only data.'),
    }
    ids = list(facts)
    schema = {'type': 'object', 'properties': {'evidence_ids': {
        'type': 'array', 'items': {'type': 'string', 'enum': ids}, 'minItems': len(ids), 'maxItems': len(ids)}},
        'required': ['evidence_ids'], 'additionalProperties': False}
    prompt = ('Explain the selected Earth investigation region in English by ordering the supplied evidence IDs. '
              'Include every ID exactly once. Do not add observations, coordinates, measurements, sources, '
              'geology or analogy claims. The backend will render the sentences.\n' +
              json.dumps({'reference_id': reference_id, 'region_id': evidence_id, 'facts': facts}, ensure_ascii=False))
    with genai.Client(api_key=key, http_options={'timeout': 45000}) as client:
        response = client.models.generate_content(
            model=os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite'),
            contents=prompt, config={'response_mime_type': 'application/json', 'response_json_schema': schema})
    if not response.candidates or getattr(response.candidates[0].finish_reason, 'value', None) != 'STOP' or not response.text:
        raise GeminiResponseError('Gemini did not return a complete structured response.')
    try:
        selected = json.loads(response.text)
        if (not isinstance(selected, dict) or set(selected) != {'evidence_ids'} or
                not isinstance(selected['evidence_ids'], list) or
                len(selected['evidence_ids']) != len(ids) or set(selected['evidence_ids']) != set(ids)):
            raise ValueError('Invalid evidence identifiers.')
    except (ValueError, TypeError) as exc:
        raise GeminiResponseError('Gemini returned invalid evidence identifiers.') from exc
    return {'status': 'verified_evidence_selection', 'provider': 'Gemini',
            'model': response.model_version, 'reference_id': reference_id,
            'evidence_id': evidence_id, 'selected_evidence_ids': selected['evidence_ids'],
            'explanation': ' '.join(facts[item] for item in selected['evidence_ids']),
            'limitation': 'Earth-only observations do not establish planetary analog validity.'}
