import xml.etree.ElementTree as ET
import gpxpy
import pandas as pd
import math
import matplotlib.pyplot as plt
import numpy as np

# Pokus o import optimalizačních knihoven
try:
    from scipy.optimize import minimize
    from scipy.spatial.distance import cdist
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("⚠️ Knihovna 'scipy' není nainstalována. Funkce Auto-Snap (O) nebude fungovat. Spusť: pip install scipy")

# Vypnutí skrytých zkratek
klavesy_k_vymazani = ['save', 'quit', 'home', 'back', 'forward', 'pan', 'zoom', 'fullscreen', 'left', 'right', 'up', 'down']
for k in klavesy_k_vymazani:
    try: plt.rcParams[f'keymap.{k}'] = []
    except KeyError: pass

# --- NASTAVENÍ SOUBORŮ ---
omap_file = 'Homolka_Vojirov_20240917.omap'
gpx_file = '5. 4. 2026 Velikonoce PGP - middle, H18-21_Top Masters, Čtrnáct František.gpx' 
xml_file = 'Vel.xml'
vystupni_soubor = 'nakalibrovana_trasa.csv'

REF_LAT = 49.02982779
REF_LON = 14.9847593

print("1. Počítám XML Kalibraci...")
tree_xml = ET.parse(xml_file)
root_xml = tree_xml.getroot()
ns = {'ns': 'http://www.orienteering.org/datastandard/3.0'}
controls = []
for ctrl in root_xml.findall('.//ns:Control', ns):
    pos = ctrl.find('ns:Position', ns)
    mpos = ctrl.find('ns:MapPosition', ns)
    if pos is not None and mpos is not None:
        controls.append({
            'lat': float(pos.attrib['lat']), 
            'lon': float(pos.attrib['lng']), 
            'mx': float(mpos.attrib['x']), 
            'my': float(mpos.attrib['y']) 
        })

c1, c2 = controls[0], controls[1]
max_dist = 0
for c_a in controls:
    for c_b in controls:
        d = math.hypot(c_a['mx'] - c_b['mx'], c_a['my'] - c_b['my'])
        if d > max_dist:
            max_dist, c1, c2 = d, c_a, c_b

rx1 = (c1['lon'] - REF_LON) * 111320 * math.cos(math.radians(REF_LAT))
ry1 = (c1['lat'] - REF_LAT) * 111320
rx2 = (c2['lon'] - REF_LON) * 111320 * math.cos(math.radians(REF_LAT))
ry2 = (c2['lat'] - REF_LAT) * 111320

dist_gps = math.sqrt((rx2 - rx1)**2 + (ry2 - ry1)**2)
dist_map = math.sqrt((c2['mx'] - c1['mx'])**2 + (c2['my'] - c1['my'])**2)
CURRENT_SCALE = dist_map / dist_gps

angle_gps = math.atan2(ry2 - ry1, rx2 - rx1)
angle_map = math.atan2(c2['my'] - c1['my'], c2['mx'] - c1['mx'])
ROTACE_RAD = angle_map - angle_gps
CURRENT_ROT = math.degrees(ROTACE_RAD)
cos_a, sin_a = math.cos(ROTACE_RAD), math.sin(ROTACE_RAD)

tx1, ty1 = rx1 * CURRENT_SCALE, ry1 * CURRENT_SCALE
rot_x1 = tx1 * cos_a - ty1 * sin_a
rot_y1 = tx1 * sin_a + ty1 * cos_a
CURRENT_OFFSET_X = c1['mx'] - rot_x1
CURRENT_OFFSET_Y = c1['my'] - rot_y1

print("2. Načítám mapu pro vizualizaci...")
tree = ET.parse(omap_file)
root = tree.getroot()
symbol_map = {elem.attrib.get('id'): elem.attrib.get('code') for elem in root.iter() if 'symbol' in elem.tag.lower()}
draw_data = {"Cesty": ([], []), "Paseky": ([], []), "Hustnik": ([], []), "Voda": ([], [])}

for obj in root.iter():
    if 'object' in obj.tag.lower():
        isom = symbol_map.get(obj.attrib.get('symbol', ""), "")
        xs, ys = [], []
        for child in obj:
            if 'coords' in child.tag.lower() and child.text:
                for p in child.text.strip().split(';'):
                    parts = p.strip().split()
                    if len(parts) >= 2:
                        try:
                            xs.append(float(parts[0]) / 1000)
                            ys.append(-float(parts[1]) / 1000)
                        except ValueError: pass
                break
        if xs:
            if isom.startswith('50'): draw_data["Cesty"][0].extend(xs + [None]); draw_data["Cesty"][1].extend(ys + [None])
            elif isom in ['403.0', '404.0']: draw_data["Paseky"][0].extend(xs + [None]); draw_data["Paseky"][1].extend(ys + [None])
            elif isom in ['406.0', '408.0', '410.0', '407.0', '409.0']: draw_data["Hustnik"][0].extend(xs + [None]); draw_data["Hustnik"][1].extend(ys + [None])
            elif isom.startswith('30'): draw_data["Voda"][0].extend(xs + [None]); draw_data["Voda"][1].extend(ys + [None])

print("3. Načítám GPX...")
with open(gpx_file, 'r', encoding='utf-8') as f: gpx = gpxpy.parse(f)
valid_points = [p for t in gpx.tracks for s in t.segments for p in s.points if p.time]

raw_rx = [(p.longitude - REF_LON) * 111320 * math.cos(math.radians(REF_LAT)) for p in valid_points]
raw_ry = [(p.latitude - REF_LAT) * 111320 for p in valid_points]

fig_tune, ax_tune = plt.subplots(figsize=(14, 10))
fig_tune.canvas.manager.set_window_title('KROK 1: DOLADĚNÍ A EXPORT')
ax_tune.plot(draw_data["Voda"][0], draw_data["Voda"][1], color='dodgerblue', linewidth=2, alpha=0.5)
ax_tune.plot(draw_data["Hustnik"][0], draw_data["Hustnik"][1], color='darkgreen', linewidth=1.5, alpha=0.2)
ax_tune.plot(draw_data["Paseky"][0], draw_data["Paseky"][1], color='gold', linewidth=1.5, alpha=0.2)
ax_tune.plot(draw_data["Cesty"][0], draw_data["Cesty"][1], color='gray', linewidth=2, alpha=0.4)

for c in controls:
    ax_tune.plot(c['mx'], c['my'], marker='o', markersize=12, color='magenta', fillstyle='none', markeredgewidth=2)

line_tune, = ax_tune.plot([], [], color='black', marker='.', linestyle='none', markersize=4)

if SCIPY_AVAILABLE:
    titulek = "O = AUTO-SNAP k bodům | ŠIPKY = Posun | A/D = Rotace | +/- = Zoom | ENTER = Uložit"
else:
    titulek = "ŠIPKY = Posun | A/D = Rotace | +/- = Zoom | ENTER = Uložit"
ax_tune.set_title(titulek)
ax_tune.axis('equal')

def update_tune_plot():
    cos_a, sin_a = math.cos(math.radians(CURRENT_ROT)), math.sin(math.radians(CURRENT_ROT))
    fx, fy = [], []
    for rx, ry in zip(raw_rx, raw_ry):
        tx, ty = rx * CURRENT_SCALE, ry * CURRENT_SCALE
        fx.append((tx * cos_a - ty * sin_a) + CURRENT_OFFSET_X)
        fy.append((tx * sin_a + ty * cos_a) + CURRENT_OFFSET_Y)
    line_tune.set_xdata(fx)
    line_tune.set_ydata(fy)
    fig_tune.canvas.draw_idle()

# --- MAGICKÁ FUNKCE AUTO-SNAP ---
def auto_snap():
    global CURRENT_OFFSET_X, CURRENT_OFFSET_Y, CURRENT_ROT, CURRENT_SCALE
    print("\n⏳ Běžím matematickou optimalizaci (Auto-Snap)... Počkej chvíli!")
    
    ctrl_coords = np.array([[c['mx'], c['my']] for c in controls])
    gps_coords = np.array(list(zip(raw_rx, raw_ry)))
    
    def cost_function(params):
        dx, dy, rot, scale = params
        rad = math.radians(rot)
        ca, sa = math.cos(rad), math.sin(rad)
        
        tx = gps_coords[:, 0] * scale
        ty = gps_coords[:, 1] * scale
        fx = tx * ca - ty * sa + dx
        fy = tx * sa + ty * ca + dy
        trans_gps = np.column_stack((fx, fy))
        
        # Spočítá vzdálenosti od každé kontroly k nejbližšímu bodu na trase
        distances = cdist(ctrl_coords, trans_gps)
        min_distances = np.min(distances, axis=1)
        
        # Chceme minimalizovat součet čtverců vzdáleností
        return np.sum(min_dists**2) if (min_dists := min_distances) is not None else 0

    init_params = [CURRENT_OFFSET_X, CURRENT_OFFSET_Y, CURRENT_ROT, CURRENT_SCALE]
    
    # Spuštění minimalizačního algoritmu
    res = minimize(cost_function, init_params, method='Nelder-Mead')
    
    CURRENT_OFFSET_X, CURRENT_OFFSET_Y, CURRENT_ROT, CURRENT_SCALE = res.x
    print("✅ Optimalizace hotova! Trasa byla magneticky přitažena ke kontrolám.")
    update_tune_plot()

def on_key_tune(event):
    global CURRENT_OFFSET_X, CURRENT_OFFSET_Y, CURRENT_ROT, CURRENT_SCALE, cos_a, sin_a
    if event.key is None: return
    k = event.key.lower().replace('shift+', '')
    
    if k == 'right': CURRENT_OFFSET_X += 0.5
    elif k == 'left': CURRENT_OFFSET_X -= 0.5
    elif k == 'up': CURRENT_OFFSET_Y += 0.5
    elif k == 'down': CURRENT_OFFSET_Y -= 0.5
    elif k == 'a': CURRENT_ROT += 0.1
    elif k == 'd': CURRENT_ROT -= 0.1
    elif k in ['+', '=']: CURRENT_SCALE *= 1.002
    elif k in ['-', '_']: CURRENT_SCALE /= 1.002
    elif k == 'o' and SCIPY_AVAILABLE: 
        auto_snap()
        return
    elif k == 'enter': 
        plt.close(fig_tune)
        return
    
    cos_a, sin_a = math.cos(math.radians(CURRENT_ROT)), math.sin(math.radians(CURRENT_ROT))
    update_tune_plot()

fig_tune.canvas.mpl_connect('key_press_event', on_key_tune)
update_tune_plot()
plt.show()

print("\n💾 Ukládám dokonalou trasu do CSV...")
cos_a, sin_a = math.cos(math.radians(CURRENT_ROT)), math.sin(math.radians(CURRENT_ROT))
export_data = []
for i in range(len(valid_points)):
    p = valid_points[i]
    tx, ty = raw_rx[i] * CURRENT_SCALE, raw_ry[i] * CURRENT_SCALE
    fx = (tx * cos_a - ty * sin_a) + CURRENT_OFFSET_X
    fy = (tx * sin_a + ty * cos_a) + CURRENT_OFFSET_Y
    
    dist = valid_points[i-1].distance_2d(p) if i > 0 else 0
    dt = (p.time - valid_points[i-1].time).total_seconds() if i > 0 else 0
    export_data.append({"Time": p.time, "X": fx, "Y": fy, "Dist_m": dist, "TimeDiff_s": dt})

pd.DataFrame(export_data).to_csv(vystupni_soubor, index=False)
print(f"✅ HOTOVO! Trasa uložena do: {vystupni_soubor}")