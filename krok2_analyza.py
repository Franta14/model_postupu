import xml.etree.ElementTree as ET
import gpxpy
import pandas as pd
from pyproj import Transformer
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union

# --- NASTAVENÍ SOUBORŮ ---
omap_file = 'Homolka_Vojirov_20240917.omap'
gpx_file = 'activity_22413815024.gpx' # <-- Vlož název originálu s časem!

# --- ⚙️ PARAMETRY MODELU ---
ZAHODIT_PRVNICH_MINUT = 0
ZAHODIT_POSLEDNICH_MINUT = 0
MAX_SKLON_PROCENTA = 12.0  # Tolerujeme mírné svahy
MAX_TEMPO_MINKM = 35.0     # Povolíme pomalé prodírání
SIRKA_CESTY_BUFFER = 6.0   # GPS odchylka v lese

REF_X = -718000
REF_Y = -1165000

print("1. Načítám geometrii mapy (Hustníky, Paseky, Cesty)...")
tree = ET.parse(omap_file)
root = tree.getroot()

symbol_map = {}
for elem in root.iter():
    if 'symbol' in elem.tag.lower():
        s_id = elem.attrib.get('id')
        s_code = elem.attrib.get('code')
        if s_id and s_code:
            symbol_map[s_id] = s_code

kategorie = {"Cesty": [], "Paseky": [], "Hustnik": [], "Podrost": []}

for obj in root.iter():
    if 'object' in obj.tag.lower():
        sym_id = obj.attrib.get('symbol')
        if not sym_id: continue
        isom = symbol_map.get(sym_id, "")
        
        pts = []
        for child in obj:
            if 'coords' in child.tag.lower() and child.text:
                pairs = child.text.strip().split(';')
                for p in pairs:
                    parts = p.strip().split()
                    if len(parts) >= 2:
                        try:
                            pts.append((float(parts[0])/1000, float(parts[1])/1000))
                        except ValueError:
                            pass
                break
        
        if not pts: continue

        if isom in ['506.0', '508.0'] and len(pts) >= 2:
            kategorie["Cesty"].append(LineString(pts).buffer(SIRKA_CESTY_BUFFER))
        elif len(pts) >= 3:
            try:
                poly = Polygon(pts)
                if not poly.is_valid: poly = poly.buffer(0)
                
                if isom in ['403.0', '404.0']: kategorie["Paseky"].append(poly)
                elif isom in ['406.0', '408.0', '410.0']: kategorie["Hustnik"].append(poly)
                elif isom in ['407.0', '409.0']: kategorie["Podrost"].append(poly)
            except: pass

print("Slučuji objekty do velkých oblastí...")
merged_geom = {k: unary_union(v) if v else Polygon() for k, v in kategorie.items()}

print("2. Načítám GPX a mapuji body rovnou na terén...")
transformer = Transformer.from_crs("epsg:4326", "epsg:5514", always_xy=True)

with open(gpx_file, 'r', encoding='utf-8') as f:
    gpx = gpxpy.parse(f)

all_points = []
for track in gpx.tracks:
    for segment in track.segments:
        for p in segment.points:
            if p.time and p.elevation is not None:
                all_points.append(p)

start_time = all_points[0].time
end_time = all_points[-1].time

data = []
for i in range(1, len(all_points)):
    p1 = all_points[i-1]
    p2 = all_points[i]
    
    minuty_od_startu = (p2.time - start_time).total_seconds() / 60
    minuty_do_cile = (end_time - p2.time).total_seconds() / 60
    
    if minuty_od_startu < ZAHODIT_PRVNICH_MINUT or minuty_do_cile < ZAHODIT_POSLEDNICH_MINUT:
        continue
        
    time_diff = (p2.time - p1.time).total_seconds()
    dist = p1.distance_2d(p2)
    
    if time_diff > 0 and dist > 0:
        elev_diff = p2.elevation - p1.elevation
        sklon_procenta = (elev_diff / dist) * 100
        
        speed_mps = dist / time_diff
        tempo_minkm = (1000 / speed_mps) / 60
        
        if 2.5 < tempo_minkm < MAX_TEMPO_MINKM and abs(sklon_procenta) <= MAX_SKLON_PROCENTA:
            grid_x, grid_y = transformer.transform(p2.longitude, p2.latitude)
            
            # Žádná rotace, pouze přímý překryv, který nám perfektně fungoval
            map_point = Point(grid_x - REF_X, grid_y - REF_Y)
            
            terrain = "Bily les"
            if merged_geom["Cesty"].contains(map_point): terrain = "Cesty"
            elif merged_geom["Hustnik"].contains(map_point): terrain = "Hustnik"
            elif merged_geom["Podrost"].contains(map_point): terrain = "Podrost"
            elif merged_geom["Paseky"].contains(map_point): terrain = "Paseky"
                
            data.append({"Terén": terrain, "Tempo_min_km": tempo_minkm})

print("\n=== 3. VÝSLEDKY: PRŮMĚRNÉ TEMPO ===")
df = pd.DataFrame(data)
if not df.empty:
    print("\nPočet GPS bodů zachycených v terénech:")
    print(df["Terén"].value_counts())
    print("-" * 40)
    
    summary = df.groupby("Terén")["Tempo_min_km"].median().round(2).sort_values()
    
    for ter, tempo in summary.items():
        minuty = int(tempo)
        vteriny = int((tempo - minuty) * 60)
        print(f"{ter.ljust(15)} : {minuty}:{vteriny:02d} min/km")
    
    print("\n=== KOEFICIENTY PRŮBĚŽNOSTI (A* Model) ===")
    if "Bily les" in summary:
        base = summary["Bily les"]
        for ter, tempo in summary.items():
            print(f"{ter.ljust(15)} : {(tempo / base):.2f}x")
    else:
        print("Model nezachytil Bílý les jako referenci.")
else:
    print("Nezbyla žádná data.")