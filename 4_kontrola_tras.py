import xml.etree.ElementTree as ET
import gpxpy
import math
import numpy as np
import os
import matplotlib.pyplot as plt
from shapely.geometry import LineString, Polygon
from scipy.optimize import minimize
from scipy.spatial.distance import cdist

# --- ⚙️ NASTAVENÍ ---
omap_file = 'Homolka_Vojirov_20240917.omap'
xml_file = 'Vel.xml'
slozka_gpx = 'vstupy'  # Složka s přejmenovanými GPX soubory (např. Elias.gpx)

REF_LAT, REF_LON = 49.02982779, 14.9847593

# =====================================================================
# 1. NAČTENÍ MAPY A KONTROL (PRO VIZUALIZACI A SNAP)
# =====================================================================
print("🗺️ Načítám mapu a kontroly...")
tree_xml = ET.parse(xml_file)
root_xml = tree_xml.getroot()
ns = {'ns': 'http://www.orienteering.org/datastandard/3.0'}
controls = []
for ctrl in root_xml.findall('.//ns:Control', ns):
    pos = ctrl.find('ns:Position', ns)
    mpos = ctrl.find('ns:MapPosition', ns)
    if pos is not None and mpos is not None:
        controls.append({
            'lat': float(pos.attrib['lat']), 'lon': float(pos.attrib['lng']), 
            'mx': float(mpos.attrib['x']), 'my': float(mpos.attrib['y'])
        })

ctrl_coords = np.array([[c['mx'], c['my']] for c in controls])

# Hledání nejvzdálenějších kontrol pro pevný matematický základ
c1, c2 = controls[0], controls[1]
max_dist = 0
for c_a in controls:
    for c_b in controls:
        d = math.hypot(c_a['mx'] - c_b['mx'], c_a['my'] - c_b['my'])
        if d > max_dist: max_dist, c1, c2 = d, c_a, c_b

rx1 = (c1['lon'] - REF_LON) * 111320 * math.cos(math.radians(REF_LAT))
ry1 = (c1['lat'] - REF_LAT) * 111320
rx2 = (c2['lon'] - REF_LON) * 111320 * math.cos(math.radians(REF_LAT))
ry2 = (c2['lat'] - REF_LAT) * 111320

tree = ET.parse(omap_file)
root = tree.getroot()
symbol_map = {elem.attrib.get('id'): elem.attrib.get('code') for elem in root.iter() if 'symbol' in elem.tag.lower()}

draw_data = {"Cesty": ([], []), "Paseky": ([], []), "Hustnik": ([], []), "Voda": ([], [])}
for obj in root.iter():
    if 'object' in obj.tag.lower():
        isom = symbol_map.get(obj.attrib.get('symbol', ""), "").split('.')[0]
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
            if isom in ['501', '502', '503', '504', '505', '506', '507', '508', '509']: 
                draw_data["Cesty"][0].extend(xs + [None]); draw_data["Cesty"][1].extend(ys + [None])
            elif isom in ['403', '404']: 
                draw_data["Paseky"][0].extend(xs + [None]); draw_data["Paseky"][1].extend(ys + [None])
            elif isom in ['406', '408', '410', '407', '409']: 
                draw_data["Hustnik"][0].extend(xs + [None]); draw_data["Hustnik"][1].extend(ys + [None])
            elif isom.startswith('30'): 
                draw_data["Voda"][0].extend(xs + [None]); draw_data["Voda"][1].extend(ys + [None])

# =====================================================================
# 2. VYKRESLENÍ PODKLADU
# =====================================================================
fig, ax = plt.subplots(figsize=(16, 10))
fig.canvas.manager.set_window_title('Hromadná kontrola Auto-Snapu')

ax.plot(draw_data["Voda"][0], draw_data["Voda"][1], color='dodgerblue', linewidth=2, alpha=0.5)
ax.plot(draw_data["Hustnik"][0], draw_data["Hustnik"][1], color='darkgreen', linewidth=1.5, alpha=0.2)
ax.plot(draw_data["Paseky"][0], draw_data["Paseky"][1], color='gold', linewidth=1.5, alpha=0.2)
ax.plot(draw_data["Cesty"][0], draw_data["Cesty"][1], color='gray', linewidth=2, alpha=0.4)

# Vykreslení kontrol
for c in controls:
    ax.plot(c['mx'], c['my'], marker='o', markersize=14, color='magenta', fillstyle='none', markeredgewidth=2, zorder=10)

# =====================================================================
# 3. ZPRACOVÁNÍ ZÁVODNÍKŮ A VYKRESLENÍ
# =====================================================================
if not os.path.exists(slozka_gpx): os.makedirs(slozka_gpx)
gpx_soubory = [f for f in os.listdir(slozka_gpx) if f.endswith('.gpx')]

# Paleta barev pro různé závodníky
barvy = ['red', 'blue', 'purple', 'darkorange', 'brown', 'teal', 'navy', 'crimson']

for idx, soubor in enumerate(gpx_soubory):
    jmeno = soubor.replace('.gpx', '')
    print(f"\n⚙️ Zaměřuji závodníka: {jmeno}")
    
    with open(os.path.join(slozka_gpx, soubor), 'r', encoding='utf-8') as f:
        gpx = gpxpy.parse(f)
    pts = [p for t in gpx.tracks for s in t.segments for p in s.points if p.time]
    
    rx = np.array([(p.longitude - REF_LON) * 111320 * math.cos(math.radians(REF_LAT)) for p in pts])
    ry = np.array([(p.latitude - REF_LAT) * 111320 for p in pts])
    
    # --- BEZPEČNÝ VÝCHOZÍ ODHAD (Zabraňuje pádu optimalizace do nesmyslů) ---
    dist_gps = math.sqrt((rx2 - rx1)**2 + (ry2 - ry1)**2)
    dist_map = math.sqrt((c2['mx'] - c1['mx'])**2 + (c2['my'] - c1['my'])**2)
    init_scale = dist_map / dist_gps
    init_rot = math.degrees(math.atan2(c2['my'] - c1['my'], c2['mx'] - c1['mx']) - math.atan2(ry2 - ry1, rx2 - rx1))
    ca, sa = math.cos(math.radians(init_rot)), math.sin(math.radians(init_rot))
    tx1, ty1 = rx1 * init_scale, ry1 * init_scale
    init_dx = c1['mx'] - (tx1 * ca - ty1 * sa)
    init_dy = c1['my'] - (tx1 * sa + ty1 * ca)

    # --- AUTO-SNAP (OPTIMALIZACE) ---
    def cost_f(params):
        dx, dy, rot, scale = params
        rad = math.radians(rot)
        ca, sa = math.cos(rad), math.sin(rad)
        fx = (rx * scale) * ca - (ry * scale) * sa + dx
        fy = (rx * scale) * sa + (ry * scale) * ca + dy
        # Hledáme polohu, kde součet vzdáleností od VŠECH kontrol k nejbližšímu bodu trasy je minimální
        return np.sum(np.min(cdist(ctrl_coords, np.column_stack((fx, fy))), axis=1)**2)

    print("   ⏳ Přicucávám trasu ke kontrolám...")
    res = minimize(cost_f, [init_dx, init_dy, init_rot, init_scale], method='Nelder-Mead')
    final_dx, final_dy, final_rot, final_scale = res.x
    
    # Výpočet finální křivky
    ca, sa = math.cos(math.radians(final_rot)), math.sin(math.radians(final_rot))
    fx = (rx * final_scale) * ca - (ry * final_scale) * sa + final_dx
    fy = (rx * final_scale) * sa + (ry * final_scale) * ca + final_dy
    
    # Vykreslení trasy závodníka do mapy
    barva = barvy[idx % len(barvy)]
    ax.plot(fx, fy, color=barva, linewidth=1.5, label=jmeno, alpha=0.8)

ax.set_title("Vizuální kontrola všech závodníků (Auto-Snap)")
ax.legend(loc='upper left', framealpha=1.0, fontsize=12)
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