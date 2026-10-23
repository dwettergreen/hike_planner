"""Build trails/at-north/campsites_source.csv from source/at-north-facilities.json.
Rules (agreed Oct 2026): shelters + AMC huts included as Established; ATC campsites
within 0.15 mi of a shelter are merged into it; outhouse = privy within 0.1 mi;
water = True for shelters, and for campsites whose name mentions water;
mile = section miles from Maine Junction (same convention as long-trail)."""
import csv, json, re, sys
sys.path.insert(0, '.')
import prepare_trail as P
# Start: AT/Long Trail split at Maine Junction, Killington VT (found by comparing with
# trails/long-trail geometry; 104.33 AT mi north of the MA/VT line).
JUNCTION = (43.67501, -72.83835)
full = P.load_trail('source/at-north.geojson', chain='endpoints', start_lat=42.745)
fcum = P.build_cumulative(full)
jtd = P.snap_trail_dist(*JUNCTION, full, fcum)
coords = P.load_trail('source/at-north.geojson', chain='endpoints', start_lat=42.745, start_point=JUNCTION)
cum = P.build_cumulative(coords)
north = lambda lat, lon: P.snap_trail_dist(lat, lon, full, fcum) > jtd
F = json.load(open('source/at-north-facilities.json'))
ll = lambda x: [x['lon'], x['lat']]
near = lambda x, L, d: any(P.haversine(ll(x), ll(y)) < d for y in L)
WATER = re.compile(r'pond|lake|brook|spring|stream|river|falls', re.I)
rows = []
for kind, L in (('shelter', F['shelters']), ('campsite', F['campsites'])):
    for x in L:
        if kind == 'campsite' and near(x, F['shelters'], 0.15):
            continue
        if not north(x['lat'], x['lon']):   # shared with the Long Trail; out of scope
            continue
        if 'Day Use' in x['name']:      # no overnight use
            continue
        td = P.snap_trail_dist(x['lat'], x['lon'], coords, cum)
        hut = bool(re.search(r'\bHut\b', x['name'])) and 'Caretaker' not in x['name']
        desc = 'AMC full-service hut; reservation and fee required.' if hut else ''
        if kind == 'shelter' and near(x, F['campsites'], 0.15):
            desc = (desc + ' Tent sites adjacent.').strip()
        rows.append(dict(name=x['name'], lat=x['lat'], lon=x['lon'], mile=round(td, 3), elev=None,
            type='Established', water=str(kind == 'shelter' or bool(WATER.search(x['name']))).lower(),
            outhouse=str(near(x, F['privies'], 0.1)).lower(), source='atc', desc=desc, amenities='',
            _h=x['h_m'], _td=td))
# Resupply towns: coordinates from OpenStreetMap Nominatim (Oct 2026), town centroids.
TOWNS = [('Manchester Center VT',43.1769,-73.0569),('Killington VT',43.6743,-72.7784),
         ('Hanover NH',43.7024,-72.2892),('Glencliff NH',43.9835,-71.8936),
         ('North Woodstock NH',44.0313,-71.6868),('Gorham NH',44.3879,-71.1730),
         ('Andover ME',44.6357,-70.7512),('Rangeley ME',44.9653,-70.6430),
         ('Stratton ME',45.1409,-70.4423),('Caratunk ME',45.2340,-69.9916),
         ('Monson ME',45.2874,-69.5016),('Millinocket ME',45.6487,-68.6849)]
for name, lat, lon in TOWNS:
    if not north(lat, lon):
        continue
    td = P.snap_trail_dist(lat, lon, coords, cum)
    d = min(P.haversine([lon, lat], c) for c in coords[::20])
    rows.append(dict(name=name, lat=lat, lon=lon, mile=round(td, 3), elev=None, type='Resupply',
        water='true', outhouse='false', source='resupply', amenities='Resupply',
        desc=f'Town resupply, about {d:.1f} mi from trail.', offTrail='true',
        _h=None, _td=td))
rows.sort(key=lambda r: r['_td'])
# Elevation: USGS 3DEP point query (feet), cached by original ATC name.
ELEV = json.load(open('source/at-north-elev.json'))
for r in rows:
    if r['type'] != 'Resupply':
        r['elev'] = ELEV.get(r['name'], '')
# Merge co-located duplicates (e.g. 'Horns Pond Lean-to Shelter 1' / '... 2').
merged = []
for r in rows:
    if merged and r['type'] != 'Resupply' and merged[-1]['type'] != 'Resupply' and abs(r['_td'] - merged[-1]['_td']) < 0.05:
        merged[-1]['desc'] = (merged[-1]['desc'] + ' Two shelters.').strip()
        continue
    merged.append(r)
rows = merged
for r in rows:
    r['name'] = re.sub(r'\s+Shelter\s+\d+$', '', r['name']).replace('Lean-to Shelter', 'Lean-to').strip()
with open('trails/at-north/campsites_source.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['name','lat','lon','mile','elev','type','water','outhouse','source','desc','amenities','offTrail'], extrasaction='ignore')
    w.writeheader(); w.writerows(rows)
json.dump([{'name': r['name'], 'h_m': r['_h']} for r in rows], open('/tmp/at_heights.json', 'w'))
print(len(rows), 'rows')
