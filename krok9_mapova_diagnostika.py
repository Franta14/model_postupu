import xml.etree.ElementTree as ET
import gpxpy
import pandas as pd
import math
import matplotlib.pyplot as plt
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union

# --- NASTAVENÍ SOUBORŮ ---
omap_file = 'Homolka_Vojirov_20240917.omap'
gpx_file = '5. 4. 2026 Velikonoce PGP - middle, H18-21_Top Masters, Čtrnáct František.gpx' 

REF_LAT = 49.02982779
REF_LON = 14.9847593

# --- 🎯 VLOŽ SVÁ NOVÁ ČÍSLA Z KALIBRÁTORU ---
OFFSET_X = 0.15
OFFSET_Y = -0.19
ROTACE   = 4.34
MERITKO  = 0.1000

SIRKA_CESTY_BUFFER = 1.0   

print("1. Načítám mapu...")
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
                            x, y = float(parts[0])/1000, -float(parts[1])/1000
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

print("2. Zpracovávám GPX pomocí nové robustní matematiky...")
with open(gpx_file, 'r', encoding='utf-8') as f:
    gpx = gpxpy.parse(f)

data = []
cos_a, sin_a = math.cos(math.radians(ROTACE)), math.sin(math.radians(ROTACE))

for track in gpx.tracks:
    for segment in track.segments:
        for p in segment.points:
            # Zajímá nás jen pohyb, čas pro 2D vizualizaci nepotřebujeme
            rx = (p.longitude - REF_LON) * 111320 * math.cos(math.radians(REF_LAT))
            ry = (p.latitude - REF_LAT) * 111320
            
            tx, ty = rx * MERITKO, ry * MERITKO
            final_x = (tx * cos_a - ty * sin_a) + OFFSET_X
            final_y = (tx * sin_a + ty * cos_a) + OFFSET_Y
            map_point = Point(final_x, final_y)
            
            terrain = "Bily les"
            if merged_geom["Cesty"].contains(map_point): terrain = "Cesty"
            elif merged_geom["Hustnik"].contains(map_point): terrain = "Hustnik"
            elif merged_geom["Podrost"].contains(map_point): terrain = "Podrost"
            elif merged_geom["Paseky"].contains(map_point): terrain = "Paseky"
                
            data.append({"Terén": terrain, "X": final_x, "Y": final_y})

df = pd.DataFrame(data, columns=["Terén", "X", "Y"])

if df.empty:
    print("🚨 CHYBA: Žádné body neprošly výpočtem!")
    exit()

print("3. Vykresluji mapu...")
fig, ax = plt.subplots(figsize=(14, 10))
fig.canvas.manager.set_window_title('Fixní Prostorová Diagnostika Livelox GPX')

ax.plot(draw_data["Voda"][0], draw_data["Voda"][1], color='dodgerblue', linewidth=2, alpha=0.5)
ax.plot(draw_data["Hustnik"][0], draw_data["Hustnik"][1], color='darkgreen', linewidth=1.5, alpha=0.2)
ax.plot(draw_data["Paseky"][0], draw_data["Paseky"][1], color='gold', linewidth=1.5, alpha=0.2)
ax.plot(draw_data["Cesty"][0], draw_data["Cesty"][1], color='gray', linewidth=2, alpha=0.4)

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
        ax.scatter(subset['X'], subset['Y'], c=color, label=label, s=35, edgecolors='white', linewidths=0.5, zorder=5)

ax.set_title("Vizuální kontrola přiřazení terénů\nKolečkem myši zazoomuj a zkontroluj černou barvu na cestách.")
ax.legend(loc='upper left', framealpha=1.0)
ax.axis('equal')
ax.grid(True, linestyle=':', alpha=0.6)

def on_scroll(event):
    if event.inaxes != ax: return
    zoom_factor = 1 / 1.2 if event.button == 'up' else 1.2
    cur_xlim, cur_ylim = ax.get_xlim(), ax.get_ylim()
    xdata, ydata = event.xdata, event.ydata
    new_width, new_height = (cur_xlim[1] - cur_xlim[0]) * zoom_factor, (cur_ylim[1] - cur_ylim[0]) * zoom_factor
    relx, rely = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0]), (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])
    ax.set_xlim([xdata - new_width * (1-relx), xdata + new_width * (relx)])
    ax.set_ylim([ydata - new_height * (1-rely), ydata + new_height * (rely)])
    fig.canvas.draw_idle()

fig.canvas.mpl_connect('scroll_event', on_scroll)
plt.show()