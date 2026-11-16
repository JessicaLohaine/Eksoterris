# Bounded regional scientific characterization

**Status:** Executed Earth-only observational context for four South American study windows and one East African water-boundary control. No confirmed lunar or Martian analog, geology, mineralogy, current ice status, or independent elevation comparison is established. The production rankings and seven-site baseline are unchanged.

## Method and exact inputs

The study centers and 220 km nominal physical footprints are read from the saved original and shifted regional discovery catalogs, not re-entered from rounded coordinates. The Tranquillitatis pair overlaps by about 0.400 intersection-over-union; the two Jezero windows overlap by about 0.105 and are analyzed separately. Tycho and Gale have no selected terrestrial characterization sites because their topographic references remain extrapolative and their nearest footprints changed after shifting the search lattice.

Three original **EC Joint Research Centre Global Surface Water occurrence v1.5** GeoTIFF tiles were downloaded from the [official 1984–2024 delivery listing](https://global-surface-water.appspot.com/download): `occurrence_70W_20S_v1_5_2024.tif`, `occurrence_70W_10S_v1_5_2024.tif`, and `occurrence_30E_10N_v1_5_2024.tif`. Their total source byte count is 104,070,865. Exact source URLs, retrieval timestamps, ETags, byte counts and SHA-256 hashes are recorded beside the files under `backend/data/regional-characterization-v1/` and repeated in the evidence JSON. The raw directory is excluded from Git. These three tiles intersect the selected windows; no global imagery was downloaded.

The GeoTIFFs report EPSG:4326, 40,000 by 40,000 pixels per ten-degree tile and 0.00025-degree geographic pixel spacing. The title suffix denotes the **north** edge in the inspected South American tiles, rather than their south edge. This was independently checked against GeoTIFF bounds; the code rejects a shifted or misnamed tile. Each nominal footprint is rasterized onto native pixel centers, and raw occurrence codes are counted in 512-row chunks without resampling. The [official data user guide](https://storage.googleapis.com/water-world/downloads_ancillary/DataUsersGuidev2024_v.5.pdf) defines code 0 as no water detected, codes 1–100 as percentage of historical water occurrence, and 255 as no data. The code records the complete positive-value histogram. The fractional pixel counts below are descriptive pixel fractions, **not** a modeled present-day water fraction or an analog score. A zero code does not prove that a pixel is currently dry; observation availability and the collection transition limit interpretation. No ice layer is inferred from this product.

Five actual [NASA POWER climatology API](https://power.larc.nasa.gov/docs/services/api/temporal/climatology/) point responses were obtained at the saved centers using `T2M`, `PRECTOTCORR` and `PS`. Their returned header states a **January 2001–December 2025** climatology, MERRA-2 source and API version v2.10.1. The API identifies units as degrees Celsius, mm/day and kPa. POWER meteorology has coarse source support (about 0.5 by 0.625 degrees): these are **model-based center-point climatologies**, not independently measured whole-window extrema or lunar/Martian environmental measurements. The exact returned JSON bytes and SHA-256 manifests are retained in the pre-existing ignored `backend/data/` cache and identified in `evidence.json`.

### Results from acquired Earth products

| Study footprint, center | JRC pixels in footprint | Any historical water detection | JRC no-data pixels | POWER annual T2M (°C) | POWER annual precipitation (mm/day) | POWER annual surface pressure (kPa) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Tranquillitatis original, 21.9726°S 67°W | 67,539,158 | 940,360 (1.392% of counted pixels) | 0 | 3.93 | 0.67 | 59.60 |
| Tranquillitatis shifted, 22.4766°S 66.5°W | 67,782,372 | 1,096,153 (1.617%) | 0 | 6.84 | 1.17 | 62.71 |
| Jezero original, 18.9840°S 65°W | 66,235,696 | 179,848 (0.272%) | 0 | 14.23 | 1.57 | 73.72 |
| Jezero shifted, 20.4710°S 64.5°W | 66,855,086 | 262,186 (0.392%) | 0 | 18.01 | 1.75 | 81.58 |
| East African water-boundary control, 0.9986°N 35°E | 62,643,602 | 246,107 (0.393%) | 0 | 17.04 | 5.06 | 79.32 |

The JRC counts include pixels with any positive occurrence; `evidence.json` also includes the exact histogram by integer occurrence percentage. Natural Earth 1:10m did not map a lake intersecting these windows, while JRC found historical water signatures within all five. These are different maps with different dates, definitions and resolutions. This result **challenges any claim that the whole footprint is permanently dry**. It neither pinpoints a present-day lake nor proves that the original ETOPO1 elevation samples are invalid. Local imagery, observation histories and ice coverage are still needed. No water observations were inserted into the topographic distance.

## NASADEM and surface imagery status

NASA CMR returned **catalog metadata only** for 102 NASADEM_HGT V001 granules in two bounded discovery queries covering the South American study windows and East African control. The source product is a one-arc-second, void-filled elevation merge; its HGT values are meters relative to EGM96, and its NUM and SWB companion layers document source class and water masking (see the [NASADEM user guide v1.3](https://lpdaac.usgs.gov/documents/2237/NASADEM_User_Guide_V13.pdf)). Intersecting granule identifiers for each footprint, CMR URLs and metadata checksums are in `evidence.json`. An unauthenticated download of one confirmed LP DAAC link redirected to Earthdata Login and returned **HTTP 401**. No NASADEM raster or NUM/SWB layer was acquired or processed. **ETOPO1 versus NASADEM descriptor consistency cannot be assessed.** A nominal one-arc-second grid would not itself establish greater measurement accuracy or equivalent support to planetary products.

The [USGS Landsat Collection 2 Level-2 Surface Reflectance STAC catalog](https://www.usgs.gov/landsat-missions/spatiotemporal-asset-catalog-stac) returned 50 items on a bounded **first page** for 2024 over the South American study area; a `next` link confirms that this is not a comprehensive search. Three intersecting scene examples per window, their scene-level cloud percentages and approximate geometric intersection fractions are saved. Scene-level cloud cover does not establish cloud-free pixels within a particular 220 km study footprint. No Landsat reflectance, QA mask, thermal band or image-derived geological classification was downloaded or analyzed. The [USGS Bolivia Altiplano geologic map](https://pubs.usgs.gov/publication/ofr95494) was identified, but the coverage of the exact study footprints and accessible GIS attributes have not been verified; no lithology has been attributed to any candidate.

The [NSIDC RGI v7](https://nsidc.org/data/nsidc-0770/versions/7) regional directory redirected to Earthdata Login in this environment. The published GLIMS OGC endpoint returned HTTP 404 when tested. Neither dataset was acquired, so a lack of mapped Natural Earth glaciated polygons is **not evidence of current ice-free terrain**. RGI v7 is designed as an approximately year-2000 glacier inventory, not current seasonal snow cover.

## Comparison with planetary references

The separate machine-readable `comparisons.json` retains the original and shifted **topographic screening** rank, reference descriptors, candidate descriptors and range diagnostics for each South American study window. Its `supported_similarity_claims_beyond_topography` and `supported_differences` lists are empty: the acquired JRC and POWER products characterize Earth only and cannot by themselves measure an Earth–Moon or Earth–Mars likeness. This explicit absence is an evidentiary result.

- **Mare Tranquillitatis:** The two overlapping Earth windows remain a useful *paired regional investigation*. Their original and shifted combined-catalog ranks are 2 and 1 respectively, under different Earth-only IQR calibrations. Historical water signals and different POWER center-point climatologies require hydrological and surface-material investigation before any lunar interpretation. Lunar vacuum, gravity and radiation are not reproduced by these measurements.
- **Jezero:** The two low-overlap Earth footprints each ranked first in their separate combined catalog. They have different historical water and climatological context. A first-place ranking of two different places does not validate either as a Martian delta, sedimentary setting or operational analog. Mars geology and hydrologic history were not measured here.
- **Tycho and Gale:** No terrestrial candidate is endorsed. Slope and RMS remain outside the sampled Earth ranges after shifting. The Earth-only evidence above cannot resolve the extrapolation.

**Next small scientific check:** first inspect site-specific Landsat QA and JRC temporal history around positive-water patches, then acquire a bounded, authenticated NASADEM HGT+NUM+SWB subset covering at least the shared Tranquillitatis footprint and compare the *same physical window* after explicitly matching effective support. Check a region-specific glacier inventory and map coverage before assigning geological units. Do not combine hydrology, temperature or geology into the existing terrain distance without a separate validated method.

## Reproduction

From PowerShell in the development-copy root, with the existing Python environment:

```powershell
backend/.venv/Scripts/python.exe backend/region_characterization.py
backend/.venv/Scripts/python.exe -m unittest discover -s backend -p test_region_characterization.py -v
Get-FileHash backend/data/regional-characterization-v1/*.tif -Algorithm SHA256
```

The runner verifies raw source checksums, GeoTIFF registration, valid occurrence codes, the five saved candidate IDs and CMR granule identifiers. `results/regional-characterization-v1/evidence.json` and `comparisons.json` are inspectable, English-only outputs. When run with the same cache, their data fields are deterministic; timestamps are source acquisition metadata, not recomputed scientific values. Nothing in this report changes or validates the existing nearest-neighbor method.
