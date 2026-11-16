# Independent complete-window reconstruction

**Status: verified numerical reproduction of the current sampled topography, not independent scientific validation of planetary analogs.** The existing API, ranking, source catalog, and default 220 km/11 by 11 baseline remain unchanged. Full machine-readable evidence is written to ignored `backend/data/independent-window-report.json`.

## Method and source registration

`backend/independent_window_validation.py` does not call production coordinate conversion, raster interpolation, window aggregation, feature extraction, or KNN functions to obtain its expected values. Rasterio/GDAL opens the exact checksum-verified detached PDS labels and IMG bytes for LOLA `LDEM_4` and MOLA `MEGT90N000CB`. The MOLA PDS registration uses the [GDAL-documented half-pixel corrections](https://gdal.org/en/stable/drivers/raster/pds.html). Heights use the label's 0.5 m/DN LOLA scaling, with the radius offset excluded, and 1 m/DN for MOLA. The PDS labels define four angular pixel centers per degree, north-up at 89.875 degrees N and eastward from 0.125 degrees E. Their rounded projected `MAP_SCALE` is not substituted for the more precise angular label registration; using the GDAL projected affine instead is a distinct coordinate convention and led to meter-scale center differences in the previous audit. NoData source neighborhoods fail instead of silently creating valid cells.

Each of the seven original NOAA ETOPO1 Ice Surface subsets is read again from its checksum-matched original ERDDAP CSV. The CSV fields declare degrees north, degrees east, and meters. Latitude/longitude node positions are independently checked for complete one-arc-minute regular coverage. A node-registered EPSG:4326 GeoTIFF is constructed in a Rasterio `MemoryFile`, reopened, and every elevation node is compared exactly to the source CSV. The seven window centers and subsets are the existing catalog, not newly selected locations. [NOAA ETOPO1 product details](https://www.ncei.noaa.gov/sites/default/files/2023-01/Product%20Details.pdf) distinguish node- and pixel-registered versions; this experiment uses the CSV's explicit geographic nodes as pixel centers.

For each 220/180/260 km configuration, the independent local sampling coordinates are calculated by mapping east/north tangent vectors onto each body's sphere. For offset vector **v** at radius *R* from center unit vector **u**, the endpoint is `cos(|v|/R) u + sinc(|v|/(pi R)) v/R`, with **v** assembled from local east and north basis vectors. Longitude is normalized to a periodic 0–360 degree axis for planetary products. This is algebraically equivalent to the production inverse azimuthal-equidistant mapping but coded with a different vector construction.

For each grid cell, 25 offsets at -0.4, -0.2, 0, +0.2, +0.4 times cell spacing in both directions are independently converted to latitude/longitude. Rasterio's affine converts those coordinates to fractional pixel-center positions. Four source heights are combined as `z00 + fx(z01-z00) + fy(z10-z00) + fx fy(z11-z10-z01+z00)`. The 25 heights are averaged. This validates every query separately; the production functions are called **afterward** solely to measure disagreements. A bilinear interpolation calculation is a numerical estimate from four existing pixels, not an additional observation.

The independent descriptors use a sorted linear percentile with index `(n-1)p`, interior centered differences `(z[i,j+1]-z[i,j-1])/(2s)` and `(z[i+1,j]-z[i-1,j])/(2s)`, slope `atan(hypot(gx,gy))` converted to degrees, and the RMS of residuals after fitting an intercept plus centered x/y plane. On a complete symmetric grid, the centered plane coefficients are the covariance of x or y with elevation divided by their respective sums of squares. The reference and all seven Earth grids are evaluated with the same physical cell spacing *s*. Earth-only IQR uses sorted, linearly interpolated 75th minus 25th percentiles; distance is `sqrt(mean(((Earth - reference)/Earth_IQR)^2))`. These independent definitions are compared to production output only after computation.

## All-window results

Five configurations × (four planetary references + seven Earth windows) give **55 complete windows** and **122,375 bilinear queries**: 25 times the sum of 11 squared, 7 squared, 5 squared, 9 squared, and 13 squared, multiplied by 11 windows. All source neighborhoods and output values were finite. The JSON reports per-window counts, maximum/mean/RMS query differences, three largest differences with coordinates and source cell indices, maximum grid difference, and every descriptor's production/independent values and absolute/relative difference.

| Comparison | Maximum absolute disagreement across all configurations |
| --- | ---: |
| LOLA query heights, ten windows | 5.90 × 10^-10 m |
| MOLA query heights, ten windows | 3.77 × 10^-10 m |
| ETOPO1 query heights, 35 windows | 8.87 × 10^-8 m, Sahara |
| Aggregated output grid cells | 1.13 × 10^-8 m, Sahara |
| P95-P5 range, all 55 windows | 5.65 × 10^-9 m, Pilbara |
| Median slope, all 55 windows | 1.62 × 10^-11 degree, Sahara |
| Plane-detrended RMS, all 55 windows | 4.66 × 10^-10 m, Pilbara |
| Standardized neighbor distance, all 20 analyses | 3.79 × 10^-11, Tycho at 260 km |

Across the 22,250 lunar queries, the weighted mean absolute difference is 1.57 × 10^-11 m and RMS difference is 4.21 × 10^-11 m. Across 22,250 Martian queries, these are 1.91 × 10^-11 m and 4.05 × 10^-11 m. Across 77,875 terrestrial queries, they are 2.39 × 10^-9 m and 4.82 × 10^-9 m. The largest lunar query difference is in Tycho's 260 km window at approximately 46.7223 S, 17.3269 W; the largest Martian difference is in Gale's 5 by 5 window at 5.1024 S, 138.6944 E. The largest terrestrial difference is in the baseline Sahara window at 24.8235 N, 10.2774 E. Exact 25-sample indices, rows, columns, values and signed differences are in the JSON report for every window.

Maximum independently calculated coordinate disagreements are 2.13 × 10^-14 degree latitude and 5.68 × 10^-14 degree longitude. The largest Earth height differences arise from first-two-node versus median-step affine registration of rounded CSV coordinates and floating-point arithmetic. The JSON records the maximum fractional pixel-position disagreement and observed adjacent-pixel contrast for every window. Their product, summed across axes, plus a conservative binary64 arithmetic allowance gives a **data-derived numerical envelope**, not a terrain accuracy limit or a scientific similarity threshold. All 55 maximum query differences fall inside their respective envelopes. Absolute/relative descriptor differences, rather than a universal significance cutoff, are reported for every window. Near-zero descriptors require absolute differences because relative differences are unstable.

The previous single-point GDAL projected-affine comparison reported differences up to 3.122 m at Gale. That is a different angular versus rounded projected registration comparison. It does not contradict the sub-nanometer agreement here under the **same angular pixel-center convention**. It remains a methodological choice that should be reviewed against source label documentation, not silently ignored.

## Scale and ranking reproduction

The independent path recomputed all Earth IQRs, 20 complete seven-candidate rankings, and per-descriptor Earth range diagnostics. Every ordered ranking, winner, and list of descriptors outside the observed Earth ranges agrees with the saved production experiment. The largest distance difference is 3.79 × 10^-11. No ranking or extrapolation diagnostic was changed.

| Configuration | Tranquillitatis | Tycho | Jezero | Gale |
| --- | --- | --- | --- | --- |
| 220 km / 11 × 11, 20 km spacing | Colorado Plateau | Atacama | Atacama | Atacama |
| 220 km / 7 × 7, 31.429 km | Ladakh | Atacama | Atacama | Atacama |
| 220 km / 5 × 5, 44 km | Death Valley | Ladakh | Atacama | Atacama |
| 180 km / 9 × 9, 20 km | Colorado Plateau | Atacama | Atacama | Atacama |
| 260 km / 13 × 13, 20 km | Death Valley | Atacama | Atacama | Atacama |

The fixed-width density experiment changes cell centers and quadrature width as well as sample count. The extent experiment changes the physical region while retaining 20 km cell strategy. The independently extracted Tranquillitatis reference range rises from 1,395 m at baseline to 1,889 m at 260 km; its largest plane residual moves from about +637 m at 2.624 S, 23.473 E to +1,396 m at 3.283 S, 22.813 E. These grid-cell diagnostics identify where the changed window includes more extreme sampled terrain; they are not a proof of a specific geological cause. The winner margin at 260 km is only 0.00284 standardized distance units. At 5 × 5, the first-ranked result is Death Valley after **IQR recalibration**, while Ladakh would rank first if the original baseline Earth IQR were retained. Thus this particular winner change involves both sampling/descriptor changes and recalibration. The 7 × 7 Ladakh and 260 km Death Valley changes persist under a fixed baseline IQR.

Tycho's 220 km P95-P5 range falls from 2,827 m on 11 × 11 to 1,793 m on 5 × 5; median slope falls from 2.081 to 0.355 degrees. The steepest *interior* cell falls from 7.47 degrees at about 42.647 S, 10.463 W to 2.11 degrees at about 41.859 S, 11.360 W. The 5 × 5 sparse grid estimates the crater-related gradients using only nine interior slope cells. Ladakh then outranks Atacama by 0.01779 distance units, **even with the original Earth IQR fixed**. This is evidence of sampling/feature sensitivity, not evidence of a data-decoding error. The possibility of LOLA strip-boundary artifacts near Tycho remains unresolved.

Jezero and Gale retain Atacama across five configurations and with fixed baseline IQR. The first-to-second distance gaps vary: Jezero ranges from 0.07 at 180 km to 2.05 on 5 × 5; Gale from 0.84 at 180 km to 3.13 on 5 × 5. This is stability **within the existing seven-window catalog**. Gale exceeds the terrestrial range in all three descriptors at every tested scale; Tycho exceeds at least one. Reference extrapolation is unchanged by independent numerical reconstruction, but the *scale* changes which Tycho descriptors are outside the catalog.

## What is and is not established

The complete numerical pipeline is reproduced from the cached original source bytes under the stated pixel-center, spherical, bilinear, percentile and distance definitions. Agreement establishes implementation reproducibility, not instrument accuracy, adequate effective spatial resolution, surface-process equivalence or a validated analog. At the equator, the nominal latitude-node intervals are about 7.6 km for LOLA, 14.8 km for MOLA, and 1.85 km for ETOPO1; longitudinal ground spacing also changes with latitude. The 20 km output interval does not imply that 4 km subcell interpolation resolves 4 km structures. Consequently, slope and residual relief may reflect different instrument-scale smoothing even when their output grids agree exactly. ETOPO1's nominal node interval and underlying composite detail differ; LOLA and MOLA have different acquisition and gridding properties. The available metadata do not support a quantitative measurement-error distribution for these eleven windows, nor a universal common effective-resolution estimate. The sample-size and feature-correlation limitations in the [previous scale report](spatial-scale-experiment.md) remain.

No source, API, candidate, feature, model, ranking threshold, default scale or frontend element was changed. Future work should compare independently supported effective resolution and observation quality near the influential cells, especially Tycho, before judging which physical scale best answers a specified exploration question.

## Reproduce in Windows PowerShell

```powershell
Set-Location 'C:\Users\jessi\Documents\Codex\2026-11-14\new-chat-2\Eksoterris'
backend/.venv/Scripts/python.exe -m pip install rasterio==1.5.2
backend/.venv/Scripts/python.exe backend/spatial_scale_experiment.py
backend/.venv/Scripts/python.exe backend/independent_window_validation.py
backend/.venv/Scripts/python.exe -m unittest discover -s backend -p 'test_*.py' -v
```

Rasterio is an optional validation dependency in the ignored virtual environment. The first two scripts require the previously acquired, checksum-verified LOLA, MOLA and seven ETOPO1 cached subsets. The scale report supplies configuration and source identities; the independent script fails when those inputs are absent instead of substituting simulated terrain. The source data, independent report and production run JSON remain under ignored `backend/data/`. All project artifacts and console messages are in English.
