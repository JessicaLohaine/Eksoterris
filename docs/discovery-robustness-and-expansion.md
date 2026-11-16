# Terrestrial discovery: robustness and bounded expansion

**Status:** Executed, exploratory topographic experiments. The seven-site production baseline, the first 49-center discovery output, and the production API remain unchanged. No location has been established as a planetary analog.

## Inputs and controlled design

The first experiment used the fixed NOAA [ETOPO1 Ice Surface](https://doi.org/10.7289/V5C8276M) 4–14°N, 2°W–8°E subset (SHA-256 `8e3f767b8e5246f59a8a27b68d0ce2e139bb5f5c4aea798df01ce37c905fd06f`). The eight configurations below reuse the same downloaded elevations and original LOLA/MOLA reference sources. Within each configuration, Earth-only IQRs are fitted anew. **Raw distances from different configurations must not be compared as if their scales were fixed.** The 220 km, 11 × 11, 20 km, 25-queries-per-cell baseline is independently repeated and checked against every original candidate status, descriptor, full ranking, and distance with an absolute numerical check of 1e-8. The two original JSON files are read, never written.

Equal-area rows are uniform in `sin(latitude)` and longitudes are uniformly spaced. The shifted lattice offsets both axes by half a row/column step. The coarse lattice uses four rows/columns with 2° longitude steps; the dense lattice uses thirteen rows/columns with 0.5° longitude steps. These choices test a bounded range of center placement and overlap, not an optimized or final grid. For the extent tests, 180 km uses 9 × 9 cells and 260 km uses 13 × 13 cells, both preserving 20 km cell spacing and the same 25-query subcell quadrature. Thus their window footprints change while the output cell spacing stays fixed; each reference is recomputed at the corresponding extent. More queries do not create source resolution.

| Configuration | Generated | Eligible | Excluded | Leading coordinate(s) for the four references |
| --- | ---: | ---: | ---: | --- |
| Original 220 km, 11 × 11, 1:50m mask | 49 | 26 | 23 | 7.9894°N, 6.0000°E for all four |
| Shifted origin, same spacing/window | 49 | 28 | 21 | 7.4912°N, 6.5000°E for all four |
| Coarse center grid, same window | 16 | 10 | 6 | 7.9894°N, 6.0000°E for all four |
| Dense center grid, same window | 169 | 82 | 87 | 7.4912°N, 6.0000°E for Tranquillitatis, Jezero and Gale; 7.4912°N, 5.5000°E for Tycho |
| 180 km window, 9 × 9 | 49 | 28 | 21 | 7.9894°N, 6.0000°E for all four |
| 260 km window, 13 × 13 | 49 | 24 | 25 | 7.9894°N, 6.0000°E for all four |
| Original grid, 1:10m mask | 49 | 26 | 23 | 7.9894°N, 6.0000°E for all four |
| Dense grid, 1:10m mask | 169 | 82 | 87 | Same coordinates as the dense 1:50m case |

Every one of these **eight** West Africa configurations remains outside the observed Earth ranges in **all three descriptors** for each of the four references. The broadly similar leading neighborhood is a relative result within this particular tile. The exact first center changes when the lattice moves or becomes denser. The leading descriptor's numerical contribution is usually slope for Tycho, Gale, and Tranquillitatis, and often elevation range for Jezero; the saved per-candidate contributions show the exceptions. Contribution to this numerical distance is not causal or scientific importance.

The original catalog has descriptor ranges of 104.59–444.39 m (P95–P5), 0.04–0.19° (median slope, rounded), and 20.96–107.63 m (detrended RMS). Shifting the grid changes these ranges to 74.35–483.79 m, approximately 0.03–0.23°, and 19.30–128.04 m. The dense grid ranges are 101.82–483.79 m, approximately 0.04–0.22°, and 20.96–107.63 m. The actual full-precision ranges, descriptor values, Earth IQRs, exclusions, rankings and individual squared-distance contributions are recorded in each configuration's JSON.

## Geographic overlap and spatial independence

Window footprints are reconstructed on the existing spherical local grid. For this bounded no-antimeridian tile, we calculate polygon intersection-over-union (IoU) area after a spherical Lambert cylindrical equal-area transformation. The polygons are densified approximations; IoU is a descriptive spatial statistic, not an independence test or validation threshold.

| Center grid | Eligible windows | Intersecting pairs | Pairs with IoU > 0.25 | Pairs with IoU > 0.50 | Windows retained by an illustrative IoU 0.25 thinning |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original | 26 | 84 of 325 possible | 34 | 0 | 13 in either spatial order |
| Dense | 82 | 1,128 of 3,321 possible | 333 | 128 | 19 in either spatial order |

All 26 original candidates and all 82 dense-grid candidates take part in at least one IoU > 0.25 pair. The thinning is an explicit **trial diagnostic**, never an eligibility rule: it retains a candidate only if its IoU with previously retained footprints is at most 0.25, starting once from southwest and once from northeast. The original first-ranked coordinate is retained in the northeast-first trial, but not in the southwest-first trial; the new first retained coordinate is then 6.9936°N, 6.0000°E for all four references, with recalibrated Earth IQRs. Dense-grid thinning also changes the first coordinates and depends on ordering. Neither 26 nor 82 is a count of independent environments. This one trial cutoff has no scientific privileged status; pairwise IoUs and additional trial levels 0.1/0.5 are included in the JSON.

## Map-scale and interpolation eligibility

The baseline [Natural Earth physical vectors](https://www.naturalearthdata.com/downloads/50m-physical-vectors/) are 1:50m land (archive version 4.1.0), lakes (5.0.0), and glaciated areas (4.1.0). The bounded alternative uses [1:10m land](https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-land/) (5.1.1), [lakes](https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-lakes/) (5.0.0), and [glaciated areas](https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-glaciated-areas/) (archive 4.1.0). Exact ZIP SHA-256 values and URLs are in the machine-readable configuration records. Both scales are checked for complete mapped land coverage of the physical footprint, intersections with mapped lakes/glaciated areas, finite elevation, tile coverage and all four source nodes at each bilinear query. A passing center is **mapped land under this screen**, not certified dry, current ice-free, or directly observed at every node.

No status changed among the original 49 centers or the 169 denser centers when replacing the 1:50m layers with 1:10m. This local agreement **does not** establish global map adequacy. Natural Earth is generalized cartography, the glaciated layer includes some recently deglaciated areas, small/informal waters can be missing, seasonal snow is unresolved, and a 1:10m map scale is not a 10 m positional accuracy claim. A source-node check prevents an obvious mapped water contribution to bilinear interpolation; it cannot detect water omitted by both masks.

## Predeclared regional expansion as a diagnostic

The initial tile samples a narrow landform distribution. Before inspecting any additional rankings, two bounded 10° × 10° tiles were fixed to test **different continents, latitude bands, regional relief, and inland-water eligibility**: a South American west-central elevation gradient (26–16°S, 73–63°W), and an East African inland elevation/water gradient (4°S–6°N, 30–40°E). These are selected regional strata, not a global or unbiased Earth sample. Each tile has a seven-by-seven `sin(latitude)`/longitude center lattice inset 2° from its data boundaries; none of its 49 centers is chosen from a named analog site. Each receives a separately acquired 601 × 601 ETOPO1 node subset, strict 1:10m land/lake/glaciated-area screen, and all four existing planetary analyses. The ETOPO1 source URLs, dimensions, units, SHA-256 and full exclusions are recorded, and future runs reject changed source bytes.

| Tile | ETOPO1 subset SHA-256 | Generated | Eligible | Excluded by cause |
| --- | --- | ---: | ---: | --- |
| South American gradient | `41ad976256e29290387d14807efc2729b7f105304f8333debd3a27ea163637ef` | 49 | 22 | 16 mixed land/ocean, 9 mapped lake, 2 mapped glaciated area |
| East African gradient | `66f67b42d611a2bf69a0dd38c7fb7ecf93b54096bb27b47e5d7c07311ae10172` | 49 | 16 | 33 mapped lake |

The 1:10m layers **changed 13 of 49 South American statuses** relative to 1:50m (2 newly mixed coastline footprints, 9 lake intersections, 2 glaciated-area intersections), and **6 of 49 East African statuses** (new lake intersections). The finer screen also changed the within-tile first-ranked coordinate for Tranquillitatis in South America and all four within-tile first coordinates in East Africa. These differences demonstrate mask-scale sensitivity and do not by themselves establish which boundary is ground truth.

For a joint **new experimental catalog only**, 26 West African windows screened at 1:10m, 22 South American windows and 16 East African windows are combined (64 total); the original seven-site production baseline remains entirely separate. Earth IQR is fitted once to these 64 windows. Its ranges broaden to 104.59–3,607.28 m, approximately 0.04–1.16°, and 20.96–690.40 m for elevation range, median slope and detrended RMS. The original 26-window Earth IQRs (151.68 m, 0.047°, 25.91 m) become approximately 1,427.74 m, 0.664°, and 331.91 m. Consequently, its distances are **not directly comparable** with the original experiment's distances.

| Planetary reference | First among 64 generated centers | Coordinates | Outside separate Earth descriptor ranges |
| --- | --- | --- | --- |
| Mare Tranquillitatis | South American gradient `r03-c05` | 20.9699°S, 66.0000°W | None |
| Tycho | South American gradient `r00-c06` | 24.0000°S, 65.0000°W | Slope and detrended RMS |
| Jezero | South American gradient `r05-c06` | 18.9840°S, 65.0000°W | None |
| Gale | South American gradient `r00-c06` | 24.0000°S, 65.0000°W | All three |

Being inside **individual** descriptor ranges for Tranquillitatis or Jezero does not establish a close **joint** match, an acceptable distance threshold, or a validated analog. The 64 windows are selected, overlapping, topographic samples. Tycho and Gale remain explicitly extrapolative. No environment, geology, operational suitability, current ice cover, source-effective-resolution equivalence or observational accuracy was established. The first experiment's exact-coordinate leader is not sufficiently stable or diverse to support a broader analog claim.

For **Tranquillitatis**, the West Africa leader moves with lattice origin and density, and its original largest numerical contribution is slope. Its combined-catalog reference lies inside the three separate descriptor ranges, but the South American within-tile first place changes with mask detail and IQR recalibration. For **Tycho**, the denser West Africa grid moves the first center from 6.0°E to 5.5°E at approximately 7.491°N; slope remains its leading numerical discrepancy and the expanded catalog still lacks the reference's slope and RMS range. For **Jezero**, the original leading discrepancy is elevation range, while center density and Earth IQR recalibration can change which descriptor contributes most; all three expanded ranges individually contain its reference. For **Gale**, slope is the dominant numerical discrepancy and all three expanded ranges are still exceeded. These statements concern the recorded finite catalogs only, not geological causes or predictive performance.

## Outputs, reproduction and next decision

Eight complete per-configuration JSON files and a summary are in `results/terrestrial-discovery-robustness-v1/`. The two expanded regional catalogs/rankings, their summary, and the jointly calibrated exploratory ranking are in `results/terrestrial-discovery-expansion-v1/`. Each configuration records generated/excluded centers, eligibility, coordinates, three descriptors, source/mask provenance, Earth IQR, all four full rankings, feature contributions and extrapolation diagnostics. The original `results/terrestrial-discovery/` files remain separate and unchanged. No frontend or production API behavior was changed.

In PowerShell from the development-copy root, with the existing backend environment:

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-discovery.txt
backend/.venv/Scripts/python.exe backend/discovery_robustness.py
backend/.venv/Scripts/python.exe backend/discovery_expansion.py
backend/.venv/Scripts/python.exe -m unittest discover -s backend -p test_discovery_*.py -v
Get-FileHash results/terrestrial-discovery/catalog.json,results/terrestrial-discovery/rankings.json -Algorithm SHA256
```

The first run requires access to the bounded NOAA and Natural Earth source URLs; cached exact bytes permit repeat runs. Next, freeze an independently chosen, geographically stratified set of additional **tiles** and compare shifted-center and overlap diagnostics in each. Independently check 1:10m shoreline/lake and ice classifications near potentially influential windows, then compare ETOPO1's effective terrain support with targeted higher-detail sources. Do not enlarge the production catalog or claim planetary analog validity until those checks are completed. A full global scan remains a separate decision.
