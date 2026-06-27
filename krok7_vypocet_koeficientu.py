import xml.etree.ElementTree as ET
import gpxpy
import pandas as pd
import math
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union

# --- NASTAVENÍ SOUBORŮ ---
omap_file = 'Homolka_Vojirov_20240917.omap'
gpx_file = 'activity_22413815024.gpx' 

REF_LAT = 49.02982779
REF_LON = 14.9847593

# --- 🎯 TVOJE KALIBRAČNÍ ČÍSLA ---
OFFSET_X = -2079.01
OFFSET_Y = -2591.08
ROTACE   = 4.34
MERITKO  = 0.1000

# --- ⚙️ OCHRANNÉ FILTRY (Uvolněno pro novou trasu!) ---
ZAHODIT_PRVNICH_MINUT = 0   # Změněno z 10 na 0
ZAHODIT_POSLEDNICH_MINUT = 0 # Změněno z 5 na 0
MAX_SKLON_PROCENTA = 30.0    # Povoleno až 30 % stoupání
MAX_TEMPO_MINKM = 50.0       # Povoleno tempo až 50 min/km (stání u kontroly, těžké prodírání)
SIRKA_CESTY_BUFFER = 0.5 

GAP_UP_FACTOR = 0.033
GAP_DOWN_FACTOR = 0.018

print("1. Načítám geometrii mapy...")
tree = ET.parse(omap_file)
root = tree.getroot()

symbol_map = {elem.attrib.get('id'): elem.attrib.get('code') for elem in root.iter() if 'symbol' in elem.tag.lower()}
kategorie = {"Cesty": [], "Paseky": [], "Hustnik": [], "Podrost": []}

for obj in root.iter():
    if 'object' in obj.tag.lower():
        sym_id = obj.attrib.get('symbol')
        if not sym_id: continue
        isom = symbol_map.get(sym_id, "")
        
        pts = []
        for child in obj:
            if 'coords' in child.tag.lower() and child.text:
                for p in child.text.strip().split(';'):
                    parts = p.strip().split()
                    if len(parts) >= 2:
                        try:
                            pts.append((float(parts[0])/1000, -float(parts[1])/1000))
                        except ValueError: pass
                break
        if not pts: continue

        if isom.startswith('50') and len(pts) >= 2:
            kategorie["Cesty"].append(LineString(pts).buffer(SIRKA_CESTY_BUFFER))
        elif len(pts) >= 3:
            try:
                poly = Polygon(pts)
                if not poly.is_valid: poly = poly.buffer(0)
                if isom in ['403.0', '404.0']: kategorie["Paseky"].append(poly)
                elif isom in ['406.0', '408.0', '410.0']: kategorie["Hustnik"].append(poly)
                elif isom in ['407.0', '409.0']: kategorie["Podrost"].append(poly)
            except: pass

merged_geom = {k: unary_union(v) if v else Polygon() for k, v in kategorie.items()}

print("2. Načítám GPX a spouštím diagnostiku filtrů...")
with open(gpx_file, 'r', encoding='utf-8') as f:
    gpx = gpxpy.parse(f)

all_points = []
for track in gpx.tracks:
    for segment in track.segments:
        all_points.extend([p for p in segment.points if p.time and p.elevation is not None])

if not all_points:
    print("🚨 CHYBA: Záznam neobsahuje data s časem a výškou!")
    exit()

start_time = all_points[0].time
end_time = all_points[-1].time

raw_x, raw_y = [], []
for p in all_points:
    raw_x.append((p.longitude - REF_LON) * 111320 * math.cos(math.radians(REF_LAT)))
    raw_y.append((p.latitude - REF_LAT) * 111320)

center_x = sum(raw_x) / len(raw_x) if raw_x else 0
center_y = sum(raw_y) / len(raw_y) if raw_y else 0

data = []
angle_rad = math.radians(ROTACE)
cos_a = math.cos(angle_rad)
sin_a = math.sin(angle_rad)

# Počítadla pro rentgen
cnt_total = len(all_points) - 1
cnt_zahoz_cas = 0
cnt_zahoz_tempo = 0

for i in range(1, len(all_points)):
    p1 = all_points[i-1]
    p2 = all_points[i]
    
    m_od_startu = (p2.time - start_time).total_seconds() / 60
    m_do_cile = (end_time - p2.time).total_seconds() / 60
    
    if m_od_startu < ZAHODIT_PRVNICH_MINUT or m_do_cile < ZAHODIT_POSLEDNICH_MINUT: 
        cnt_zahoz_cas += 1
        continue
        
    time_diff = (p2.time - p1.time).total_seconds()
    dist = p1.distance_2d(p2)
    
    if time_diff > 0 and dist > 0:
        elev_diff = p2.elevation - p1.elevation
        sklon = (elev_diff / dist) * 100
        real_tempo = (1000 / (dist / time_diff)) / 60
        
        if 2.0 < real_tempo < MAX_TEMPO_MINKM and abs(sklon) <= MAX_SKLON_PROCENTA:
            # GAP Výpočet
            if sklon > 0:
                faktor = 1 + (sklon * GAP_UP_FACTOR)
            else:
                efektivni_sklon = max(sklon, -15.0) 
                faktor = 1 + (efektivni_sklon * GAP_DOWN_FACTOR)
            
            gap_tempo = real_tempo / faktor
            
            # Geometrický překryv
            tx, ty = (raw_x[i] - center_x) * MERITKO, (raw_y[i] - center_y) * MERITKO
            lx = tx * cos_a - ty * sin_a
            ly = tx * sin_a + ty * cos_a
            map_point = Point(lx + center_x + OFFSET_X, ly + center_y + OFFSET_Y)
            
            terrain = "Bily les"
            if merged_geom["Cesty"].contains(map_point): terrain = "Cesty"
            elif merged_geom["Hustnik"].contains(map_point): terrain = "Hustnik"
            elif merged_geom["Podrost"].contains(map_point): terrain = "Podrost"
            elif merged_geom["Paseky"].contains(map_point): terrain = "Paseky"
                
            data.append({"Terén": terrain, "Tempo_min_km": gap_tempo})
        else:
            cnt_zahoz_tempo += 1

print("\n=== 📊 DIAGNOSTIKA FILTRŮ ===")
print(f"Celkem úseků v GPX:         {cnt_total}")
print(f"Zahozeno kvůli času:        {cnt_zahoz_cas}")
print(f"Zahozeno (rychlost/sklon):  {cnt_zahoz_tempo}")
print(f"Zpracováno do výsledku:     {len(data)}")

print("\n=== 3. VÝSLEDKY OČIŠTĚNÉ O KOPCE (GAP) ===")
df = pd.DataFrame(data)
if not df.empty:
    print(df["Terén"].value_counts())
    print("-" * 40)
    
    summary = df.groupby("Terén")["Tempo_min_km"].median().round(2).sort_values()
    for ter, tempo in summary.items():
        minuty = int(tempo)
        vteriny = int((tempo - minuty) * 60)
        print(f"{ter.ljust(15)} : {minuty}:{vteriny:02d} min/km")
    
    print("\n=== KOEFICIENTY PRŮBĚŽNOSTI ===")
    if "Bily les" in summary:
        base = summary["Bily les"]
        for ter, tempo in summary.items():
            print(f"{ter.ljust(15)} : {(tempo / base):.2f}x")
    else:
        print("Nedostatek dat pro Bílý les.")
else:
    print("Stále žádná data! Filtrům něco hodně vadí.")