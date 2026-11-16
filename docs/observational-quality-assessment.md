# Observational quality and effective resolution assessment

**Scope and status.** This is an assessment of the existing LOLA `LDEM_4`, MOLA `MEGT90N000CB`, and NOAA ETOPO1 Ice Surface comparisons. It uses the saved [geospatial registration audit](geospatial-validation.md), [scale experiment](spatial-scale-experiment.md), [independent window reconstruction](independent-window-validation.md), cached source labels, and the existing experiment JSON reports. It does not rerun the 122,375 queries, acquire another dataset, alter production rankings, or validate any planetary analog.

## Evidence levels and terminology

| Term | Meaning here | What it does not establish |
| --- | --- | --- |
| Nominal grid spacing | Distance between neighboring product pixel centers, derived from the product's angular grid and body radius. | Instrument footprint, terrain detail actually retained, or vertical accuracy. |
| Effective spatial resolution | Smallest terrain variation that the acquisition, coverage, gridding, and processing can reliably represent *locally*. | It cannot be read from pixel spacing alone and has not been established for these eleven windows. |
| Measurement accuracy | Agreement between reported heights and an independent physical reference, with an appropriate error model. | Byte-for-byte decoder agreement or numerical reproducibility. |
| Observation support | Whether contributing source bins contain recorded observations, where a matching count product exists and has been checked. | Accuracy of a bin median, independence of interpolated outputs, or complete coverage at finer scales. |

**Verified locally:** All previously reported complete-window samples and descriptors were reproduced by the independent implementation under the stated angular registration and interpolation convention. The five saved configurations and rankings were independently reproduced. This is a check on implementation, not on the underlying measurements. See the machine-readable `backend/data/independent-window-report.json` and `backend/data/spatial-scale-report.json` (ignored by Git), and the corresponding reports above.

**Supported by producer metadata:** The [LOLA `LDEM_4` label](https://imbrium.mit.edu/DATA/LOLA_GDR/CYLINDRICAL/IMG/LDEM_4.LBL) describes a 4-pixel-per-degree gridded shape map relative to a 1,737.4 km sphere, generated in 45-degree latitude bands with *possible* edge artifacts. The label says GMT `surface` compensated for incomplete coverage **at higher resolutions**; it does not establish that this interpolation procedure was applied to every `LDEM_4` pixel. The [LOLA archive description](https://imbrium.mit.edu/DOCUMENT/archsis.htm) says gridded products may be scaled and interpolated where necessary. The [MOLA topography label](https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg004/megt90n000cb.lbl) explicitly permits interpolated elevations in bins with no shots; its approximately 55% equatorial occupied-bin figure is a broad product description, not a measurement of Jezero or Gale. [NOAA ETOPO1](https://www.ncei.noaa.gov/sites/default/files/2020-04/ETOPO1.pdf) is assembled from heterogeneous sources. Its [node registration](https://www.ncei.noaa.gov/sites/g/files/anmtlf171/files/2023-01/Product%20Details.pdf) and one-arc-minute spacing do not imply uniform local terrain resolution.

**Not established:** A local LOLA count map, shot-track coverage, cell-level uncertainty, and independent terrain truth for Tycho or Tranquillitatis have not been evaluated in this project. No common effective resolution or quantitative error distribution has been derived for the three products. A finite DEM value is not proof of a directly observed elevation.

### Available coverage products, without claiming they have been applied

The LOLA archive [lists `LDEC_4.IMG` and its label](https://imbrium.mit.edu/DATA/LOLA_GDR/CYLINDRICAL/IMG/), and the [LOLA archive specification](https://imbrium.mit.edu/DOCUMENT/archsis.htm) describes digital elevation counts as samples per pixel. A [LOLA data workshop](https://pds-geosciences.wustl.edu/workshops/LRO_DataUsersWorkshop/2014/LOLA.pdf) explains that a zero in an LDEC product denotes a coverage gap with an interpolated elevation. **This `LDEC_4` pair was identified in the official listing, but its exact label, version correspondence, registration, pixels, and alignment with the cached `LDEM_4` have not been verified locally.** It must not yet be used to declare either lunar window directly observed or interpolated. This is the smallest promising next observational check, subject to verifying product correspondence first.

By contrast, the existing MOLA companion `MEGC90N000CB` count grid was checked against the elevation product's registration and source-bin support. Each of the Jezero and Gale baseline windows touches 289 bins with nonzero bilinear weight, and all 289 have positive count; the ranges are 247–1,100 and 107–1,205 shots per touched bin respectively. This excludes zero-count input bins **for these particular sampled neighborhoods**, without measuring local elevation error. The companion count values are never treated as extra elevations or interpolated into a continuous quality score. See the [geospatial audit](geospatial-validation.md) and [`terrain_quality.py`](../backend/terrain_quality.py).

## What changed in the lunar experiments

The nominal source spacing is about **7.58 km north–south for LOLA**, **14.82 km for MOLA**, and **1.85 km for ETOPO1** at their respective equators. East–west ground spacing varies with latitude. The baseline window is nominally 220 km wide, with 11 by 11 cell centers separated by 20 km. Each cell averages 25 bilinear queries at 4 km subcell intervals; these are numerical evaluations of the source grids, not 25 new observations. Median slope uses interior centered differences spanning 40 km between opposite neighbor centers. The percentile range and plane-detrended RMS summarize the full window. Both the density experiments and their 25-point cell averaging change the effective numerical smoothing when cell spacing changes; they cannot isolate sampling density from every other aspect of the estimator.

| Lunar reference | 220 km / 11 by 11 baseline: range, median slope, RMS | 220 km / 7 by 7 | 220 km / 5 by 5 | 180 km / 9 by 9 | 260 km / 13 by 13 |
| --- | --- | --- | --- | --- | --- |
| Tycho | 2,827.0 m; 2.081°; 901.5 m | 1,985.4 m; 1.075°; 705.6 m | 1,792.7 m; 0.355°; 703.2 m | 3,275.7 m; 2.462°; 977.0 m | 2,522.3 m; 2.122°; 833.5 m |
| Tranquillitatis | 1,395.3 m; 0.577°; 250.8 m | 1,351.3 m; 0.556°; 230.5 m | 1,297.8 m; 0.487°; 212.0 m | 1,245.1 m; 0.619°; 194.3 m | 1,889.0 m; 0.482°; 344.4 m |

These are *computed descriptors*, not measurement uncertainty estimates. Values and exact source hashes are recorded in the saved scale and independent-window reports.

### Tycho: spatial influence and unresolved strip quality

The baseline's steepest **interior slope cell** is about **7.47° at 42.647°S, 10.463°W**. On the 5 by 5 grid, the steepest interior cell is about **2.11° at 41.859°S, 11.360°W**; only nine cells remain eligible for interior slopes. The baseline's largest plane residual is about **−2,863 m at 43.306°S, 10.454°W**; on the 5 by 5 grid it is about **−2,681 m at 43.310°S, 11.360°W**. The two grids sample different positions, so the drop in the median slope is consistent with a density/placement effect on heterogeneous terrain. The extreme cell does not, by itself, determine a median, RMS, or geologic cause. The 5 by 5 winner becomes Ladakh instead of Atacama even when the baseline Earth IQR is retained, showing that recalibration alone cannot explain that winner change. Tycho exceeds the seven Earth windows' slope and RMS ranges at baseline; a nearest candidate therefore remains only relative to the limited catalog.

The actual Tycho baseline subcell positions span **46.872°S to 39.652°S**: **795 of 3,025** queries lie south of 45°S; **33 of 121** output cells contain such a query and **six** straddle the boundary. The steepest cell and largest residual cited above lie north of 45°S, but gradients and plane fits can depend on surrounding cells. The previously performed adjacent-row comparison around the 45°S boundary found no exceptional step *by that diagnostic*. It did not test shot coverage, along-track patterns, or against an independent DEM. **Artifact status: inconclusive.** Spatial coincidence with a warned boundary is not evidence that the measured descriptor changes were caused by an artifact; neither is a nonexceptional row median evidence that no artifact exists.

### Tranquillitatis: window and calibration sensitivity

At baseline, the steepest interior cell is about **1.44° at 1.964°S, 24.133°E**, and the largest plane residual about **+637 m at 2.624°S, 23.473°E**. Widening the window to 260 km while keeping 20 km cell spacing places the largest residual at **3.283°S, 22.813°E, about +1,396 m**, and the steepest interior cell at **2.624°S, 22.813°E, about 2.48°**. The widened footprint includes different outer cells; its P95–P5 and RMS increase substantially. This identifies influential sampled positions, not their geologic origin or observational reliability.

The baseline winner is Colorado Plateau; 7 by 7 yields Ladakh, 5 by 5 yields Death Valley, and 260 km yields Death Valley. The 260 km first-to-second distance margin is only **0.00284** in this calculation's scaled units. The 5 by 5 Death Valley result depends on recomputing the seven Earth-window IQRs; retaining baseline IQR makes Ladakh first. The 7 by 7 and 260 km winner changes persist with baseline IQR held fixed. Prior reference-only center shifts of 20 km in each cardinal direction also changed the winner. These outcomes implicate sampling geometry, included terrain, and calibration in different scenarios. They do **not** distinguish terrain variability from unmeasured LOLA shot gaps or product artifacts. This window does not intersect the particular 45°S production boundary warning, but observation support is still unmeasured.

## Cross-product comparability and the 220 km decision

| Comparison issue | Established evidence | Consequence |
| --- | --- | --- |
| Height reference | LOLA gives height relative to a 1,737.4 km reference sphere; MOLA topography uses the GMM3 areoid; ETOPO1 uses a sea-level reference. | The current distance excludes absolute mean elevation. Relief, local slope, and plane-detrended RMS can be compared as **defined numerical summaries**, subject to quality and scale caveats; equal values do not imply equivalent geology or mission conditions. |
| Source support | MOLA counts were examined locally; corresponding LOLA `LDEC_4` support has not been aligned/checked; Earth CSVs lack a per-cell source-quality map. | The information available for weighting or excluding questionable cells differs by body. Do not apply a quality mask to one body and declare all outputs equivalent. |
| Spacing and processing | The three grids have different angular intervals, body radii, instrument histories, interpolation, and Earth composite inputs. | Matching 11 by 11 output dimensions or interpolating to 4 km queries cannot supply a shared effective spatial resolution. Gradients and relief can respond differently to smoothing and missing underlying detail. |
| Numerical reproducibility | Independent GDAL/CSV window calculations reproduce all saved queries and rankings within reported floating-point differences. | Registration and algorithm consistency are supported under the adopted conventions; source truth, local accuracy, and analog validity remain open. |

**Decision:** Retain the 220 km / 11 by 11 / 20 km baseline **as a named exploratory regional comparison**. There is no demonstrated decoding or registration defect and no evidence-based replacement scale. Do not present the first-ranked Earth site as a validated analog. For Tycho, display the existing out-of-range and seam/coverage caveats alongside the relative ranking. For Tranquillitatis, display the existing scale and center sensitivity alongside the relative ranking; its descriptor-by-descriptor inclusion within Earth ranges is not a joint match or a stability guarantee. The 220 km choice is defensible for reproducible broad-window *exploration*, but the current evidence is insufficient to defend a unique site conclusion for either lunar reference.

## Smallest next validation steps

1. **Verify lunar source support at the influential cells.** Inspect the official `LDEC_4` detached label, release/version relation to `LDEM_4`, angular registration, counts, and NoData semantics. If compatible, map the source bins with nonzero bilinear weight for each lunar window, including the Tycho boundary and the cited high-gradient/residual cells. Compare count-zero prevalence at baseline and alternative scales. This adds a coverage diagnostic, not a new terrain feature or confidence percentage. **Investigated as available; not acquired or implemented.**
2. **Check the Tycho boundary and influential lunar cells against a separate observation path.** Examine geolocated LOLA RDR shots or an independently processed lunar elevation product with documented reference-surface and registration conversion. A product derived from the same LOLA shots offers a processing cross-check, not independent instrument truth. Determine whether any seam-specific discrepancy remains after coverage and spatial scale are considered. **Not performed.**
3. **Constrain terrestrial effective detail only where it affects the comparison.** Trace the ETOPO1 local source/provenance for the seven existing windows and document relevant source scale or resampling; check a limited set of influential sites before proposing a common effective analysis scale. This does not add candidates or switch to SRTM. **Not performed.**

None of these steps warrants changing the default scale or ranking until a verified defect or a mission-specific validation criterion is established. A quantitative uncertainty model would require independent measurements and an explicit error/coverage model; no such numbers are assigned here.

## Reproduction and boundaries

From PowerShell in the **development copy**:

```powershell
Set-Location 'C:\Users\jessi\Documents\Codex\2026-11-14\new-chat-2\Eksoterris'
Get-Content docs/geospatial-validation.md
Get-Content docs/spatial-scale-experiment.md
Get-Content docs/independent-window-validation.md
Get-Content backend/data/validation-pds/LDEM_4.LBL
Get-Content backend/data/validation-pds/megt90n000cb.lbl
```

The cached IMG/CSV source files and machine-readable experimental reports are under ignored `backend/data/` and are not part of the Git checkout. Their earlier SHA-256 checks and independent calculations are documented in the linked reports. This assessment reads those existing results rather than re-running them. It makes no change to `backend/science.py`, `backend/terrain_knn.py`, the API, the user interface, or any production behavior.
