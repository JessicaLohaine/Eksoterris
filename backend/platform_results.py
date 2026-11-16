"""Read immutable, separately calibrated research outputs for the platform."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / 'results'
EXPERIMENTS = {
    'west-africa-49': {
        'title': 'West Africa: initial 49 centers',
        'ranking': 'terrestrial-discovery/rankings.json',
        'catalog': 'terrestrial-discovery/catalog.json',
        'report': 'docs/terrestrial-discovery-experiment.md',
    },
    'expanded-64': {
        'title': 'Three-region expanded catalog: 64 eligible windows',
        'ranking': 'terrestrial-discovery-expansion-v1/combined.json',
        'report': 'docs/discovery-robustness-and-expansion.md',
    },
    'shifted-69': {
        'title': 'Shifted South America and East Africa: 69 eligible windows',
        'ranking': 'terrestrial-discovery-characterization-v1/combined-shifted.json',
        'report': 'docs/shifted-discovery-characterization.md',
    },
}
REFERENCE_IDS = ('moon-tranquillitatis', 'moon-tycho', 'mars-jezero', 'mars-gale')
REPORTS = {
    'discovery-initial': 'docs/terrestrial-discovery-experiment.md',
    'discovery-expanded': 'docs/discovery-robustness-and-expansion.md',
    'discovery-shifted': 'docs/shifted-discovery-characterization.md',
    'regional-characterization': 'docs/regional-scientific-characterization.md',
}


def _read(relative):
    path = RESULTS / relative
    content = path.read_bytes()
    return json.loads(content), hashlib.sha256(content).hexdigest()


def experiment_index():
    entries = []
    for experiment_id, metadata in EXPERIMENTS.items():
        data, digest = _read(metadata['ranking'])
        if metadata.get('catalog'):
            catalog, _ = _read(metadata['catalog'])
            generated = catalog['generated_count']
            excluded = catalog['excluded_count']
            eligible = catalog['evaluated_count']
            source = catalog['provenance']['earth_source']
            generation = catalog['provenance']['center_generation']
        else:
            eligible = data['candidate_count']
            generated = None  # Different regional runs cannot be summed as one global lattice.
            excluded = None
            source = data.get('source_provenance')
            generation = data.get('population', 'Separate bounded regional geographic lattices')
        entries.append({
            'id': experiment_id, 'title': metadata['title'],
            'generated_count': generated, 'eligible_count': eligible,
            'excluded_count': excluded, 'center_generation': generation,
            'source': source, 'ranking_sha256': digest, 'report': metadata['report'],
            'calibration': 'Earth-only IQR fitted separately to this catalog; distances across experiments are not directly comparable.',
        })
    return {'baseline': {'title': 'Seven predefined sites', 'kind': 'separate production baseline',
                         'endpoint': '/api/catalog', 'analysis_endpoint': '/api/analyses'},
            'experiments': entries}


def experiment_reference(experiment_id, reference_id):
    if experiment_id not in EXPERIMENTS or reference_id not in REFERENCE_IDS:
        raise KeyError('Unknown experiment or planetary reference.')
    metadata = EXPERIMENTS[experiment_id]
    data, digest = _read(metadata['ranking'])
    result = data['references'][reference_id]
    # Read the original ranking, never recompute it with a different calibration.
    return {
        'experiment_id': experiment_id, 'title': metadata['title'],
        'reference': result['reference'], 'ranking': result['ranking'],
        'range_diagnostics': result['range_diagnostics'],
        'earth_iqr': (data.get('model') or data['provenance'].get('model', {})).get('earth_iqr'),
        'ranking_sha256': digest, 'report': metadata['report'],
        'calibration': 'Distances apply only within this experiment and are not probabilities or analog validation.',
    }


def characterization():
    evidence, evidence_hash = _read('regional-characterization-v1/evidence.json')
    comparison, comparison_hash = _read('regional-characterization-v1/comparisons.json')
    return {'evidence': evidence, 'comparisons': comparison,
            'provenance': {'evidence_sha256': evidence_hash, 'comparisons_sha256': comparison_hash,
                           'report': 'docs/regional-scientific-characterization.md'}}
