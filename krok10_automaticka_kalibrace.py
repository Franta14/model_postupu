import xml.etree.ElementTree as ET
import gpxpy
import pandas as pd
import math
import matplotlib.pyplot as plt
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union

# Vypnutí výchozích zkratek Matplotlibu, aby se nepletly s naším laděním
plt.rcParams['keymap.save'] = ''
plt.rcParams['keymap.quit'] = ''
plt.rcParams['keymap.home'] = ''
plt.rcParams['keymap.back'] = ''
plt.rcParams['keymap.forward'] = ''

# --- NASTAVENÍ SOUBORŮ ---
omap_file = 'Homolka_Vojirov_20240917.omap'
gpx_file = '5. 4. 2026 Velikonoce PGP - middle, H18-21_Top Masters, Čtrnáct František (2).gpx' 
xml_file = 'Vel.xml'

REF_LAT = 49.02982779
REF_LON = 14.9847593
SIRKA_CESTY_BUFFER = 0.2   # 2 metry tolerance kolem cest

# =====================================================================
# 1. AUTOMATICKÁ KALIBRACE (Tvůj fungující základ)
# =====================================================================
print("1. Analyzuji IOF XML a spouštím automatickou kalibraci...")
try:
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

    if len(controls) < 2:
        raise ValueError("Nedostatek kontrol v XML!")

    max_dist = 0
    c1, c2 = controls[0], controls[1]
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
    
    # Výchozí automatické hodnoty
    CURRENT_SCALE = dist_map / dist_gps

    angle_gps = math.atan2(ry2 - ry1, rx2 - rx1)
    angle_map = math.atan2(c2['my'] - c1['my'], c2['mx'] - c1['mx'])
    CURRENT_ROT = math.degrees(angle_map - angle_gps)
    
    cos_a = math.cos(math.radians(CURRENT_ROT))
    sin_a = math.sin(math.radians(CURRENT_ROT))

    tx1, ty1 = rx1 * CURRENT_SCALE, ry1 * CURRENT_SCALE
    rot_x1 = tx1 * cos_a - ty1 * sin_a
    rot_y1 = tx1 * sin_a + ty1 * cos_a
    
    CURRENT_OFFSET_X = c1['mx'] - rot_x1
    CURRENT_OFFSET_Y = c1['my'] - rot_y1

    print(f"✅ AUTO-KALIBRACE HOTOVA (Předběžná rotace: {CURRENT_ROT:.2f}°)")

except Exception as e:
    print(f"🚨 CHYBA při čtení XML: {e}")
    exit()

# =====================================================================
# 2. NAČTENÍ MAPY 
# =====================================================================
print("2. Načítám polygony mapy...")
tree = ET.parse(omap_file)
root = tree.getroot()

symbol_map = {elem.attrib.get('id'): elem.attrib.get('code') for elem in root.iter() if 'symbol' in elem.tag.lower()}
kategorie = {"Cesty": [], "Paseky": [], "Hustnik": [], "Podrost": [], "Voda": []}
draw_data = {"Cesty": ([], []), "Paseky": ([], []), "Hustnik": ([], []), "Voda": ([], [])}

for obj in root.iter():
    if 'object' in obj.tag.lower():
        sym_id = obj.attrib.get('symbol')
        if not sym_id: continue
        isom = symbol_map.get(sym_id, "")
        
        pts, xs, ys = [], [], []
        for child in obj:
            if 'coords' in child.tag.lower() and child.text:
                for p in child.text.strip().split(';'):
                    parts = p.strip().split()
                    if len(parts) >= 2:
                        try:
                            x = float(parts[0]) / 1000
                            y = -float(parts[1]) / 1000
                            pts.append((x, y))
                            xs.append(x)
                            ys.append(y)
                        except ValueError: pass
                break
        if not pts: continue

        if isom.startswith('50') and len(pts) >= 2: kategorie["Cesty"].append(LineString(pts).buffer(SIRKA_CESTY_BUFFER))
        elif len(pts) >= 3:
            poly = Polygon(pts)
            if not poly.is_valid: poly = poly.buffer(0)
            if isom in ['403.0', '404.0']: kategorie["Paseky"].append(poly)
            elif isom in ['406.0', '408.0', '410.0']: kategorie["Hustnik"].append(poly)
            elif isom in ['407.0', '409.0']: kategorie["Podrost"].append(poly)
            elif isom.startswith('30'): kategorie["Voda"].append(poly)

        if isom.startswith('50'): draw_data["Cesty"][0].extend(xs + [None]); draw_data["Cesty"][1].extend(ys + [None])
        elif isom in ['403.0', '404.0']: draw_data["Paseky"][0].extend(xs + [None]); draw_data["Paseky"][1].extend(ys + [None])
        elif isom in ['406.0', '408.0', '410.0']: draw_data["Hustnik"][0].extend(xs + [None]); draw_data["Hustnik"][1].extend(ys + [None])
        elif isom.startswith('30'): draw_data["Voda"][0].extend(xs + [None]); draw_data["Voda"][1].extend(ys + [None])

merged_geom = {k: unary_union(v) if v else Polygon() for k, v in kategorie.items()}

# =====================================================================
# 3. NAČTENÍ GPX
# =====================================================================
print("3. Načítám Livelox GPX pro zobrazení...")
with open(gpx_file, 'r', encoding='utf-8') as f:
    gpx = gpxpy.parse(f)

valid_points = [p for t in gpx.tracks for s in t.segments for p in s.points if p.time]

# Příprava čistých GPS souřadnic pro rychlou rotaci v paměti
raw_rx, raw_ry = [], []
for p in valid_points:
    raw_rx.append((p.longitude - REF_LON) * 111320 * math.cos(math.radians(REF_LAT)))
    raw_ry.append((p.latitude - REF_LAT) * 111320)

# =====================================================================
# 4. INTERAKTIVNÍ MIKRO-LADĚNÍ
# =====================================================================
print("\n=== OTEVÍRÁM OKNO PRO MIKRO-LADĚNÍ ===")
print(" Zazoomuj kolečkem nad nějakou cestu.")
print(" Šipky    = Posun (Krok 0.5m)")
print(" A / D    = Rotace")
print(" + / -    = Měřítko (Zoom)")
print(" ENTER    = Uložit a Spustit výpočet!\n")

fig_tune, ax_tune = plt.subplots(figsize=(14, 10))
fig_tune.canvas.manager.set_window_title('KROK 1: MIKRO-LADĚNÍ TRASY')

ax_tune.plot(draw_data["Voda"][0], draw_data["Voda"][1], color='dodgerblue', linewidth=2, alpha=0.5)
ax_tune.plot(draw_data["Hustnik"][0], draw_data["Hustnik"][1], color='darkgreen', linewidth=1.5, alpha=0.2)
ax_tune.plot(draw_data["Paseky"][0], draw_data["Paseky"][1], color='gold', linewidth=1.5, alpha=0.2)
ax_tune.plot(draw_data["Cesty"][0], draw_data["Cesty"][1], color='gray', linewidth=2, alpha=0.4)

for c in controls:
    ax_tune.plot(c['mx'], c['my'], marker='o', markersize=12, color='magenta', fillstyle='none', markeredgewidth=2)

line_tune, = ax_tune.plot([], [], color='black', marker='.', linestyle='none', markersize=3, zorder=5)

ax_tune.set_title("MIKRO-LADĚNÍ: Použij Šipky pro posun, A/D pro rotaci, +/- pro měřítko.\nAž to sedne na milimetr, stiskni ENTER.")
ax_tune.axis('equal')
ax_tune.grid(True, linestyle=':', alpha=0.6)

def update_tune_plot():
    cos_a = math.cos(math.radians(CURRENT_ROT))
    sin_a = math.sin(math.radians(CURRENT_ROT))
    fx, fy = [], []
    for rx, ry in zip(raw_rx, raw_ry):
        tx, ty = rx * CURRENT_SCALE, ry * CURRENT_SCALE
        fx.append((tx * cos_a - ty * sin_a) + CURRENT_OFFSET_X)
        fy.append((tx * sin_a + ty * cos_a) + CURRENT_OFFSET_Y)
    line_tune.set_xdata(fx)
    line_tune.set_ydata(fy)
    fig_tune.canvas.draw_idle()

def on_key_tune(event):
    global CURRENT_OFFSET_X, CURRENT_OFFSET_Y, CURRENT_ROT, CURRENT_SCALE
    k = event.key.lower().replace('shift+', '')
    
    if k == 'right': CURRENT_OFFSET_X += 0.5
    elif k == 'left': CURRENT_OFFSET_X -= 0.5
    elif k == 'up': CURRENT_OFFSET_Y += 0.5
    elif k == 'down': CURRENT_OFFSET_Y -= 0.5
    elif k == 'a': CURRENT_ROT += 0.1
    elif k == 'd': CURRENT_ROT -= 0.1
    elif k in ['+', '=']: CURRENT_SCALE *= 1.001
    elif k in ['-', '_']: CURRENT_SCALE /= 1.001
    elif k == 'enter':
        plt.close(fig_tune)
        return
    update_tune_plot()

def on_scroll(event):
    if event.inaxes != event.canvas.figure.axes[0]: return
    zoom_factor = 1 / 1.2 if event.button == 'up' else 1.2
    ax = event.inaxes
    cur_xlim, cur_ylim = ax.get_xlim(), ax.get_ylim()
    xdata, ydata = event.xdata, event.ydata
    new_width = (cur_xlim[1] - cur_xlim[0]) * zoom_factor
    new_height = (cur_ylim[1] - cur_ylim[0]) * zoom_factor
    relx = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
    rely = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])
    ax.set_xlim([xdata - new_width * (1-relx), xdata + new_width * (relx)])
    ax.set_ylim([ydata - new_height * (1-rely), ydata + new_height * (rely)])
    event.canvas.draw_idle()

fig_tune.canvas.mpl_connect('key_press_event', on_key_tune)
fig_tune.canvas.mpl_connect('scroll_event', on_scroll)
update_tune_plot()
plt.show()  # Zastaví skript, dokud uživatel nestiskne ENTER

# =====================================================================
# 5. FINÁLNÍ VÝPOČET S DOLADĚNÝMI PARAMETRY
# =====================================================================
print("4. Ladění dokončeno! Spouštím výpočet tempa...")
cos_a = math.cos(math.radians(CURRENT_ROT))
sin_a = math.sin(math.radians(CURRENT_ROT))

data = []
for i in range(1, len(valid_points)):
    p1 = valid_points[i-1]
    p2 = valid_points[i]
    
    time_diff = (p2.time - p1.time).total_seconds()
    dist = p1.distance_2d(p2)
    
    if time_diff > 0 and dist > 0:
        tempo = (1000 / (dist / time_diff)) / 60
        
        if 2.0 < tempo < 40.0:
            # Aplikace těch nejnovějších, tebou doladěných čísel!
            rx = raw_rx[i]
            ry = raw_ry[i]
            tx, ty = rx * CURRENT_SCALE, ry * CURRENT_SCALE
            final_x = (tx * cos_a - ty * sin_a) + CURRENT_OFFSET_X
            final_y = (tx * sin_a + ty * cos_a) + CURRENT_OFFSET_Y
            map_point = Point(final_x, final_y)
            
            terrain = "Bily les"
            if merged_geom["Cesty"].contains(map_point): terrain = "Cesty"
            elif merged_geom["Hustnik"].contains(map_point): terrain = "Hustnik"
            elif merged_geom["Podrost"].contains(map_point): terrain = "Podrost"
            elif merged_geom["Paseky"].contains(map_point): terrain = "Paseky"
                
            data.append({"Terén": terrain, "X": final_x, "Y": final_y, "Tempo_min_km": tempo})

df = pd.DataFrame(data)

# =====================================================================
# 6. VÝPIS VÝSLEDKŮ A VYKRESLENÍ FINÁLNÍ MAPY
# =====================================================================
print("\n" + "="*40)
print("🏆 FINÁLNÍ VÝSLEDKY TVÉHO TEMPA:")
print("="*40)
if not df.empty:
    summary = df.groupby("Terén")["Tempo_min_km"].median().round(2).sort_values()
    for ter, tempo in summary.items():
        minuty = int(tempo)
        vteriny = int((tempo - minuty) * 60)
        print(f"{ter.ljust(15)} : {minuty}:{vteriny:02d} min/km")
else:
    print("Nedostatek dat pro výpočet tempa.")
print("="*40 + "\n")

fig_final, ax_final = plt.subplots(figsize=(14, 10))
fig_final.canvas.manager.set_window_title('KROK 2: FINÁLNÍ OBARVENÁ MAPA')

ax_final.plot(draw_data["Voda"][0], draw_data["Voda"][1], color='dodgerblue', linewidth=2, alpha=0.5)
ax_final.plot(draw_data["Hustnik"][0], draw_data["Hustnik"][1], color='darkgreen', linewidth=1.5, alpha=0.2)
ax_final.plot(draw_data["Paseky"][0], draw_data["Paseky"][1], color='gold', linewidth=1.5, alpha=0.2)
ax_final.plot(draw_data["Cesty"][0], draw_data["Cesty"][1], color='gray', linewidth=2, alpha=0.4)

colors = {
    'Bily les': ('cyan', 'Bílý les (Azurová)'), 
    'Hustnik': ('darkgreen', 'Hustník (Zelená)'),
    'Podrost': ('limegreen', 'Podrost (Světle zelená)'),
    'Paseky': ('orange', 'Paseky (Oranžová)'),
    'Cesty': ('black', 'Cesty (Černá)')
}

for ter, (color, label) in colors.items():
    subset = df[df['Terén'] == ter]
    if not subset.empty:
        ax_final.scatter(subset['X'], subset['Y'], c=color, label=label, s=20, edgecolors='none', zorder=5)

for c in controls:
    ax_final.plot(c['mx'], c['my'], marker='o', markersize=15, color='magenta', fillstyle='none', markeredgewidth=2, zorder=10)

ax_final.set_title("VÝSLEDEK: Rozpad tempa do terénů po tvém mikro-ladění")
ax_final.legend(loc='upper left', framealpha=1.0)
ax_final.axis('equal')
ax_final.grid(True, linestyle=':', alpha=0.6)

fig_final.canvas.mpl_connect('scroll_event', on_scroll)
plt.show()
