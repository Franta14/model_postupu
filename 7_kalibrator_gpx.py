import numpy as np
import matplotlib.pyplot as plt
import math
import os
from PIL import Image
import xml.etree.ElementTree as ET
from datetime import datetime

# =====================================================================
# --- NASTAVENI ---
# =====================================================================
gpx_file = "Zapa.gpx"     # Tvůj GPX soubor z hodinek
import config
xml_file = config.XML_FILE     # 👈 NOVÉ: Tvůj IOF XML soubor z OCADu/Purple Pen
map_image_file = config.PNG_FILE

# ZÁKLADNÍ TEMPO MODELU (To, které chceme kalibrovat)
ZAKLADNI_TEMPO_MIN = 3
ZAKLADNI_TEMPO_SEC = 50
NASOBIC_MERITKA = 10.0
CENA_LESNI_CESTY = 0.965

print("🚀 Startuji Analytický kalibrátor řízený přes IOF XML...")
zakladni_tempo_desetinne = ZAKLADNI_TEMPO_MIN + (ZAKLADNI_TEMPO_SEC / 60.0)

# =====================================================================
# 1. NAČTENÍ DAT, GPX A IOF XML
# =====================================================================
try:
    cost_grid = np.load("cenova_mapa.npy")
    elev_grid = np.load("vyskova_mapa.npy")
    meta = np.load("cenova_mapa_meta.npy")
    min_x, min_y, max_x, max_y, grid_size = meta
    scale_x, scale_y, off_x, off_y = np.load("kalibrace.npy")
    height, width = cost_grid.shape
except FileNotFoundError:
    print("❌ Chybi .npy soubory. Spust skripty 5 a proved kalibraci ve skriptu 6.")
    raise SystemExit(1)

# --- NAČTENÍ IOF XML ---
print(f"🗺️ Čtu absolutní souřadnice kontrol z IOF XML: {xml_file}")
tree_xml = ET.parse(xml_file)
root_xml = tree_xml.getroot()

for elem in root_xml.iter():
    if '}' in elem.tag: elem.tag = elem.tag.split('}', 1)[1]

start_gps = None
finish_gps = None

for control in root_xml.findall('.//Control'):
    ctype = control.get('type')
    pos = control.find('Position')
    if pos is not None:
        lng = float(pos.get('lng'))
        lat = float(pos.get('lat'))
        if ctype == 'Start': start_gps = (lng, lat)
        if ctype == 'Finish': finish_gps = (lng, lat)

if not start_gps or not finish_gps:
    print("❌ V XML souboru chybí Start nebo Cíl!")
    raise SystemExit(1)

# --- NAČTENÍ GPX ---
print(f"📍 Načítám GPX trasu z hodinek: {gpx_file}")
tree_gpx = ET.parse(gpx_file)
root_gpx = tree_gpx.getroot()

for elem in root_gpx.iter():
    if '}' in elem.tag: elem.tag = elem.tag.split('}', 1)[1]

gpx_points = []
for trkpt in root_gpx.iter('trkpt'):
    lat = float(trkpt.attrib['lat'])
    lon = float(trkpt.attrib['lon'])
    time_str = trkpt.find('time').text
    
    time_str_clean = time_str.replace('Z', '+0000')
    try:
        time_obj = datetime.strptime(time_str_clean, "%Y-%m-%dT%H:%M:%S.%f%z")
    except ValueError:
        time_obj = datetime.strptime(time_str_clean, "%Y-%m-%dT%H:%M:%S%z")
    gpx_points.append((lon, lat, time_obj))

if len(gpx_points) < 2:
    print("❌ GPX soubor neobsahuje dostatek dat!")
    raise SystemExit(1)

# =====================================================================
# 2. INTERAKTIVNÍ ZAROVNÁNÍ NA MAPU
# =====================================================================
print("\n🛠️ PŘESNÁ KALIBRACE...")

img = Image.open(map_image_file)
fig, ax = plt.subplots(figsize=(14, 10))
ax.imshow(img, interpolation='nearest')
navod_mapa = "\n[LUPA/POSUN povoleno] | Vypni lupu a klikni na START a pak na CÍL"
ax.set_title(f"Zarovnání přes XML{navod_mapa}", fontweight='bold', color='red')

map_anchors = []
def onclick_map(event):
    if event.inaxes != ax: return
    if fig.canvas.toolbar.mode != '': return # Ochrana proti loupě
    
    if event.button == 1:
        map_anchors.append((event.xdata, event.ydata))
        ax.plot(event.xdata, event.ydata, 'mo', markersize=12)
        
        # Interaktivní textová nápověda
        if len(map_anchors) == 1:
            ax.set_title("Nyní klikni na CÍL", fontweight='bold', color='blue')
        
        fig.canvas.draw()
        if len(map_anchors) == 2: fig.canvas.stop_event_loop()

fig.canvas.mpl_connect('button_press_event', onclick_map)
plt.show(block=False)
fig.canvas.start_event_loop(timeout=0)
plt.close(fig)

# --- MATEMATIKA: 2D Afinní transformace (Řeší i rotaci k magnetickému severu) ---
p1, p2 = start_gps, finish_gps
q1, q2 = map_anchors[0], map_anchors[1]

# Korekce zakřivení zeměměpisné délky podle zeměpisné šířky
avg_lat = math.radians((p1[1] + p2[1]) / 2.0)
v_x = (p2[0] - p1[0]) * math.cos(avg_lat)
v_y = p2[1] - p1[1]

u_x = q2[0] - q1[0]
u_y = q2[1] - q1[1]

angle_p = math.atan2(v_y, v_x)
angle_q = math.atan2(u_y, u_x)
d_angle = angle_q - angle_p # Natočení mapy

mag_p = math.hypot(v_x, v_y)
mag_q = math.hypot(u_x, u_y)
trans_scale = mag_q / mag_p if mag_p != 0 else 1.0

def gpx_to_grid(lon, lat):
    # 1. Převod na metrický rozdíl od Startu
    dx = (lon - p1[0]) * math.cos(avg_lat)
    dy = lat - p1[1]
    
    # 2. Rotace do osy mapy
    rx = dx * math.cos(d_angle) - dy * math.sin(d_angle)
    ry = dx * math.sin(d_angle) + dy * math.cos(d_angle)
    
    # 3. Zvětšení a posun na pixely obrázku
    img_x = rx * trans_scale + q1[0]
    img_y = ry * trans_scale + q1[1]
    
    # 4. Převod z pixelů na naši mřížku
    gx, gy = img_x * scale_x + off_x, img_y * scale_y + off_y
    return max(0, min(height - 1, int(gy))), max(0, min(width - 1, int(gx)))

# =====================================================================
# 3. ANALÝZA BĚHU (Model vs. GPX Realita)
# =====================================================================
print("\n🧠 Analyzuji krok za krokem...")

stats = {}

for i in range(1, len(gpx_points)):
    lon1, lat1, t1 = gpx_points[i-1]
    lon2, lat2, t2 = gpx_points[i]
    
    y1, x1 = gpx_to_grid(lon1, lat1)
    y2, x2 = gpx_to_grid(lon2, lat2)
    
    real_time_sec = (t2 - t1).total_seconds()
    if real_time_sec <= 0 or real_time_sec > 120: continue 
    
    grid_dist = math.hypot(x2 - x1, y2 - y1)
    if grid_dist == 0: continue
    real_dist_m = grid_dist * grid_size * NASOBIC_MERITKA
    
    mid_y, mid_x = int((y1+y2)/2), int((x1+x2)/2)
    if not (0 <= mid_y < height and 0 <= mid_x < width): continue
        
    terren_cost = cost_grid[mid_y, mid_x]
    if terren_cost >= 9000: continue # Přeskakujeme zdi, pokud do nich skočila nepřesná GPS
    
    dz = elev_grid[y2, x2] - elev_grid[y1, x1]
    sklon = dz / real_dist_m if real_dist_m > 0 else 0
    
    if sklon > 0: hill_multiplier = 1.0 + (sklon * 1.4)
    elif sklon < -0.25: hill_multiplier = 1.0 + (abs(sklon) * 0.4)
    else: hill_multiplier = 1.0

    step_effort = (real_dist_m / NASOBIC_MERITKA) * terren_cost * hill_multiplier
    model_time_min = (step_effort * NASOBIC_MERITKA) * (zakladni_tempo_desetinne / (1000.0 * CENA_LESNI_CESTY))
    model_time_sec = model_time_min * 60.0
    
    klíč_terénu = round(terren_cost, 2)
    if klíč_terénu not in stats: stats[klíč_terénu] = {'real': 0, 'model': 0, 'dist': 0}
    
    stats[klíč_terénu]['real'] += real_time_sec
    stats[klíč_terénu]['model'] += model_time_sec
    stats[klíč_terénu]['dist'] += real_dist_m

# =====================================================================
# 4. ZÁVĚREČNÉ VYSVĚDČENÍ
# =====================================================================
print("\n" + "="*60)
print("📊 VÝSLEDKY KALIBRACE MODELU (Díky přesnosti IOF XML)")
print("="*60)
print(f"{'Cena v Modelu':<15} | {'Vzdálenost':<12} | {'Realita vs Model':<17} | {'Doporučení'}")
print("-" * 80)

for cost in sorted(stats.keys()):
    data = stats[cost]
    if data['dist'] < 80: continue 
    
    real_t = data['real']
    mod_t = data['model']
    odchylka = (real_t / mod_t) * 100 - 100 
    
    nová_cena = cost * (real_t / mod_t)
    
    if odchylka > 5:
        doporuceni = f"Zvýšit na cca {nová_cena:.2f} (Běžec byl pomalejší)"
    elif odchylka < -5:
        doporuceni = f"Snížit na cca {nová_cena:.2f} (Běžec byl rychlejší)"
    else:
        doporuceni = "Cena je PERFEKTNÍ! ✅"
        
    print(f"{cost:<15.2f} | {data['dist']:<9.0f} m | {odchylka:>+5.1f} % času       | {doporuceni}")

print("="*80)