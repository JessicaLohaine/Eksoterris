"""Separate experimental sampling density from analysis-window extent.

This module never changes the application's default 11 by 11, 20 km analysis.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from science import CANDIDATES, FEATURES, RADIUS, TARGETS, coordinates, features, window
from sources import DATA, earth_raster, planetary_raster
from ranking_sensitivity import summarize_ranking
from terrain_knn import TerrainKNN
from terrain_quality import assess_quality


CONFIGURATIONS = (
    {'id': 'baseline-220km-11', 'question': 'baseline', 'width_m': 220000, 'grid_size': 11},
    {'id': 'density-220km-7', 'question': 'sampling_density', 'width_m': 220000, 'grid_size': 7},
    {'id': 'density-220km-5', 'question': 'sampling_density', 'width_m': 220000, 'grid_size': 5},
    {'id': 'extent-180km-9', 'question': 'window_extent', 'width_m': 180000, 'grid_size': 9},
    {'id': 'extent-260km-13', 'question': 'window_extent', 'width_m': 260000, 'grid_size': 13},
)

BASELINE_CONTROLS = {
    'moon-tranquillitatis': ('colorado-plateau', 0.4354883112),
    'moon-tycho': ('atacama', 2.2923108590),
    'mars-jezero': ('atacama', 0.7217655570),
    'mars-gale': ('atacama', 2.2567657900),
}


def sample_window(raster, location, body, width_m, grid_size, return_coordinates=False):
    """Use the baseline's five-by-five bilinear quadrature at variable grid size."""
    if grid_size < 5 or grid_size % 2 != 1 or width_m <= 0:
        raise ValueError('The experiment requires a positive width and an odd grid of at least five cells.')
    spacing = width_m / grid_size
    axis = (np.arange(grid_size) - grid_size // 2) * spacing
    x, y = np.meshgrid(axis, axis)
    values, latitudes, longitudes = [], [], []
    for dy in (-0.4, -0.2, 0, 0.2, 0.4):
        for dx in (-0.4, -0.2, 0, 0.2, 0.4):
            lat, lon = coordinates(location['latitude'], location['longitude'],
                                   x + dx * spacing, y + dy * spacing, RADIUS[body])
            values.append(raster.sample(lat, lon))
            if return_coordinates:
                latitudes.append(lat)
                longitudes.append(lon)
    grid = np.mean(values, axis=0)
    if grid.shape != (grid_size, grid_size) or not np.isfinite(grid).all():
        raise ValueError('The experimental grid has missing or invalid elevation cells.')
    if return_coordinates:
        return grid, (np.stack(latitudes), np.stack(longitudes))
    return grid


def terrain_descriptors(grid, spacing_m):
    """Apply the original three definitions to any odd square experimental grid."""
    z = np.asarray(grid, dtype=float)
    if z.ndim != 2 or z.shape[0] != z.shape[1] or z.shape[0] < 5 or not np.isfinite(z).all() or spacing_m <= 0:
        raise ValueError('Finite square elevation data and positive spacing are required.')
    north, east = np.gradient(z, spacing_m)
    slope = np.degrees(np.arctan(np.hypot(east, north)))
    y, x = np.indices(z.shape)
    design = np.column_stack((np.ones(z.size), x.ravel(), y.ravel()))
    residual = z.ravel() - design @ np.linalg.lstsq(design, z.ravel(), rcond=None)[0]
    return {'relief_m': float(np.percentile(z, 95) - np.percentile(z, 5)),
            'median_slope_deg': float(np.median(slope[1:-1, 1:-1])),
            'detrended_rms_m': float(np.sqrt(np.mean(residual ** 2))),
            'mean_elevation_m': float(z.mean()), 'valid_cells': int(z.size)}


def run_experiment():
    """Recompute all four references and seven Earth windows without changing API results."""
    earth = {c['id']: earth_raster(c['latitude'], c['longitude']) for c in CANDIDATES}
    planets = {body: planetary_raster(body) for body in ('moon', 'mars')}
    result = {'experiment_version': 'spatial-scale-v1',
              'computed_at': datetime.now(timezone.utc).isoformat(),
              'configurations': [{**c, 'spacing_m': c['width_m'] / c['grid_size'],
                                  'subsamples_per_cell': 25} for c in CONFIGURATIONS],
              'sources': {'earth': {key: raster.provenance['sha256'] for key, raster in earth.items()},
                          'moon': planets['moon'].provenance['sha256'],
                          'mars': planets['mars'].provenance['sha256']},
              'targets': {}}
    for target_id, target in TARGETS.items():
        planet = planets[target['body']]
        scenarios = []
        baseline_ranking = None
        baseline_features = None
        for config in CONFIGURATIONS:
            size, width = config['grid_size'], config['width_m']
            spacing = width / size
            try:
                grid, positions = sample_window(planet, target, target['body'], width, size, True)
                reference = terrain_descriptors(grid, spacing)
                terrestrial = []
                for candidate in CANDIDATES:
                    candidate_grid = sample_window(earth[candidate['id']], candidate, 'earth', width, size)
                    terrestrial.append({**candidate, 'features': terrain_descriptors(candidate_grid, spacing)})
                if config['question'] == 'baseline':
                    # Guard against a nominally identical experimental baseline
                    # inadvertently using a different production sampling method.
                    np.testing.assert_allclose(grid, window(planet, target, target['body']), rtol=0, atol=1e-9)
                    for candidate, original in zip(terrestrial, CANDIDATES):
                        old = features(window(earth[original['id']], original, 'earth'))
                        for descriptor in FEATURES:
                            np.testing.assert_allclose(candidate['features'][descriptor], old[descriptor], rtol=0, atol=1e-9)
                    old = features(window(planet, target, target['body']))
                    for descriptor in FEATURES:
                        np.testing.assert_allclose(reference[descriptor], old[descriptor], rtol=0, atol=1e-9)
                model = TerrainKNN(FEATURES).fit(terrestrial)
                ranking = model.query(reference)
                if config['question'] == 'baseline':
                    expected_winner, expected_distance = BASELINE_CONTROLS[target_id]
                    if ranking[0][0] != expected_winner or not np.isclose(ranking[0][1], expected_distance, atol=1e-7, rtol=0):
                        raise ValueError('The baseline differs from the verified source-file ranking.')
                    baseline_ranking = ranking
                    baseline_features = {'reference': reference,
                                         'earth': {c['id']: c['features'] for c in terrestrial},
                                         'contributions': model.explain(reference)}
                if baseline_ranking is None:
                    raise ValueError('A verified baseline is required before evaluating alternatives.')
                comparison = summarize_ranking(config['id'],
                    'Keep nominal window width fixed while changing cell spacing and subcell quadrature.' if config['question'] == 'sampling_density' else
                    'Change window extent while retaining 20 km cell spacing.' if config['question'] == 'window_extent' else
                    'Original 11 by 11 grid at 20 km spacing.', ranking, baseline_ranking)
                quality = assess_quality(target, planet, grid, positions)
                observed = quality.get('observation_coverage', {})
                comparison.update(status='inconclusive_source_coverage' if observed.get('bins_with_no_shots', 0) else 'computed',
                    grid_size=size, window_width_m=width, spacing_m=spacing,
                    reference_features=reference,
                    earth_features={c['id']: c['features'] for c in terrestrial},
                    earth_iqr=dict(zip(FEATURES, model.scale.tolist())),
                    range_diagnostics=model.range_diagnostics(reference),
                    distance_explanations=model.explain(reference),
                    source_coverage=observed or {'status': 'not_established'},
                    reference_descriptor_change={key: reference[key] - baseline_features['reference'][key] for key in FEATURES},
                    earth_descriptor_change={c['id']: {key: c['features'][key] - baseline_features['earth'][c['id']][key] for key in FEATURES} for c in terrestrial},
                    squared_contribution_change={identifier: {key: model.explain(reference)[identifier]['descriptors'][key]['contribution_to_squared_distance'] - baseline_features['contributions'][identifier]['descriptors'][key]['contribution_to_squared_distance'] for key in FEATURES} for identifier, _ in ranking})
            except (ValueError, RuntimeError, AssertionError) as exc:
                if config['question'] == 'baseline':
                    raise RuntimeError(f'Cannot reproduce baseline for {target_id}: {exc}') from exc
                comparison = {'name': config['id'], 'status': 'invalid', 'reason': str(exc)}
            scenarios.append(comparison)
        result['targets'][target_id] = scenarios
    result['implementation_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (DATA / 'spatial-scale-report.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    return result


if __name__ == '__main__':
    report = run_experiment()
    for target, scenarios in report['targets'].items():
        print(target)
        for scenario in scenarios:
            print(' ', scenario['name'], scenario['status'], scenario.get('winner'),
                  scenario.get('shared_candidate_spearman_rho'))
