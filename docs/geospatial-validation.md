# Geospatial registration and raster integrity audit

Status: validation of the present seven Earth windows and four planetary references. This audit does not certify planetary analogs. The original ranking remains the reproducible baseline. Source product descriptions below are distinguished from measurements made on cached source bytes.

## Evidence and product metadata

| Product used | Official documentation and local evidence | Grid and registration | Elevation and quality caveats |
| --- | --- | --- | --- |
| NASA LRO LOLA `LDEM_4`, PDS3 `LRO-L-LOLA-4-GDR-V1.0`, product version 3.0 | [Official LOLA IMG and label](https://imbrium.mit.edu/DATA/LOLA_GDR/CYLINDRICAL/IMG/), [LOLA product documentation](https://imbrium.mit.edu/DOCUMENT/rdrsis.htm); cached label and IMG SHA-256 `972d66d7f330abca62abc21aae270661516c00dd1a881ec102b94df9563656b5` | 720 rows north to south by 1440 columns eastward, 4 pixels/degree, 0–360° east longitude, ±90° latitude extent. Simple cylindrical, body-fixed Mean Earth/polar axis DE421. Pixel-registered nominal centers 89.875°N/0.125°E to 89.875°S/359.875°E. Equatorial grid spacing 7.581 km; east-west spacing decreases with latitude. | Signed 16-bit little-endian DN multiplied by 0.5 m. Height relative to the 1,737.4 km reference sphere, **not** planetopotential topography. No per-cell observation-count or uncertainty layer is processed. Label warns of possible artifacts at 45° latitude strip boundaries and of interpolation used at higher resolutions for incomplete coverage. No special NoData value is declared in this label; the decoder rejects any `-32768` values as a conservative sentinel check, and the cached IMG contains none. |
| NASA MGS MOLA `MEGT90N000CB.IMG`, PDS3 `MGS-M-MOLA-5-MEGDR-L3-V1.0`, product version 2.0 | [PDS MEGDR archive](https://pds-geosciences.wustl.edu/missions/mgs/megdr.html), [MOLA EGDR SIS](https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/document/egdrsis.pdf), [PDS advice on GDAL offsets](https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/extras/mola_envi.htm); cached IMG SHA-256 `25f16fb7aaf857898dcf98bc4f841341a24f8b9f7e98453ca083bc45d897ca2c` | 720 by 1440, 4 pixels/degree, north-up in source; 0–360° east longitude, planetocentric latitude, IAU2000 body-fixed system. Simple cylindrical with 3,396 km map radius. [PDS4 XML map metadata](https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg004/megt90n000cb.xml) places the **upper-left corner** at 0°E/90°N and gives 14.817845349 km/pixel at the equator. The interpreted first center is 0.125°E/89.875°N. | Signed 16-bit big-endian meters, elevation relative to the GMM3 areoid, not directly comparable as absolute height to LOLA or Earth. The elevation label says cells with no shots can have interpolated values. The companion [MEGC count label](https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg004/megc90n000cb.lbl) provides counts of observations contributing to each bin. The elevation IMG has no declared per-pixel NoData sentinel; cached values contain no `-32768`. |
| NOAA NCEI ETOPO1 Ice Surface, ERDDAP dataset `etopo180` | [NOAA ETOPO1 report](https://www.ncei.noaa.gov/sites/default/files/2020-04/ETOPO1.pdf), [NCEI product metadata](https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ngdc.mgg.dem%3A316/html), [NOAA ERDDAP dataset information](https://oceanwatch.aoml.noaa.gov/erddap/info/etopo180/index.htmlTable); seven cached CSV subsets | WGS 84 geographic, -180–180° longitude, ±90° latitude, 1 arc-minute **grid/node registration**. The original global grid is 10801 by 21601 nodes; each cached regional subset is 241 rows by 261–305 columns with 1/60° ascending lat/lon axes. North-south node spacing is about 1.853 km; east-west spacing varies with latitude. | Elevation in meters relative to generic sea level, a composite from sources of heterogeneous effective resolution and quality. The NOAA report distinguishes this authoritative grid-registered version from a separately resampled cell-registered version. Each of the seven cached subsets and 121-cell output grids is finite, but there is no per-cell source identity or uncertainty layer in the local CSV. |

The producer's PDS3 MOLA projection offsets (`360.5`, `720.5`) differ from LOLA's (`359.5`, `719.5`). These numbers cannot be interpreted in isolation as a one-pixel shift. PDS documents GDAL center/corner ambiguity and a half-pixel GDAL configuration adjustment. The PDS4 corner coordinates, full 360°/180° extent and pixel count independently support the current MOLA 0.125° center interpretation. A second GIS decoder comparison remains desirable before asserting subpixel registration accuracy.

The cached IMG byte lengths are 2,073,600 each, matching 720 × 1440 × 2; observed LOLA decoded range is -8878.5 to 10504 m and MOLA range -8068 to 21134 m. These checks support data decoding, but they do not establish observation accuracy.

## Coordinate controls and actual source bytes

The controls use feature coordinates from the [USGS planetary gazetteer (Tycho)](https://planetarynames.wr.usgs.gov/Feature/6163), [USGS planetary gazetteer (Gale)](https://planetarynames.wr.usgs.gov/Feature/2071) and [US National Park Service (Badwater Basin)](https://www.nps.gov/planyourvisit/event-details.htm?id=59F834E6-C4AE-5BAF-60BB19B3BC28F3F3). These are *geographic position controls*, not ground-truth elevations or confirmation that the selected 220 km analysis centers coincide with feature centers. The selected source row is zero-based, north-up; the Python raster reverses planetary rows to ascending latitude. Great-circle separations below use the same stated spherical body radii solely to describe pixel-center distances; the tolerance is half of the nominal angular grid step per coordinate, not an empirical accuracy claim.

| Control | Independent coordinates | Source row, column | Selected cell center | Center difference | Source value independently read at byte offset | Position test |
| --- | --- | --- | --- | --- | --- | --- |
| Badwater Basin, Earth | 36.229805°N, -116.767413°E | 119, 151 in the Death Valley CSV subset | 36.233333°N, -116.766667°E | 0.398 km | -87 m in the CSV | Each component below 0.5 arc-minute. NPS reports approximately -86 m at the broader site; 1 m agreement does not validate regional accuracy. |
| Tycho, Moon | -43.30°, -11.22°E (348.78°E) | 533, 1395 | -43.375°, 348.875°E | 3.092 km | -2999 m from little-endian DN × 0.5 | Each component below 0.125°. |
| Gale, Mars | -5.44°, 137.70°E | 381, 550 | -5.375°, 137.625°E | 5.868 km | -2589 m from big-endian DN | Each component below 0.125°. |

The independent byte-offset tests use `2 * (row * 1440 + column)`, the label-specified endian order, and separate arithmetic for the coordinate centers; they compare those readings to `Raster.sample()` at the center. At the longitude seam, the synthetic periodic grid returns the same interpolation at 0° and 360°; the source planet grids span 0.125–359.875° and wrap between their final and first columns. At the north/south pole, there is no pixel **center** at ±90°; requesting beyond the center latitude range is rejected. ETOPO1 subset grids do not wrap. None of the current Earth windows crosses ±180°; a future window there would need split/wrapped NOAA acquisition rather than an assumption of coverage.

## Regional sampling and spatial scale

The source IMG is reversed to south-to-north indexing before bilinear interpolation. NOAA CSV rows are parsed by their explicit coordinate values. `Raster.sample()` interpolates in latitude/longitude between four centers and rejects positions outside a nonperiodic subset or planetary latitude-center coverage; it does not interpolate across declared NoData. The present cached input grids and all 11 × 11 analysis grids are finite. A future missing value causes failure, rather than silently creating a valid cell.

The inverse spherical local-coordinate mapping places 11 output centers at -100 to +100 km east/north of each selected center, 20 km apart. Each output cell averages 25 bilinear lookups with offsets -8, -4, 0, +4 and +8 km in each axis. The nominal cell footprint is 20 km wide and the nominal 11-cell window is **220 km** wide. Actual sampled positions extend at most ±108 km on each local axis, spanning 216 km; the outer 2 km on each edge of the nominal footprint is not sampled. The 25 equally weighted positions approximate, rather than exactly integrate, surface area. Geographic longitude spacing varies with latitude; the spherical inverse transform accounts for this at the nominal local distance, but Earth's WGS 84 geodetic coordinates are approximated by a sphere of radius 6,371,008.8 m. This approximation and original source registration differ across bodies and have not been assigned uncertainty bounds.

At the equator, nominal source spacing is approximately 7.58 km for LOLA, 14.82 km for MOLA, and 1.85 km north-south for ETOPO1. The 4 km subcell sampling is therefore **oversampling interpolated surfaces** for both planetary grids. Twenty-kilometer output centers and averaging suppress fine features; MOLA can only supply roughly 1.35 source rows per output-center spacing at the equator. Counts of output samples do not increase measurement resolution. Native sample spacing, effective terrain resolution, registration uncertainty and measurement precision are different concepts. The current baseline is suitable only as an exploratory comparison of broad relief under these caveats. A coarser common effective scale would need a sensitivity experiment with independently established source support and mission-specific terrain scale, not an arbitrary resampling choice.

## Tycho and the 45°S LOLA strip boundary

The LOLA `LDEM_4` label explicitly warns of *possible* edge artifacts in the 45° latitude production bands. In the current Tycho window, actual sample latitudes extend from -46.872° to -39.652°. Of 3025 subcell lookups, 795 fall south of 45°S; 33 output cells include at least one southern lookup and six output cells have lookups on both sides. The 45°S boundary lies between source rows centered at -45.125° and -44.875°.

Using the original IMG and longitudes within 5° of the Tycho reference, the median absolute adjacent-row difference across this pair is 216.5 m (90th percentile across columns 480.55 m). Within the inspected -47° to -39° latitude neighborhood, medians for adjacent row pairs have 25th/50th/75th/90th/95th percentiles 204.5/272.25/396.625/602/640.125 m; the boundary pair is at approximately the 35th percentile of these descriptive medians. This test did **not** detect an exceptional boundary step. It cannot rule out local strip artifacts, anisotropy, alignment changes or errors hidden in real crater topography. No per-cell LOLA quality raster or independent lunar elevation comparison was used. **Conclusion: inconclusive artifact status; preserve the measured elevations and expose the warning.**

## MOLA observation coverage

The official paired `MEGC90N000CB.IMG` (SHA-256 `7e920ec43497b4beddf974650471600c7afd4916e2a8dd3500d6b14714365661`) and detached label (SHA-256 `487004de9598296dc910b814ee8a256e7755abed7ade9f1180743208eccb8476`) were downloaded. Their dimensions, coordinate bounds, projection, reference offsets and pixel type match the cached topographic MEGT label. The count IMG is big-endian signed 16-bit with observed nonnegative counts. It is a **count per original source bin**, never bilinearly interpolated as an elevation-like continuous field.

For each of Jezero and Gale, enumeration of the distinct source bins with nonzero bilinear weight across all 3025 sample positions touches 289 bins. All 289 have at least one recorded shot. Jezero source-bin counts span 247–1100; Gale spans 107–1205. Thus excluding zero-shot source bins changes no elevation sample, descriptor or ranking for these two references; the API records this no-effect comparison. The count layer does not validate the precision of elevations, the 25-sample average or the terrestrial data. A count-positive bin may still be uncertain. Without the optional cached count files, the analysis continues and reports coverage as unavailable; it does not change the ranking.

## ETOPO1 and ranking impact

Each of the seven Earth CSV subsets spans 4° latitude with valid 1 arc-minute nodes and ample margins around its current ±108 km sampling footprint. All output cells are finite. Node registration was checked by direct inspection of the original CSV at an independently located point, Badwater Basin. This does not supply source-by-source quality flags. ETOPO1 is a global composite; the local land source and effective terrain resolution can vary, and values produced by interpolation or blending are not separately labeled in these subsets. Use of 1 arc-minute nodes does not establish uniform 1 arc-minute terrain detail.

The audit found no demonstrated row reversal, longitude sign error, cell-center shift, or NoData interpolation error requiring a change to the current extraction. Therefore the original four nearest-neighbor rankings and distances are unchanged. The MOLA source-bin coverage diagnostic is separate from elevation features and the KNN distance. The small catalog, descriptor correlation, LOLA seam uncertainty, unknown ETOPO1 local source quality and cross-product effective-resolution differences still prevent validated planetary-analog conclusions.

## Reproduce

In PowerShell, from the **development copy** only:

```powershell
Set-Location 'C:\Users\jessi\Documents\Codex\2026-11-14\new-chat-2\Eksoterris'
backend/.venv/Scripts/python.exe -m unittest discover -s backend -p 'test_*.py' -v
backend/.venv/Scripts/python.exe -m uvicorn app:app --app-dir backend --host 127.0.0.1 --port 8000
```

In another PowerShell terminal, from the same development copy:

```powershell
backend/.venv/Scripts/python.exe backend/verify_demo.py
npm.cmd run build
```

The offline analytical fixtures exercise coordinate centers, longitude wrapping, spherical distance, NoData rejection, bilinear interpolation, window geometry and source-count support. The two raw-byte and Earth CSV controls require the previously acquired, checksum-verified cache. To acquire the optional MOLA count pair independently, run these commands from the project directory in a backend Python environment with network access:

```powershell
Set-Location 'C:\Users\jessi\Documents\Codex\2026-11-14\new-chat-2\Eksoterris\backend'
./.venv/Scripts/python.exe -c "from sources import fetch, MARS_BASE; fetch(MARS_BASE+'megc90n000cb.lbl','lbl'); fetch(MARS_BASE+'megc90n000cb.img','img')"
```

The cache is ignored by Git. Verify file manifests and product label before treating any different version as equivalent. No secret is required for these three elevation products or the MOLA count pair.
