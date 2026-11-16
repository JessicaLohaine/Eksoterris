"""Controlled perturbations of the existing nearest-neighbor ranking."""
from itertools import combinations
import numpy as np
from terrain_knn import TerrainKNN


def summarize_ranking(name, assumption, ranking, baseline):
    """Compare ordered identifiers on common candidates; distances remain scenario-specific."""
    ordered = [identifier for identifier, _ in ranking]
    base_order = [identifier for identifier, _ in baseline]
    shared = set(ordered) & set(base_order)
    common = [identifier for identifier in base_order if identifier in shared]
    scenario_common = [identifier for identifier in ordered if identifier in shared]
    base_distances, distances = dict(baseline), dict(ranking)
    if len(common) >= 2:
        left = np.array([common.index(identifier) for identifier in common], dtype=float)
        right = np.array([scenario_common.index(identifier) for identifier in common], dtype=float)
        rho = float(np.corrcoef(left, right)[0, 1])
    else:
        rho = None
    return {'name':name, 'assumption_changed':assumption,
            'winner':ordered[0],
            'ranking':[{'id':identifier, 'rank':index, 'distance':distance}
                       for index, (identifier, distance) in enumerate(ranking, 1)],
            'top_three_overlap_count':len(set(ordered[:3]) & set(base_order[:3])),
            'top_three_comparison_size':min(3, len(ordered), len(base_order)),
            'shared_candidate_spearman_rho':rho,
            'distance_change_from_baseline':{identifier:distances[identifier]-base_distances[identifier]
                                             for identifier in common}}


def descriptor_and_catalog_scenarios(model, candidates, reference):
    """Hold the baseline scale or refit it after a controlled candidate exclusion."""
    baseline = model.query(reference)
    scenarios = []
    for size in range(1, len(model.feature_names)):
        for subset in combinations(model.feature_names, size):
            ranking = model.query_subset(reference, subset)
            scenario = summarize_ranking('features:' + ','.join(subset),
                                         'Retain only the listed descriptors; keep the original Earth IQR.', ranking, baseline)
            scenario['features_used'] = list(subset)
            scenario['earth_iqr'] = {name:float(model.scale[model.feature_names.index(name)]) for name in subset}
            scenarios.append(scenario)
    if len(candidates) >= 3:
        for candidate in sorted(candidates, key=lambda item:item['id']):
            omitted = candidate['id']
            fixed = [(identifier, distance) for identifier, distance in baseline if identifier != omitted]
            scenario = summarize_ranking('exclude:' + omitted + ':fixed_iqr',
                                         'Exclude one Earth candidate from the search; retain baseline Earth IQR.', fixed, baseline)
            scenario['earth_iqr'] = dict(zip(model.feature_names, model.scale.tolist()))
            scenarios.append(scenario)
            refit = TerrainKNN(model.feature_names).fit([item for item in candidates if item['id'] != omitted])
            scenario = summarize_ranking('exclude:' + omitted + ':refit_iqr',
                                         'Exclude one Earth candidate and recompute the Earth IQR on the remaining catalog.',
                                         refit.query(reference), baseline)
            scenario['earth_iqr'] = dict(zip(model.feature_names, refit.scale.tolist()))
            scenarios.append(scenario)
    return {'baseline':summarize_ranking('baseline', 'All available candidates and all three features.', baseline, baseline),
            'scenarios':scenarios,
            'interpretation':'Rank sensitivity under the listed perturbations is not a probability of analog validity. '
                             'Distances from different descriptor subsets use different averaging dimensions.'}
