# Long Trail Interactive Planner

An interactive trip planning tool for Vermont's Long Trail — from the Massachusetts border to the Canadian border, a distance of approximately 272 miles (438 km) along the spine of the Green Mountains.

The planner uses dynamic programming to generate an optimal multi-night itinerary from your target pace and start date, scoring candidate campsites on elevation. You can adjust any night by dragging markers on the map, edit the campsite dataset directly in the browser, and export your plan as CSV or JSON.

---

## Project Structure

```
lt_planner/
├── index.html          ← Planner + embedded campsite editor (single page)
├── campsites.json      ← 64 Long Trail overnight sites with GPS coordinates
├── long-trail.json     ← Long Trail polyline from OpenStreetMap (~19,741 GPS points)
├── trail.geojson       ← Trail geometry (alternate format)
├── plan.json           ← Saved plan; auto-restored on load if present
├── build_campsites.py  ← Data pipeline: merges sources, deduplicates, verifies
└── README.md
```

The tool is a static site — no server-side code, no database, no build step. It loads data via `fetch()`, which means it must be served over HTTP rather than opened directly from the filesystem. GitHub Pages handles this automatically; for local use run `python3 -m http.server 8000` in the project folder and open `http://localhost:8000`.

---

## Campsite Dataset

`campsites.json` contains **64 verified Long Trail overnight sites**, assembled from three free sources and validated against the trail polyline. It covers the full 272-mile route from Seth Warner Shelter (mile 5.1) to Journey's End Camp (mile 246.7).

### Site breakdown

| Type | Count | Description |
|------|-------|-------------|
| Lean-to | 43 | Three-sided shelter with roof, sleeps 6–16 |
| Camp / Lodge | 15 | Fully enclosed cabin with bunks, sleeps 8–24 |
| Tenting Area | 6 | Designated tent platforms, no structure |
| **Total** | **64** | |

All established GMC sites have a water source and privy. See the [GMC overnight sites page](https://www.greenmountainclub.org/the-long-trail/overnight-accommodations/) for current conditions.

### Rebuilding the dataset

```bash
python3 build_campsites.py
```

The script merges the three sources, deduplicates within a 200 m radius, computes trail distances by snapping each site to the nearest point on `long-trail.json`, sorts south-to-north, and runs verification checks. It exits with code 1 if any check fails.

**Verification checks performed:**
- Site count within expected range (55–95)
- All coordinates within Vermont bounding box
- No negative latitudes (catches the classic KML lon/lat swap)
- No duplicate site names
- Trail distances monotonically increasing south-to-north
- Five anchor sites within 0.015° of known reference coordinates (Taft Lodge, Stratton Pond Shelter, Cooper Lodge, Seth Warner Shelter, Jay Camp, Goddard Shelter, Montclair Glen Lodge)
- Warning if any site snaps more than 3 km from the trail (expected for off-trail spurs like Duck Brook Shelter at 4.2 mi)

---

## Campsite Selection Algorithm

The planner uses **dynamic programming (DP)** to find the globally optimal sequence of campsites for the entire trip in one pass, rather than making greedy day-by-day decisions.

### Step 1 — Set the target night count

Given your average pace (say 12 mi/day) and the total distance (272 mi):

```
T = round(272 / 12) = 23 nights
```

### Step 2 — Define the daily distance window

To allow flexibility around the average, it uses a tolerance that starts tight and widens if no valid path is found:

```
min_d = 272 / (23 × 1.25) = 9.5 mi
max_d = 272 / (23 × 0.75) = 15.8 mi
```

If no complete path exists within those bounds (campsites are too sparse in a section), it retries with progressively wider tolerances: ±25%, ±35%, ±45%, ±55%, ±65%, ±80%. The flex slider controls the display of the range but the DP always finds a valid plan.

### Step 3 — Score each campsite

Every candidate campsite is scored on **elevation**:

```
score = elev
```

Higher camps score higher, directing the planner toward ridgeline sites over valley camps all else being equal.

### Step 4 — Dynamic programming

The DP fills a table where `dp[i]` = the best cumulative score achievable by stopping at campsite `i`. For each campsite it looks back at all earlier campsites within the valid distance window:

```
for each campsite i:
  for each earlier campsite j where min_d ≤ dist[i] - dist[j] ≤ max_d:
    candidate = dp[j] + score(i)
    if candidate > dp[i]: dp[i] = candidate, prev[i] = j
```

It then traces back from the terminus to reconstruct the winning sequence — the globally optimal path rather than locally good day-by-day choices.

Inter-campsite distances are derived from trail GPS geometry (the `trailDist` field in `campsites.json`), computed by snapping each site to the nearest point on the OpenStreetMap-derived trail polyline in `long-trail.json`.

---

## Using the Planner

### Planning Controls

| Control | Effect |
|---------|--------|
| **Start date** | Date you leave the southern terminus; drives arrival date calculations |
| **Avg mi/day** | Target pace in 0.1 mi increments; determines night count and DP distance window |
| **Flex ± mi** | Displayed pace variation (informational; DP widens its window independently as needed) |

### Reading the Itinerary

The sidebar shows a card per night with campsite name, trail mile, elevation, miles that day, and arrival date. Badges flag notable conditions:

| Badge | Meaning |
|-------|---------|
| 🏠 Shelter | Site has a lean-to, lodge, or enclosed camp |
| ⛺ Tenting | Designated tenting area only (no structure) |
| 💧 Water | Water source at or near camp (all GMC sites) |
| 🚽 Privy | Outhouse present (all GMC sites) |

Click any card to fly the map to that camp and open a details popup.

### Map

The **basemap selector** (top-right corner) switches between OpenTopoMap (recommended), USGS Topo, and OpenStreetMap.

### Exporting

The **Export** tab offers:

- **⬇ Download CSV** — one row per night; columns: Trail Mile, Miles Today, Campsite, Elevation, Date, Notes. Opens in Excel or Google Sheets.
- **💾 Save plan.json** — JSON recording pace settings and all camp locations. Drop it in the project folder and commit to restore your plan on next load.

---

## Editing the Campsite Data

### Editor Tab

Click the **Editor** tab to enter edit mode. All campsites appear as colored dots on the map:

| Dot color | Source |
|-----------|--------|
| Teal | TrailFinder / GMC data |
| Orange | Andy Arthur KMZ data |
| Purple | Manually geocoded sites |
| Green | Custom sites you have added |

**Add a campsite** — click anywhere on or near the trail. The location snaps to the nearest point on the trail polyline, and a form opens pre-filled with that lat/lon and an estimated trail distance. Enter the name, elevation, type, and amenities and click **💾 Save**.

**Edit a campsite** — click a dot or a row in the list. Edit the form and save.

**Delete a campsite** — select it and click **🗑 Delete**.

### Saving Changes Permanently

Edits exist only in the current browser session. Before closing:

1. Click **⬇ Download campsites.json** in the Editor toolbar
2. Replace `campsites.json` in your local repo folder
3. Run `python3 build_campsites.py` to re-validate (optional but recommended)
4. Commit and push — the live site updates within a minute

---

## Campsite Data Reference

| Field | Type | Description |
|-------|------|-------------|
| name | string | Campsite name |
| lat | number | Latitude (decimal degrees, WGS84) |
| lon | number | Longitude (decimal degrees, negative = West) |
| trailDist | number | Distance from southern terminus along trail geometry (km) |
| type | string | `Lean-to`, `Lodge`, `Camp`, or `Tenting` |
| shelter | boolean | `true` if an enclosed or semi-enclosed structure exists |
| water | boolean | Water source nearby |
| outhouse | boolean | Privy present |
| desc | string | Notes (spur distance, capacity, fire rules, etc.) |
| source | string | `trailfinder`, `andyarthur`, or `manual` |

---

## Data Sources

All data sources are free and require no registration.

### 1. TrailFinder (primary — 54 sites)

**URL:** https://www.trailfinder.info/trails/trail/long-trail  
**Direct KML download:** https://www.trailfinder.info/docs/kml/TrailPoints1309.kml  
**License:** Data curated by the [Upper Valley Trails Alliance](https://www.uvtrails.org/) in partnership with the [Green Mountain Club](https://www.greenmountainclub.org/). No explicit license stated; used with attribution.

TrailFinder is the official trail information partner of the GMC. The KML file contains named Points of Interest for the Long Trail including all shelter types (Lean-to, Hut/Lodge, Cabin, Tent Site, Campground) with precise GPS coordinates, capacity notes, and spur distances. This is the authoritative free source.

**Important notes for maintainers:**
- The KML download URL contains a CDN cache-busting timestamp (`1773328249`) that may change when TrailFinder updates the file. If the live download link breaks, scrape the fresh URL from the TrailFinder page above.
- The KML stores coordinates in `longitude,latitude` order (KML standard). The build script handles this swap; be careful if parsing manually.
- Snapshot `trailfinder_cache.kml` and commit it alongside `build_campsites.py` so the pipeline can run offline.

### 2. Andy Arthur KMZ (cross-reference — 23 sites, all now deduplicated)

**URL:** https://andyarthur.org/kml-maps-long-trail-and-appalachian-trail-in-vermont.html  
**Vermont Campsites KMZ:** linked on the page above  
**License:** No explicit license; Andy Arthur.org blog, informal personal use / attribution.

A hand-curated KMZ covering Vermont backcountry campsites, including Long Trail shelters. All 23 sites from this source are fully covered by the TrailFinder dataset and appear as duplicates during the merge step. Retained as a source in `build_campsites.py` for cross-checking; it adds no new sites to the current dataset but provides coordinate confirmation.

### 3. Manual geocodes (gap-fill — 10 sites)

**Sources used for verification:** [CalTopo](https://caltopo.com), [Google Maps satellite](https://maps.google.com), [GMC shelter history](https://gmcburlington.org/long-trail-system-shelter-history/), hiking trip reports.

Sites manually geocoded to fill gaps not covered by the above sources:

| Site | Reason |
|------|--------|
| Sunrise Shelter | Built 2023; not yet in TrailFinder |
| Stratton View Shelter | Built 2023; not yet in TrailFinder |
| Butler Lodge | Off-trail spur; missing from KML |
| Boyce Shelter | Gap between Sunrise and Sucker Brook |
| Atlas Valley Shelter | Remote northern section |
| Journey's End Camp | Northernmost site; near Canadian border |
| North Shore Tenting Area | Stratton Pond caretaker site |
| Griffith Lake Tenting Area | Caretaker site on AT/LT coincide section |
| Little Rock Pond Tenting Area | Overflow tenting adjacent to shelter |
| Lula Tye Shelter | Listed in some sources; status uncertain — verify on-trail |

Manual coordinates should be re-verified against current GMC maps before each hiking season. The `source: "manual"` field makes it easy to audit these entries.

### 4. Trail geometry

**Source:** OpenStreetMap via [Waymarked Trails](https://hiking.waymarkedtrails.org/#route?id=391736)  
**License:** © OpenStreetMap contributors, [ODbL 1.0](https://www.openstreetmap.org/copyright)

`long-trail.json` is a GeoJSON FeatureCollection containing the Long Trail as a MultiLineString with ~19,741 GPS points (400.9 km / 249 mi). Retrieved 2026-03-14. The trail geometry is used to compute `trailDist` values by snapping each campsite to the nearest polyline point and measuring cumulative distance from the southern terminus.

Per the ODbL license: if you redistribute a dataset that incorporates OSM data, you must attribute OpenStreetMap and make the derived dataset available under ODbL or a compatible license.

---

## Known Limitations and Maintenance Notes

- **2023 shelters:** Sunrise Shelter and Stratton View Shelter were built in 2023. Their coordinates are manually geocoded from satellite imagery and should be confirmed in person or against the current GMC printed map before relying on them for planning.

- **Lula Tye Shelter:** Listed in older sources (pre-2020); current status is uncertain. May have been removed or replaced. The `desc` field notes this. Verify before including in a plan.

- **Off-trail spurs:** Several shelters sit 0.1–4.2 miles off the main LT on side trails (Duck Brook, Beaver Meadow, etc.). The `trailDist` value reflects the snap point on the main trail, not the actual walking distance to the shelter. The `desc` field notes spur distances.

- **Seasonal water:** The GMC notes that some springs dry up in drought conditions. The `water: true` flag reflects normal conditions. Check current trail reports at [greenmountainclub.org](https://www.greenmountainclub.org/hiking/trail-updates/) before your trip.

- **Bear boxes:** Several high-use sites have installed bear boxes (marked "BB" in older shelter lists). The dataset does not currently track bear box presence. Food storage requirements apply throughout Green Mountain National Forest per a 2019 regulation.

- **Caretaker sites:** As of the 2023 hiking season, the GMC no longer charges overnight fees at caretaker-staffed sites. The `desc` field for some sites still references the former $5/night fee; this reflects the original source note and does not mean a fee applies.

---

## Data Attribution Summary

> This project uses data from the following free sources:
>
> - Campsite locations: [TrailFinder](https://www.trailfinder.info/trails/trail/long-trail) (Upper Valley Trails Alliance / Green Mountain Club) and [Andy Arthur](https://andyarthur.org/kml-maps-long-trail-and-appalachian-trail-in-vermont.html)
> - Trail geometry: © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), ODbL 1.0, via [Waymarked Trails](https://hiking.waymarkedtrails.org/)
> - Trail information: [Green Mountain Club](https://www.greenmountainclub.org/)

---

## Original PCT Planner

This project is adapted from the [PCT Washington Interactive Planner](https://dwettergreen.github.io/pct_planner/) originally built for the Pacific Crest Trail Washington section. The dynamic programming algorithm and planner interface are carried over from that project.

---

*Built with Claude by David Wettergreen*
