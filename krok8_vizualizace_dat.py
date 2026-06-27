import xml.etree.ElementTree as ET
import gpxpy
import pandas as pd
import math
import matplotlib.pyplot as plt
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

# --- ⚙️ OCHRANNÉ FILTRY ---
ZAHODIT_PRVNICH_MINUT = 0
ZAHODIT_POSLEDNICH_MINUT = 0
MAX_SKLON_PROCENTA = 30.0  
MAX_TEMPO_MINKM = 50.0       
SIRKA_CESTY_BUFFER = 0.5   # Náš nový zpřísněný filtr na cesty

GAP_UP_FACTOR = 0.033
GAP_DOWN_FACTOR = 0.018

print("1. Zpracovávám geometrii a modeluji GAP...")
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
                        try: pts.append((float(parts[0])/1000, -float(parts[1])/1000))
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

with open(gpx_file, 'r', encoding='utf-8') as f:
    gpx = gpxpy.parse(f)

all_points = [p for t in gpx.tracks for s in t.segments for p in s.points if p.time and p.elevation is not None]
start_time, end_time = all_points[0].time, all_points[-1].time

raw_x, raw_y = [], []
for p in all_points:
    raw_x.append((p.longitude - REF_LON) * 111320 * math.cos(math.radians(REF_LAT)))
    raw_y.append((p.latitude - REF_LAT) * 111320)

center_x = sum(raw_x) / len(raw_x) if raw_x else 0
center_y = sum(raw_y) / len(raw_y) if raw_y else 0

data = []
cos_a, sin_a = math.cos(math.radians(ROTACE)), math.sin(math.radians(ROTACE))

for i in range(1, len(all_points)):
    p1, p2 = all_points[i-1], all_points[i]
    time_diff = (p2.time - p1.time).total_seconds()
    dist = p1.distance_2d(p2)
    
    if time_diff > 0 and dist > 0:
        sklon = ((p2.elevation - p1.elevation) / dist) * 100
        real_tempo = (1000 / (dist / time_diff)) / 60
        
        if 2.0 < real_tempo < MAX_TEMPO_MINKM and abs(sklon) <= MAX_SKLON_PROCENTA:
            faktor = 1 + (sklon * GAP_UP_FACTOR) if sklon > 0 else 1 + (max(sklon, -15.0) * GAP_DOWN_FACTOR)
            gap_tempo = real_tempo / faktor
            
            tx, ty = (raw_x[i] - center_x) * MERITKO, (raw_y[i] - center_y) * MERITKO
            map_point = Point((tx * cos_a - ty * sin_a) + center_x + OFFSET_X, (tx * sin_a + ty * cos_a) + center_y + OFFSET_Y)
            
            terrain = "Bily les"
            if merged_geom["Cesty"].contains(map_point): terrain = "Cesty"
            elif merged_geom["Hustnik"].contains(map_point): terrain = "Hustnik"
            elif merged_geom["Podrost"].contains(map_point): terrain = "Podrost"
            elif merged_geom["Paseky"].contains(map_point): terrain = "Paseky"
                
            data.append({"Terén": terrain, "Real_Tempo": real_tempo, "GAP_Tempo": gap_tempo, "Sklon": sklon})

df = pd.DataFrame(data)

print("2. Generuji analytické grafy...")

# --- VYKRESLENÍ GRAFŮ ---
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
fig.canvas.manager.set_window_title('Diagnostika Výpočtu Průběžnosti')

# Barvy pro terény
colors = {'Bily les': 'dodgerblue', 'Hustnik': 'darkgreen', 'Podrost': 'limegreen', 'Paseky': 'gold', 'Cesty': 'gray'}

# 1. GRAF: Boxplot (Krabicový graf) rozložení temp
df.boxplot(column='GAP_Tempo', by='Terén', ax=ax1, grid=True, showfliers=True)
ax1.set_title('Rozložení očištěného tempa (GAP) v terénech')
ax1.set_ylabel('Tempo (min/km) - MÉNĚ JE RYCHLEJI')
ax1.set_xlabel('Typ terénu')
ax1.set_ylim(0, 20) # Ořízneme extrémní GPS skoky nad 20 min/km
plt.suptitle('') # Smazání automatického titulku pandas

# 2. GRAF: Bodový graf Sklon vs. Reálné Tempo
for ter, group in df.groupby('Terén'):
    ax2.scatter(group['Sklon'], group['Real_Tempo'], label=ter, alpha=0.6, c=colors.get(ter, 'black'), edgecolors='w', s=50)

ax2.set_title('Závislost Reálného Tempa na Sklonu')
ax2.set_xlabel('Sklon (%) [Z kopce <--- ---> Do kopce]')
ax2.set_ylabel('Reálné tempo (min/km)')
ax2.axvline(0, color='black', linestyle='--', linewidth=1) # Osa nula
ax2.set_ylim(0, 20)
ax2.legend(title="Terén")
ax2.grid(True)

plt.tight_layout()
plt.show()