# Independent PDS decoding and controlled spatial-scale experiment

Status: experimental validation on the existing four planetary references and seven terrestrial windows. The application's 11 × 11, 20 km baseline is unchanged. No new candidate or scientific variable was introduced. Machine-readable outputs are saved to ignored `backend/data/independent-decoder-report.json` and `backend/data/spatial-scale-report.json`.

## Scientific question and source support

LOLA `LDEM_4` is a 4-pixel/degree Moon radius-relative height grid; MOLA `MEGT90N000CB` is a 4-pixel/degree Mars areoid-relative topography grid. ETOPO1 Ice Surface has 1-arc-minute geographic nodes, but its effective terrain resolution varies with its composite input sources. The native nominal equatorial intervals are about 7.58 km, 14.82 km and 1.85 km north-south, respectively. The baseline places output centers 20 km apart and averages 25 bilinear lookups within each nominal cell. At 4 km between nearby subcell lookups, the planetary DEMs are oversampled: interpolation changes where the reconstructed surface is queried, not how much was originally observed. See the [registration audit](geospatial-validation.md) and the official [GDAL PDS driver](https://gdal.org/en/stable/drivers/raster/pds.html), [PDS MOLA georeferencing guidance](https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/extras/mola_envi.htm) and [NOAA ETOPO1 report](https://www.ncei.noaa.gov/sites/default/files/2020-04/ETOPO1.pdf).

The following quantities have distinct meanings: the source pixel interval is the distance between grid positions; the output sampling interval separates calculated terrain cells; window width defines the geographic region being summarized; effective spatial resolution depends on instrument footprint, coverage, gridding and smoothing; the 4 km subcell interpolation interval is only numerical quadrature. No tested output grid can resolve a feature absent from the source DEM.

## Independent decoder: exact cached source bytes

Rasterio 1.5.2 with GDAL 3.12.2 was installed **only in the existing ignored backend virtual environment for this audit**. It is not an application/runtime dependency. The archived, SHA-256-verified IMG and detached PDS3 label bytes were copied under their original product basenames into the ignored `backend/data/validation-pds` directory because GDAL follows the image filename in the detached label. The copies are checked against the acquisition manifests; no substitute dataset or modified label is used. GDAL's independent PDS driver opens both labels as 720 × 1440 signed 16-bit arrays with projected, body-fixed equirectangular coordinates.

GDAL reports LOLA scale 0.5 and offset 1,737,400 m. The offset yields planetary radius when applied to the scaled digital number; Eksoterris intentionally compares **height relative to the reference sphere** and applies only the 0.5 m scale. MOLA scale is 1 m with offset 0. GDAL reports `-32768` as NoData for both products; no such value occurs in these exact cached images. The maximum difference over **every decoded source pixel** between GDAL and the production decoder, after the appropriate height scaling and north-to-south row reversal, is **0 m** for each product.

The official GDAL PDS documentation specifies `PDS_SampleProjOffset_Shift=-0.5` and `PDS_LineProjOffset_Shift=-0.5` for this MOLA label. Without these options, GDAL selects row/column 287/311 for Jezero and 382/552 for Gale, one pixel off the correctly shifted 286/310 and 381/551. The current Eksoterris coordinate axes agree with the *shifted* positions. The label's rounded `MAP_SCALE` of 14.818 km/pixel also differs from 2π × 3396 km / 1440 = 14.817845349 km/pixel. GDAL consequently places some projected pixel centers slightly away from the exact 0.25-degree angular centers used by the production decoder. LOLA's rounded map scale differs much less from the circumference-derived value. These are registration details, not disagreements about the IMG bytes.

| Reference | Source row, column (north-up, zero-based) | GDAL pixel height (m) | Production pixel height (m) | Pixel difference (m) | GDAL bilinear at reference (m) | Production bilinear (m) | Production minus GDAL bilinear (m) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Mare Tranquillitatis | 357, 93 | -1883.0 | -1883.0 | 0 | -1921.454 | -1921.442 | +0.012 |
| Tycho | 533, 1394 | -1858.5 | -1858.5 | 0 | -2303.427 | -2303.519 | -0.092 |
| Jezero | 286, 310 | -2651.0 | -2651.0 | 0 | -2617.192 | -2616.304 | +0.888 |
| Gale | 381, 551 | -893.0 | -893.0 | 0 | -1577.548 | -1580.670 | -3.122 |

The bilinear comparison uses GDAL's bilinear resampling at the same projected target coordinate; it does not call the production interpolation to generate an expected value. Small differences combine GDAL's rounded label map scale, coordinate placement and interpolation arithmetic. They should not be rounded away into a claim of identical continuous surfaces. Full-array pixel equality establishes byte decoding and orientation; the target center checks support registration, but do not establish independent geodetic accuracy or source measurement quality. No elevation-derived ranking was substituted with the GDAL output.

## Experimental design

The baseline definitions of P95–P5, median interior gradient slope and plane-detrended RMS are applied identically to every experimental grid. The baseline uses the production 11 × 11 method; the experiment additionally checks that its separately constructed 11 × 11 grid and descriptors agree numerically before comparing alternatives. Candidate selection, source rasters, coordinate centers, bilinear quadrature, Earth-only IQR fitting, three-feature scaled Euclidean distance, range diagnostics and tie-breaking remain unchanged.

| Configuration | Question | Output cells | Spacing | Nominal width | Interpretation |
| --- | --- | ---: | ---: | ---: | --- |
| Baseline | Reference | 11 × 11 | 20 km | 220 km | Original result, not replaced. |
| Density 7 | Sampling density | 7 × 7 | 31.429 km | 220 km | Same nominal geographic footprint with fewer cell estimates; the 25 bilinear offsets scale to each cell. |
| Density 5 | Sampling density | 5 × 5 | 44 km | 220 km | Stress test; only nine interior slope cells and 25 values for percentiles. Not a recommended production setting. |
| Extent 180 | Window dimensions | 9 × 9 | 20 km | 180 km | Same cell strategy, smaller region. |
| Extent 260 | Window dimensions | 13 × 13 | 20 km | 260 km | Same cell strategy, larger region. |

The density experiment preserves nominal width but changes both output-center positions and cell quadrature width. It therefore measures the effect of the *whole sampling strategy*, not a pure change in point count at identical positions. The extent experiment preserves 20 km spacing and quadrature offsets. These distinctions are recorded in the JSON output. Any source-coverage failure marks a configuration invalid rather than forcing a ranking. The optional MOLA count grid reports no zero-shot original bins touched by the tested Martian reference configurations; it does not quantify elevation errors.

## Results: four references

Distances use the **Earth IQR refitted independently for each configuration**. They are not calibrated probabilities, and numerical distances across scales are not directly comparable as a physical measure of analog quality. Spearman rho compares the seven ranks with the baseline; top-three overlap is the number of shared candidates in the first three positions.

| Reference | Baseline winner / distance | Density 7 winner / distance; rho | Density 5 winner / distance; rho | Extent 180 winner / distance; rho | Extent 260 winner / distance; rho |
| --- | --- | --- | --- | --- | --- |
| Tranquillitatis | Colorado Plateau / 0.43549 | Ladakh / 0.37696; 0.857 | Death Valley / 0.67146; 0.893 | Colorado Plateau / 0.41187; 0.679 | Death Valley / 0.53213; 0.893 |
| Tycho | Atacama / 2.29231 | Atacama / 2.15383; 1.000 | Ladakh / 3.03735; 0.250 | Atacama / 2.90350; 0.964 | Atacama / 2.22774; 0.929 |
| Jezero | Atacama / 0.72177 | Atacama / 0.85454; 1.000 | Atacama / 1.37910; 0.929 | Atacama / 1.07360; 0.964 | Atacama / 0.65574; 0.964 |
| Gale | Atacama / 2.25677 | Atacama / 2.52743; 1.000 | Atacama / 2.97879; 0.964 | Atacama / 3.19013; 0.964 | Atacama / 1.59288; 0.964 |

Tranquillitatis's top-three overlap remains 3/3 in both density changes and the 260 km extent, despite winner changes; it drops to **1/3** for 180 km. Tycho's 5 × 5 scenario has top-three overlap **2/3** and moves Atacama from first to seventh. The other tested comparisons have top-three overlap 3/3. Full seven-candidate ranking, descriptor values for every candidate, Earth IQR, squared-distance contribution by descriptor, distance differences and SHA-256 source identities are in the reproducible JSON report.

### Descriptor and calibration changes

| Reference | Baseline P95–P5 (m), slope (°), RMS (m) | Density 7 | Density 5 | Extent 180 | Extent 260 |
| --- | --- | --- | --- | --- | --- |
| Tranquillitatis | 1395.3, 0.577, 250.8 | 1351.3, 0.556, 230.5 | 1297.8, 0.487, 212.0 | 1245.1, 0.619, 194.3 | 1889.0, 0.482, 344.4 |
| Tycho | 2827.0, 2.081, 901.5 | 1985.4, 1.075, 705.6 | 1792.7, 0.355, 703.2 | 3275.7, 2.462, 977.0 | 2522.3, 2.122, 833.5 |
| Jezero | 2894.2, 0.933, 233.3 | 2821.2, 0.918, 198.9 | 2764.3, 0.879, 176.8 | 2426.9, 0.944, 165.8 | 3162.5, 0.872, 269.8 |
| Gale | 3725.2, 2.063, 899.2 | 3499.1, 1.545, 822.6 | 3196.4, 1.295, 775.5 | 3990.1, 2.980, 904.3 | 3618.3, 1.510, 865.4 |

The corresponding Earth IQRs for range/slope/RMS change from **702.10 m / 0.379° / 168.84 m** at baseline to **486.72 / 0.240 / 124.97** for density 7 and **396.17 / 0.127 / 93.57** for density 5. At extent 180 they are **666.01 / 0.436 / 149.68**; at extent 260, **724.68 / 0.398 / 173.84**. Thus distance and feature contribution changes reflect both changing terrain descriptors and recalibration on the same seven Earth sites. For Tycho–Atacama, the squared-distance slope contribution drops from 2.074 at baseline to 0.004 for density 7, while the range contribution rises from 0.168 to 1.916. Numerical contributions describe this metric at one scale; they are not causal or geological importance.

### Extrapolation diagnostics

Tranquillitatis and Jezero stay within each individual terrestrial descriptor range under every tested configuration; this does not establish a close joint match. Gale is **above all three terrestrial descriptor ranges in every configuration**. Tycho is above terrestrial slope and RMS ranges at baseline, density 7 and extent 260. At density 5 only its RMS lies above the Earth range; at extent 180 all three lie above. These diagnostics warn about catalog support without imposing a distance threshold. The change in Tycho's individual range status reflects changing measurements and terrestrial ranges, not validated similarity.

## Interpretation and limits

Tranquillitatis is the clearest ranking-stability concern: small shifts were already known to change its winner, and both a fixed-width density change and a wider extent do so here. Tycho retains Atacama at 7 × 7 but changes both winner and full rank structure at 5 × 5; its LOLA 45°S strip quality remains inconclusive. Jezero and Gale keep Atacama first in this narrow catalog, yet Gale never enters the observed terrestrial descriptor ranges. The same candidate appearing first repeatedly is still only a relative nearest-neighbor result.

Coarser output sampling reduces the amount of interpolation detail represented in the descriptors but does not equalize source observation quality. It can discard meaningful regional relief, especially around a crater, and its small-cell-count estimators are more variable. These results do **not** establish a superior universal scale. Retain 20 km as the explicitly labeled baseline; treat 31.429 km as a sensitivity result and 44 km as a stress test. A production scale recommendation requires a defined mission question, source effective-resolution/quality estimates, more terrestrial windows and external validation. Do not tune the scale to retain a preferred winner.

## Reproduction

From PowerShell in the **development copy**:

```powershell
Set-Location 'C:\Users\jessi\Documents\Codex\2026-11-14\new-chat-2\Eksoterris'
backend/.venv/Scripts/python.exe -m pip install rasterio==1.5.2
backend/.venv/Scripts/python.exe backend/independent_decoder.py
backend/.venv/Scripts/python.exe backend/spatial_scale_experiment.py
backend/.venv/Scripts/python.exe -m unittest discover -s backend -p 'test_*.py' -v
npm.cmd run build
```

The Rasterio installation is optional and limited to validation; do not add it to the application requirements solely to reproduce the normal ranking. Both experimental scripts require the already acquired and SHA-256-verified LOLA, MOLA and seven ETOPO1 subsets in ignored `backend/data`. No credentials are needed for this cached experiment. `independent_decoder.py` writes a copy only within the ignored validation directory so the original detached PDS labels can locate their image files. The experiments do not alter `science.py`, the default API method or existing result files. They write separate JSON outputs in `backend/data`.
