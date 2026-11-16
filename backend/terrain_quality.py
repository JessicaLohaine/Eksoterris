"""Product-level caveats and inspectable, non-calibrated raster diagnostics."""
import numpy as np
from sources import mola_observation_counts


def assess_quality(target, raster, grid, sampling_coordinates=None):
    """Report what the inputs establish without treating finite pixels as direct observations."""
    body = target['body']
    spacing_km = 2 * np.pi * (1737.4 if body == 'moon' else 3396.0) / 360 / raster.provenance['pixels_per_degree']
    result = {'product':raster.provenance['title'],
              'native_grid_spacing_km_at_equator':float(spacing_km),
              'finite_output_cells':int(np.isfinite(grid).sum()), 'output_cells':int(grid.size),
              'effective_resolution':'Not established by the native grid spacing or the 20 km output grid.',
              'coverage_note':'Finite output cells do not distinguish direct observations from interpolated source cells.',
              'registration':'Ascending cell-centered latitude and east-positive longitude; local sampling uses a spherical body radius.',
              'vertical_reference':raster.provenance['datum'], 'warnings':[]}
    if body == 'moon':
        result['warnings'].append('LOLA LDEM_4 label notes possible artifacts at 45-degree latitude strip boundaries; this is not an observed artifact diagnosis.')
        # A 220 km-wide projected footprint can meet a parallel within 110 km of its center.
        crosses = abs(target['latitude'] + 45) < np.degrees(110000 / 1737400)
        result['tycho_45_south_intersection'] = bool(crosses)
        if crosses:
            rows = np.where((raster.lat >= -46.5) & (raster.lat <= -43.5))[0]
            longitudes = ((raster.lon + 180) % 360) - 180
            cols = np.where(np.abs((longitudes-target['longitude']+180) % 360-180) <= 4)[0]
            seam = int(np.argmin(abs(raster.lat + 45)))
            if len(rows) >= 4 and len(cols) >= 2 and seam > 1 and seam + 2 < len(raster.lat):
                # These are descriptive gradients, not a seam/no-seam hypothesis test.
                differences = np.abs(np.diff(raster.z[np.arange(seam-2,seam+3)[:, None], cols], axis=0))
                result['seam_inspection'] = {
                    'sample_longitude_count':int(len(cols)),
                    'row_latitudes_deg':raster.lat[seam-2:seam+3].tolist(),
                    'median_adjacent_row_difference_m':np.median(differences, axis=1).tolist(),
                    'conclusion':'Adjacent-row differences alone cannot distinguish topography from a processing seam; quality remains unresolved.'}
            result['warnings'].append('This regional window intersects the nominal 45 S strip boundary; verify seam behavior with independent data before interpreting the ranking.')
    else:
        result['warnings'].append('The MOLA label describes interpolated bins where no direct observations exist. The companion counts grid is not used, so per-cell observation coverage is unknown.')
        result['quality_layer_status'] = 'MOLA MEGDR companion observation-count grid available from PDS but not processed in this analysis.'
        try:
            companion = mola_observation_counts()
            if companion is not None and sampling_coordinates is not None:
                counts, provenance = companion
                if counts.shape != raster.z.shape:
                    raise ValueError('MOLA count grid dimensions do not match topography.')
                latitudes, longitudes = sampling_coordinates
                # Enumerate the actual source pixels with nonzero bilinear weight.
                yi = (np.asarray(latitudes) - raster.lat[0]) / (raster.lat[1] - raster.lat[0])
                xi = ((np.asarray(longitudes) - raster.lon[0]) / (raster.lon[1] - raster.lon[0])) % counts.shape[1]
                if np.any(yi < 0) or np.any(yi > counts.shape[0] - 1):
                    raise ValueError('MOLA count lookup outside latitude coverage.')
                low_y = np.minimum(np.floor(yi).astype(int), counts.shape[0] - 2)
                low_x = np.floor(xi).astype(int)
                support = set()
                for row, col, fy, fx in zip(low_y.ravel(), low_x.ravel(),
                                             (yi - low_y).ravel(), (xi - low_x).ravel()):
                    for dy, wy in ((0, 1 - fy), (1, fy)):
                        for dx, wx in ((0, 1 - fx), (1, fx)):
                            if wy * wx > 1e-12:
                                support.add((int(row + dy), int((col + dx) % counts.shape[1])))
                observed = [int(counts[row, col]) for row, col in support]
                result['observation_coverage'] = {
                    'status': 'observed_source_bins' if all(observed) else 'includes_zero_count_source_bins',
                    'source_bins_touched': len(observed),
                    'bins_with_at_least_one_shot': sum(value > 0 for value in observed),
                    'bins_with_no_shots': sum(value == 0 for value in observed),
                    'shot_count_range_in_touched_bins': [min(observed), max(observed)],
                    'count_grid_source': provenance,
                    'interpretation': 'Counts describe source bins, not independent measurements of bilinearly interpolated output cells or elevation uncertainty.'}
                result['quality_layer_status'] = 'The aligned PDS MEGDR count grid was checked against every source bin touched by the 25 by 121 bilinear samples.'
                result['warnings'][-1] = 'MOLA elevation bins with no shots may be filled; the companion count grid reports direct shot support for the sampled source bins, not accuracy.'
        except (ValueError, RuntimeError) as exc:
            result['quality_layer_status'] = 'Optional MOLA count-grid check unavailable: ' + str(exc)
    return result


def earth_quality(candidates):
    return {'product':'NOAA ETOPO1 Ice Surface',
            'native_grid_spacing_km_north_south_approx':1.85,
            'effective_resolution':'Varies with the source survey and composite; not established at 1 arc-minute everywhere.',
            'finite_regional_grids':all(candidate['features']['valid_cells'] == 121 for candidate in candidates),
            'quality_layer_status':'Source-by-source observation quality and uncertainty are not mapped to the regional samples.',
            'warnings':['ETOPO1 combines different land and ocean source surveys; identical grid spacing does not imply identical effective terrain detail.',
                        'Earth mean-sea-level, lunar reference-sphere, and Martian areoid heights are not directly compared as absolute elevations.']}
