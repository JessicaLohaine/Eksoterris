"""Unsupervised nearest-neighbor retrieval over measured terrain descriptors."""
import numpy as np


class TerrainKNN:
    """Fit Earth feature scales, then rank Earth windows against a planetary query.

    This instance-based model has no labels, probability estimates, or predictive
    accuracy claim. Median and IQR are fitted only on Earth candidates.
    """
    def __init__(self, feature_names):
        self.feature_names = tuple(feature_names)

    def fit(self, candidates):
        self.identifiers = tuple(c['id'] for c in candidates)
        self.samples = np.array([[c['features'][name] for name in self.feature_names] for c in candidates], dtype=float)
        if len(self.samples) < 2 or not np.isfinite(self.samples).all():
            raise ValueError('At least two complete finite Earth feature vectors are required.')
        self.center = np.median(self.samples, axis=0)
        self.scale = np.percentile(self.samples, 75, axis=0) - np.percentile(self.samples, 25, axis=0)
        if np.any(self.scale <= 1e-12):
            raise ValueError('Earth feature dispersion is zero; this comparison is not identifiable.')
        return self

    def query(self, reference, omitted=None):
        retained = [name for name in self.feature_names if name != omitted]
        return self.query_subset(reference, retained)

    def query_subset(self, reference, retained):
        retained = tuple(retained)
        if not retained or len(set(retained)) != len(retained) or any(name not in self.feature_names for name in retained):
            raise ValueError('A neighbor search needs distinct known features.')
        vector = np.array([reference[name] for name in self.feature_names], dtype=float)
        if not np.isfinite(vector).all():
            raise ValueError('Planetary reference has missing or invalid features.')
        indices = [self.feature_names.index(name) for name in retained]
        delta = (self.samples[:, indices] - vector[indices]) / self.scale[indices]
        distance = np.sqrt(np.mean(delta**2, axis=1))
        return sorted(zip(self.identifiers, distance.tolist()), key=lambda pair: (pair[1], pair[0]))

    def range_diagnostics(self, reference):
        values = np.array([reference[name] for name in self.feature_names], dtype=float)
        if not np.isfinite(values).all():
            raise ValueError('Planetary reference has missing or invalid features.')
        low, high = self.samples.min(axis=0), self.samples.max(axis=0)
        descriptors = {}
        for index, name in enumerate(self.feature_names):
            side = 'below' if values[index] < low[index] else 'above' if values[index] > high[index] else 'within'
            descriptors[name] = {'reference':float(values[index]), 'earth_min':float(low[index]),
                                 'earth_max':float(high[index]), 'position':side}
        outside = [name for name, item in descriptors.items() if item['position'] != 'within']
        return {'status':'insufficient_catalog_evidence' if outside else 'within_observed_feature_ranges',
                'outside_features':outside, 'descriptors':descriptors,
                'catalog_size':len(self.identifiers),
                'interpretation':('The reference is outside the observed Earth range for at least one descriptor. '
                                  'The nearest available candidate is only a relative result; this catalog does not support a confident comparison.'
                                  if outside else 'The reference lies within each separate observed Earth descriptor range. '
                                  'This does not establish a close multivariate match or validate a planetary analog.')}

    def explain(self, reference):
        vector = np.array([reference[name] for name in self.feature_names], dtype=float)
        if not np.isfinite(vector).all():
            raise ValueError('Planetary reference has missing or invalid features.')
        explanations = {}
        for row, identifier in zip(self.samples, self.identifiers):
            scaled = (row - vector) / self.scale
            contributions = scaled ** 2 / len(self.feature_names)
            explanations[identifier] = {
                'descriptors':{name:{'earth':float(row[i]), 'reference':float(vector[i]),
                                      'earth_iqr':float(self.scale[i]), 'scaled_difference':float(scaled[i]),
                                      'contribution_to_squared_distance':float(contributions[i])}
                               for i, name in enumerate(self.feature_names)},
                'largest_numerical_contributor':self.feature_names[int(np.argmax(contributions))],
                'squared_distance':float(contributions.sum()),
                'distance':float(np.sqrt(contributions.sum()))}
        return explanations

    def metadata(self):
        return {'algorithm':'Unsupervised k-nearest-neighbor retrieval',
                'normalization':'Earth training-set median and interquartile range (IQR); query uses fitted Earth scale',
                'distance':'sqrt(mean(((Earth feature - planetary feature) / Earth feature IQR)^2))',
                'k':len(self.identifiers),'training_samples':len(self.identifiers),
                'feature_names':list(self.feature_names),
                'earth_median':dict(zip(self.feature_names, self.center.tolist())),
                'earth_iqr':dict(zip(self.feature_names, self.scale.tolist())),
                'labels_used':False,'distance_is_probability':False}
