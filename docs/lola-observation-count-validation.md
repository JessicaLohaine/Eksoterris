# LOLA LDEC_4 observation-count validation

**Status: verified pixel correspondence and descriptive source-bin support for the existing lunar windows.** This is an offline validation of NASA's original count and elevation grids, not a change to the ranking, quality weighting, default scale, or frontend. The machine-readable output is the ignored `backend/data/lola-count-validation-report.json`. Counts are observations contributing to *source bins*, not independent observations at each bilinearly interpolated query or a calibrated elevation uncertainty.

## Product identity and exact source bytes

| Product | Official source file | SHA-256 | Bytes |
| --- | --- | --- | ---: |
| LOLA count label | [`LDEC_4.LBL`](https://imbrium.mit.edu/DATA/LOLA_GDR/CYLINDRICAL/IMG/LDEC_4.LBL) | `ab220f2b95482f9d4a6e94a8714897e822492fe731aedaa1b275ba758869da13` | 3,942 |
| LOLA counts | [`LDEC_4.IMG`](https://imbrium.mit.edu/DATA/LOLA_GDR/CYLINDRICAL/IMG/LDEC_4.IMG) | `10ccc1253a7adab1ecb651d26b00ef6cbfa41107fd40f8998b5ab9fa5f9ee943` | 2,073,600 |
| LOLA elevation label | [`LDEM_4.LBL`](https://imbrium.mit.edu/DATA/LOLA_GDR/CYLINDRICAL/IMG/LDEM_4.LBL) | `b5a197b4d417e3b5e0e84f8fe15f9a1d2203b8eb5d7213236c0ffbc86e940cc6` | 5,107 |
| LOLA elevation | [`LDEM_4.IMG`](https://imbrium.mit.edu/DATA/LOLA_GDR/CYLINDRICAL/IMG/LDEM_4.IMG) | `972d66d7f330abca62abc21aae270661516c00dd1a881ec102b94df9563656b5` | 2,073,600 |

The [LOLA archive specification](https://imbrium.mit.edu/DOCUMENT/archsis.htm) identifies the LDEC gridded products as elevation counts, and the [LOLA data workshop](https://pds-geosciences.wustl.edu/workshops/LRO_DataUsersWorkshop/2014/LOLA.pdf) describes the count as the number of LOLA measurements averaged into a pixel; zero in an LDEC map is described as a gap with an interpolated value. The specific `LDEC_4.LBL` describes counts of topographic data points used to generate the corresponding gridded topographic product. This is a producer description of support, **not** evidence of the precision or independence of each contributing shot. Its generic text includes the phrase “preliminary LOLA data”; the matching product identity and metadata below, rather than that adjective, establish which archived products were compared.

Both labels specify PDS3 dataset `LRO-L-LOLA-4-GDR-V1.0`, version `V3.0`, acquisition interval **2009-07-13 to 2016-11-29**, product creation date **2017-09-15**, producer and instrument LOLA, and data through mission phase `LRO_ES_52`. The count label has `PRODUCT_ID=LDEC_4` and `NAME=COUNTS`. It does **not** name `LDEM_4` in a separate explicit counterpart field; correspondence is supported by its stated matching gridded topography, identical release/acquisition metadata, and the independent registration checks below. Counts are dimensionless nonnegative integers. The count label declares a minimum of 64 and maximum of 26,671; both match the decoded full image. It declares no special NoData value. GDAL reports a conventional `-32768` NoData for both PDS images; neither cached image contains that value. **The entire 4-pixel-per-degree count image contains zero zero-count pixels.** This is an observation about this product and release, not proof of uniformly accurate terrain or a claim that higher-resolution LOLA grids have no gaps.

## Independent decoding and pixel alignment

The detached labels specify 720 north-to-south rows by 1,440 eastward columns, signed 16-bit `LSB_INTEGER` (little-endian), four pixels per degree, simple cylindrical projection, east-positive 0–360-degree longitude, body-fixed Mean Earth/polar axis of DE421, and pixel registration. The angular pixel center at zero-based source row `r`, column `c` is `latitude = 90 - (r + 0.5)/4` degrees and `longitude = (c + 0.5)/4` degrees east. Thus the first center is 89.875°N, 0.125°E; the last is 89.875°S, 359.875°E. Longitude wraps between columns 1439 and 0. The `A/B/C_AXIS_RADIUS` values agree at 1,737.4 km. The radius in the count label describes map geometry, **not** a count unit or an elevation datum for the counts.

[`backend/lola_count_validation.py`](../backend/lola_count_validation.py) reads each original checksum-verified IMG as a little-endian array using NumPy and independently opens an unchanged, same-name copy with Rasterio/GDAL's PDS driver. All **1,036,800 pixels in each image** agree exactly between decoders, including orientation; the count image is never multiplied by the 0.5 m/DN scale that applies only to elevation. The script compares 27 registration/identity fields, normalizing the textual forms `0` and `0.` as equal numeric coordinates. Product version, acquisition times, coordinate system, projection offsets, dimensions, pixel type, angular resolution and direction all match.

The labels write `MAP_SCALE` with different decimal precision and units: **7,580.84 m/pixel** for LDEM and **7.580837606 km/pixel** for LDEC, a difference of **0.002394 m/pixel in the written metadata**. GDAL reports the same rounded pixel step but projected affine origins differing by **+1.72368 m east** and **−0.86184 m north** (LDEC minus LDEM). This is **not exact projected-affine equality**. The authoritative 0.25-degree angular centers, projection offsets, reference radius, and pixel ordering specified by both labels do agree exactly, so counts are paired by source **row/column**, never by a GDAL reprojection between the two slightly different affines. This supports pixel correspondence at the label-defined angular grid; it does not establish subpixel observational accuracy.

The validator checks both `MAP_SCALE` units and rejects a scale discrepancy that would accumulate to half a source pixel over half the 1,440-column map. This half-pixel bound is a geometric guard against gross registration disagreement, **not** a quality, similarity, or observational-confidence threshold. The actual origin differences above are far smaller than one pixel.

| Geographic control | Source row, column (zero-based) | Angular pixel center | Elevation from LDEM (m) | LDEC observations |
| --- | ---: | --- | ---: | ---: |
| Tycho analysis center (−43.31°, −11.36°) | 533, 1394 | 43.375°S, 348.625°E | −1,858.5 | 12,410 |
| Tranquillitatis analysis center (0.674°, 23.473°) | 357, 93 | 0.625°N, 23.375°E | −1,883.0 | 8,755 |
| North side of 45°S boundary | 539, 1395 | 44.875°S, 348.875°E | 657.5 | 16,737 |
| South side of 45°S boundary | 540, 1395 | 45.125°S, 348.875°E | 316.0 | 16,601 |
| Longitude seam, west | 359, 1439 | 0.125°N, 359.875°E | −768.5 | 4,966 |
| Longitude seam, east | 359, 0 | 0.125°N, 0.125°E | −796.0 | 5,550 |

These values were verified by independent signed little-endian reads at byte offset `2 × (row × 1440 + column)` in the tests; they are **not** independent ground-truth elevations. Synthetic tests detect one-pixel row/column projection-offset changes, north/south and east/west array inversions, single-pixel array rolls, byte swaps, incorrect longitude wrapping, and pixel-center mistakes. Negative/NoData count values fail validation; zero counts remain reportable rather than becoming observations.

## Counting support under the actual window queries

The validation reconstructs the existing five window configurations with the prior independent spherical coordinate method. Each cell's 25 query coordinates are mapped to their four potential bilinear source neighbors; only neighbors with **nonzero interpolation weight** are counted. Unique source bins are reported once per window, not once per query. Source counts themselves are **never bilinearly interpolated or summed into an invented output-cell count**. The saved influential-cell coordinates from the [independent window report](independent-window-validation.md) are checked against reconstructed coordinates before linking their supporting source bins to counts.

| Window | Distinct contributing bins | Minimum | P5 | Median | P95 | Maximum | Zero-count bins |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Tycho, baseline 220 km / 11 × 11 | 1,237 | 4,590 | 6,985 | 11,028 | 15,809.4 | 20,641 | 0 |
| Tranquillitatis, baseline 220 km / 11 × 11 | 930 | 1,904 | 3,312.85 | 6,555.5 | 9,081.75 | 13,138 | 0 |
| Tycho, 220 km / 5 × 5 | 1,215 | 4,590 | 6,968.7 | 11,055 | 15,697.5 | 20,641 | 0 |
| Tranquillitatis, 220 km / 5 × 5 | 900 | 1,904 | 3,306.7 | 6,549 | 9,093.75 | 13,138 | 0 |
| Tycho, 260 km / 13 × 13 | 1,746 | 4,590 | 7,216.25 | 11,058.5 | 16,050.5 | 21,825 | 0 |
| Tranquillitatis, 260 km / 13 × 13 | 1,296 | 1,834 | 3,347 | 6,568.5 | 9,087 | 13,138 | 0 |

The 220 km / 7 × 7 and 180 km / 9 × 9 windows were also checked, with zero zero-count contributing bins in both lunar references. Their complete summaries and the 11 × 11 per-output-cell minimum-count matrices are in the JSON. Descriptive percentiles of bin counts are **not quality thresholds**. They have different distributions and numbers of unique bins; neither the absolute counts nor their ratio across windows measures relative elevation accuracy. Baseline Tycho's minimum support bin is at 43.875°S, 348.125°E (4,590); Tranquillitatis's is at 4.375°N, 21.125°E (1,904). The maxima are at 43.125°S, 350.875°E (20,641) and 2.875°S, 23.375°E (13,138), respectively.

### Tycho and the 45°S strip boundary

The baseline's 3,025 bilinear queries include **795 south of 45°S**. The unique source support contains 344 bins centered south of 45°S (minimum 5,709; median 11,656.5) and 893 bins north of it (minimum 4,590; median 10,763). The 43 paired columns touched in the source rows centered at **44.875°S and 45.125°S** all have positive counts. Their median south-minus-north count difference is **+15** and median absolute difference **340** counts (maximum absolute difference **2,445**). These descriptive checks reveal no zero-count gap at this coarse grid boundary. They cannot detect a geometric seam, exclude the producer's possible edge-artifact warning, or attribute adjacent elevation differences to processing versus real relief.

| Previously identified baseline output location | Source bins with nonzero weight | Minimum–median–maximum counts | Interpretation |
| --- | ---: | --- | --- |
| Nearest output cell to the P5 elevation percentile | 20 | 5,512–7,648.5–12,365 | Context around a percentile; the range uses the full grid. |
| Nearest output cell to the P95 elevation percentile | 25 | 5,512–9,425–13,270 | This cell alone does not determine P95. |
| Steepest interior cell (7.47° at 42.647°S, 10.463°W) | 74 | 5,332–10,210–20,641 | Support of the four neighboring output cells used in its centered slope, not direct shots at the interpolated slope cell. |
| Largest plane residual (−2,863 m at 43.306°S, 10.454°W) | 20 | 6,066–7,594–11,681 | Support of that output cell; the fitted plane depends on the entire window. |

At 220 km / 5 × 5, the steepest interior cell's four neighbors draw on 234 bins (minimum **4,590**, median **10,431.5**, zero-count **0**) while its slope value changes to 2.11°. Because the sample centers and the distance used for spatial differencing change, this does **not** isolate a count effect. The data weaken a *zero-shot-bin at 4 ppd* explanation for the Tycho winner change; they do not rule out gridding artifacts at the strip boundary, uneven shot geometry within occupied bins, or real terrain variation. Artifact status remains **inconclusive**.

### Tranquillitatis and spatial-scale sensitivity

| Previously identified output location | Source bins with nonzero weight | Minimum–median–maximum counts | Interpretation |
| --- | ---: | --- | --- |
| Baseline nearest P5 cell | 16 | 4,451–7,132.5–8,035 | Percentile context only. |
| Baseline nearest P95 cell | 16 | 4,031–6,687–8,020 | Percentile context only. |
| Baseline steepest interior cell (1.44° at 1.964°S, 24.133°E) | 65 | 2,934–6,554–12,831 | Four slope-neighbor output cells. |
| Baseline largest plane residual (+637 m at 2.624°S, 23.473°E) | 20 | 3,408–6,442.5–13,138 | The fitted plane depends on all 121 output cells. |
| 260 km largest plane residual (+1,396 m at 3.283°S, 22.813°E) | 16 | 4,505–5,549.5–8,648 | An outer cell of a different footprint; not a direct accuracy comparison. |

Both windows have positive counts throughout the bins touched in all five tested configurations. A complete absence of contributing LOLA observations at the source-bin scale therefore does **not** explain the Tranquillitatis winner changes in these tests. The broadened footprint includes different elevations; a different Earth IQR also affects some winner changes. The count raster alone cannot distinguish physical relief, variable within-bin sampling, or DEM processing effects. Counts do not establish effective spatial resolution, per-cell accuracy, slope uncertainty, or a stable analog ranking.

## Consequences and decision

**Verified:** The specific V3.0 `LDEC_4` bytes are independently decoded, match the label extrema, and align with `LDEM_4` by the documented angular pixel centers and source indices. Every source bin used by the examined Tycho and Tranquillitatis queries has a positive count. Positive support is more informative than merely observing finite elevation values.

**Still unresolved:** The producer's Tycho strip-edge warning; distribution of original shots *inside* each 0.25-degree bin; shot quality and systematic geolocation error; whether gridding smooths the local terrain differently; local effective resolution and terrain truth. A count-positive bin can be processed, uncertain, or spatially uneven. The `LDEC_4` label has no per-shot quality or uncertainty field, and a higher count cannot by itself calibrate a descriptor confidence interval.

**Recommendation:** Retain this count product as an **optional, separate observational-support diagnostic** in future analyses after documenting the label pair and checksums. Do not mask observations, reweight descriptors, alter KNN, change the default scale, or turn counts into accuracy/confidence scores on this evidence alone. A targeted review of LOLA shot tracks and seam-sensitive elevations would be needed before a production quality rule could be defended. The existing exploratory rankings remain unchanged, and neither lunar region is validated as a planetary analog.

## Reproduce in PowerShell

Use a PowerShell terminal in the **development copy only**. These public NASA downloads require no credentials; the existing `fetch` function stores original bytes and SHA-256 manifests in ignored `backend/data/`.

```powershell
Set-Location 'C:\Users\jessi\Documents\Codex\2026-11-14\new-chat-2\Eksoterris'
backend/.venv/Scripts/python.exe -c "import sys; sys.path.insert(0, 'backend'); from sources import fetch, MOON_BASE; fetch(MOON_BASE + 'LDEC_4.LBL', 'lbl'); fetch(MOON_BASE + 'LDEC_4.IMG', 'img')"
backend/.venv/Scripts/python.exe backend/lola_count_validation.py
backend/.venv/Scripts/python.exe -m unittest discover -s backend -p 'test_lola_count_validation.py' -v
backend/.venv/Scripts/python.exe -m unittest discover -s backend -p 'test_*.py' -v
git diff --check
```

The validation script requires the previously cached, checksum-matched `LDEM_4` pair and `backend/data/independent-window-report.json` to locate the exact influential cells. It fails rather than combining unverified versions. Rasterio/GDAL is the **already installed optional validation dependency**, not a new application dependency. Re-running writes only the ignored count report and detached-label validation copies. The script and tests do not import production sampling functions to calculate expected counts. The production science pipeline and Earth ranking are unchanged.
