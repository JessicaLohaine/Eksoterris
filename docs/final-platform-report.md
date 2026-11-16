# Eksoterris: platform integration and scientific scope

## Research objective

Eksoterris investigates whether terrain in bounded terrestrial regions is *relatively close* to selected lunar or Martian regional elevation profiles. It is an exploratory topographic discovery and evidence-review platform, not a detector of validated planetary analogs. A near neighbor is only the nearest member of the specific catalog searched. The selected Earth windows could motivate hydrological, geological, material or operational field studies; those uses require independent validation.

## Implemented system

- The Vite frontend keeps the CesiumJS Earth globe, NASA GIBS imagery and Three.js Moon and Mars models. Its scientific panel offers the separate seven-site baseline, three saved discovery populations, and five regional evidence windows. Cesium plots baseline sites and generated centers with distinct styling; selected analyzed footprints use the saved GeoJSON geometry, which is an analysis boundary rather than a mapped geologic unit.
- The local FastAPI backend reads the saved experimental JSON without recalculating or merging differently calibrated rankings. `/api/discovery/experiments` identifies the populations and source hashes; `/api/discovery/experiments/{experiment_id}/references/{reference_id}` returns the corresponding saved reference, complete ranking, feature contribution and extrapolation diagnostics; `/api/discovery/characterization` returns the saved Earth evidence and reference comparisons. The seven-site analysis remains on `/api/analyses`, `/api/jobs` and `/api/runs`.
- `/api/reports/{report_id}` serves only allowlisted English research reports. The UI links each experiment and the regional characterization to its methodology. Missing output files generate an explicit error instead of fabricated content.
- Optional Gemini endpoints operate on backend-only credentials. The seven-site path selects validated calculation evidence IDs; the regional path selects and orders only saved facts about the selected Earth study window. The server validates all IDs and writes factual sentences. Gemini does not compute the ranking, create coordinates or supply missing measurements. A missing key leaves all non-AI results available.

## Data and provenance

| Purpose | Actual source and processing | Limits |
| --- | --- | --- |
| Lunar reference | NASA LOLA LDEM_4 elevation | Different acquisition and resolution from Earth; observation counts are not accuracy estimates. |
| Martian reference | NASA MOLA MEGT90N000CB elevation | Some source cells may be interpolated or filled; observation support is distinct from accuracy. |
| Terrestrial terrain | NOAA ETOPO1 Ice Surface elevation via bounded ERDDAP subsets | Composite source detail varies geographically; one-arc-minute grid spacing is not uniformly effective resolution. |
| Geographic screening | Natural Earth land, lakes and mapped glaciated-area polygons, at documented scales per experiment | Cartographic screening does not prove current absence of water, snow or ice. |
| Regional historical water | European Commission JRC Global Surface Water v1.5 occurrence, 1984–2024; raw native pixels counted in selected footprints | Positive occurrence means historical detection, not current water coverage. |
| Earth climate context | NASA POWER annual 2001–2025 modeled point climatology (MERRA-2) | Center-point modeled air temperature, precipitation and pressure; not measured local surface conditions or planetary values. |
| NASADEM_HGT V001 | NASA CMR metadata and protected granule URLs only | LP DAAC authentication returned HTTP 401; HGT, NUM and SWB were not downloaded or compared with ETOPO1. |

Every saved experiment has its own provenance and SHA-256 result checksum. Raw source hashes, URLs, versions, acquisition metadata and processing details appear in the corresponding JSON and reports. See [independent window validation](independent-window-validation.md), [discovery robustness and expansion](discovery-robustness-and-expansion.md), and [regional scientific characterization](regional-scientific-characterization.md).

## Candidate generation and terrain comparison

The production baseline evaluates **seven predefined** Earth windows. The first geographically generated West Africa lattice had **49 centers, 26 eligible and 23 excluded**. The separate three-region population has **64 eligible windows**: West Africa 26, South America 22 and East Africa 16. A half-step shift in the two new regional lattices produces a **separate 69-window population**: West Africa 26, South America 27 and East Africa 16. The latter is a sensitivity experiment, not an enlargement of the original population. The 1:50m and 1:10m mask details and exclusions are in the source reports. These are bounded regional searches, not a global terrestrial search.

Each approximately 220 km window is sampled into an 11 × 11 elevation grid. Twenty-five bilinear queries contribute to each output cell. Three derived descriptors are P95 minus P5 elevation range (m), median slope (degrees), and RMS relief after plane removal (m). For descriptor `j`, candidate `x` and reference `q`, the saved distance is `sqrt(mean_j(((x_j - q_j) / Earth_IQR_j)^2))`. The Earth-only IQR is fitted separately within **each** candidate population. The score is nonnegative and unbounded. Its squared contributions describe only this formula; none is a causal explanation or scientific feature importance. Distances across experiments cannot be compared numerically. Separate min/max checks show when a planetary descriptor exceeds the observed terrestrial range, but being inside all three marginal ranges is not proof of joint similarity.

## Observed results and uncertainty

| Reference | Original 64-window nearest center | Shifted 69-window nearest center | Interpretation |
| --- | --- | --- | --- |
| Mare Tranquillitatis | 20.9699°S, 66°W | 22.4766°S, 66.5°W | The exact winner moves. Investigate the separate overlapping regional pair at 21.9726°S, 67°W and 22.4766°S, 66.5°W. |
| Tycho | 24°S, 65°W | 17.5101°S, 65.5°W | Slope and RMS exceed both catalog ranges. No terrestrial analog is endorsed. |
| Jezero | 18.9840°S, 65°W | 20.4710°S, 64.5°W | The windows have limited overlap; investigate both independently. Neither is a confirmed delta or Martian analog. |
| Gale | 24°S, 65°W | 17.5101°S, 65.5°W | Slope and RMS exceed the shifted catalog ranges; the original catalog also excludes relief. No analog is endorsed. |

The original West Africa search ranked the same eligible point (7.9894°N, 6°E) first for all four references, with all three planetary descriptors outside that regional population's ranges. The later regional diversity changes the search space, not the scientific validation status. The screen must not imply that Tycho and Gale have acceptable matches just because it can draw a top-ranked point.

The five investigated Earth footprints have actual JRC positive-pixel counts and NASA POWER annual center-point values in `results/regional-characterization-v1/evidence.json`. The South American Tranquillitatis pair overlaps and is treated as one regional investigation. Two Jezero sites are separate. An East African window is a water-screening control, not a selected planetary counterpart. The structured comparison deliberately records **no supported cross-body similarities beyond topography**. Historical surface-water signals were detected in all five windows; that challenges any unconditional claim of permanent dryness, without establishing present-day water at a particular location. No geology, mineralogy, current ice, interpreted Landsat pixels or NASADEM elevation comparison has been verified.

## Reproduce and demonstrate

From PowerShell in the **development-copy root**:

```powershell
./setup.ps1
./start-backend.ps1
```

In a second PowerShell window in the same directory:

```powershell
npm.cmd run dev
```

Open the URL printed by Vite, usually `http://127.0.0.1:5173/` (or the next free port). No Gemini key is necessary. A saved baseline computation loads if present; click **Compare Earth windows** to reproduce it from cached scientific source files. In **Discover and investigate**, switch between the 49-center, 64-window and 69-window populations, and select each planetary reference. Click a generated window to fly the globe. Click a selected investigation region to view its saved footprint, ETOPO1 descriptors, historical JRC counts, POWER model values, source links and unresolved evidence. Use the experiment report links for the full methods. Select Tycho or Gale to show extrapolation and the absence of an endorsed investigation region.

Tests and integration checks:

```powershell
backend/.venv/Scripts/python.exe -m unittest discover -s backend -p 'test_*.py' -v
backend/.venv/Scripts/python.exe backend/verify_demo.py
npm.cmd run build
git diff --check
```

`verify_demo.py` requires the backend running and can contact NASA CMR. Live Gemini requires a separately configured backend `GEMINI_API_KEY`; see the [README](../README.md). A mocked response contract test is **not** a live Gemini verification. Existing saved outputs remain unchanged. Do not copy this working tree over the original project without separate authorization.

## Limits and next scientific work

The geographically bounded catalogs are sparse, overlapping and sensitive to grid origin and window extent. Mapped eligibility does not replace site-level hydrology or ice validation. Different planetary and Earth raster resolutions and reference surfaces limit interpretation. Numerical reproducibility is strong, but does not establish geology, environmental equivalence, astronaut-training value or rover safety. The next bounded step is to inspect JRC temporal histories and site-specific Landsat QA, acquire an authenticated NASADEM HGT+NUM+SWB subset, and validate comparable spatial support before making an independent terrain comparison. Geological and mineralogical claims require their own measured evidence and methodology.
