import xml.etree.ElementTree as ET
import gpxpy
import pandas as pd
import math
import numpy as np
import os
import matplotlib.pyplot as plt
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union
from scipy.optimize import minimize
from scipy.spatial.distance import cdist

# --- ⚙️ NASTAVENÍ (Stejné jako v hlavní analytice) ---
omap_file = 'Homolka_Vojirov_20240917.omap'
xml_file = 'Vel.xml'
slozka_gpx = 'vstupy'  

REF_LAT, REF_LON = 49.02982779, 14.9847593
MIN_SEKUND_V_TERENU = 15.0  
SIRKA_CESTY_BUFFER = 2.5    
MAX_TEMPO_CHYBA = 16.0  

# =====================================================================
# 1. NAČTENÍ MAPY 
# =====================================================================
print("🔍 Startuji Diagnostický Rentgen Data-Bodů...")

tree_xml = ET.parse(xml_file)
root_xml = tree_xml.getroot()
ns = {'ns': 'http://www.orienteering.org/datastandard/3.0'}
controls = []
for ctrl in root_xml.findall('.//ns:Control', ns):
    pos = ctrl.find('ns:Position', ns)
    mpos = ctrl.find('ns:MapPosition', ns)
    if pos is not None and mpos is not None:
        controls.append({'lat': float(pos.attrib['lat']), 'lon': float(pos.attrib['lng']), 'mx': float(mpos.attrib['x']), 'my': float(mpos.attrib['y'])})

ctrl_coords = np.array([[c['mx'], c['my']] for c in controls])
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

kategorie = {"Cesta (Zpevnena)": [], "Cesta (Lesni)": [], "Pesina": [], "Prusek": [], "Voda": [], 
             "Paseky": [], "Kamenne pole": [], "Hustnik 1 (Svetly)": [], "Hustnik 2 (Stredni)": [], 
             "Hustnik 3 (Tmave)": [], "Podrost (Srafy)": []}

draw_data = {k: ([], []) for k in kategorie.keys()}

for obj in root.iter():
    if 'object' in obj.tag.lower():
        isom = symbol_map.get(obj.attrib.get('symbol', ""), "").split('.')[0]
        pts, xs, ys = [], [], []
        for child in obj:
            if 'coords' in child.tag.lower() and child.text:
                for p in child.text.strip().split(';'):
                    parts = p.strip().split()
                    if len(parts) >= 2:
                        try: 
                            x, y = float(parts[0])/1000, -float(parts[1])/1000
                            pts.append((x, y))
                            xs.append(x); ys.append(y)
                        except ValueError: pass
                break
        if not pts: continue
        
        if len(pts) >= 2:
            ter_lin = None
            if isom in ['501', '502', '503']: ter_lin = "Cesta (Zpevnena)"
            elif isom == '504': ter_lin = "Cesta (Lesni)"
            elif isom in ['505', '506', '507']: ter_lin = "Pesina"
            elif isom in ['508', '509']: ter_lin = "Prusek"
            if ter_lin: 
                kategorie[ter_lin].append(LineString(pts).buffer(SIRKA_CESTY_BUFFER))
                draw_data[ter_lin][0].extend(xs + [None]); draw_data[ter_lin][1].extend(ys + [None])

        if len(pts) >= 3:
            poly = Polygon(pts)
            if not poly.is_valid: poly = poly.buffer(0)
            ter_pol = None
            if isom in ['403', '404']: ter_pol = "Paseky"
            elif isom == '406': ter_pol = "Hustnik 1 (Svetly)"
            elif isom == '408': ter_pol = "Hustnik 2 (Stredni)"
            elif isom == '410': ter_pol = "Hustnik 3 (Tmave)"
            elif isom in ['407', '409']: ter_pol = "Podrost (Srafy)"
            elif isom in ['208', '209', '210', '211', '212']: ter_pol = "Kamenne pole"
            elif isom.startswith('30'): ter_pol = "Voda"
            if ter_pol: 
                kategorie[ter_pol].append(poly)
                draw_data[ter_pol][0].extend(xs + [None]); draw_data[ter_pol][1].extend(ys + [None])

merged_geom = {k: unary_union(v) if v else Polygon() for k, v in kategorie.items()}

# =====================================================================
# 2. DIAGNOSTIKA ZÁVODNÍKŮ (POSTUPNÉ OTEVÍRÁNÍ)
# =====================================================================
gpx_soubory = [f for f in os.listdir(slozka_gpx) if f.endswith('.gpx')]

# Definice jasných barev pro terény
barvy_terenu = {
    'Bily les': 'cyan', 
    'Cesta (Zpevnena)': 'black',
    'Cesta (Lesni)': 'fuchsia',
    'Pesina': 'blue',
    'Prusek': 'silver',
    'Hustnik 1 (Svetly)': 'lime',
    'Hustnik 2 (Stredni)': 'forestgreen',
    'Hustnik 3 (Tmave)': 'darkgreen',
    'Podrost (Srafy)': 'olive',
    'Kamenne pole': 'red',
    'Paseky': 'orange',
    'Voda': 'blue'
}

for soubor in gpx_soubory:
    jmeno = soubor.replace('.gpx', '').upper()
    print(f"\n🏃 Diagnostikuji: {jmeno}")
    
    with open(os.path.join(slozka_gpx, soubor), 'r', encoding='utf-8') as f:
        gpx = gpxpy.parse(f)
    pts = [p for t in gpx.tracks for s in t.segments for p in s.points if p.time]
    
    rx = np.array([(p.longitude - REF_LON) * 111320 * math.cos(math.radians(REF_LAT)) for p in pts])
    ry = np.array([(p.latitude - REF_LAT) * 111320 for p in pts])

    # Auto-Snap
    dist_gps = math.sqrt((rx2 - rx1)**2 + (ry2 - ry1)**2)
    dist_map = math.sqrt((c2['mx'] - c1['mx'])**2 + (c2['my'] - c1['my'])**2)
    init_scale = dist_map / dist_gps
    init_rot = math.degrees(math.atan2(c2['my'] - c1['my'], c2['mx'] - c1['mx']) - math.atan2(ry2 - ry1, rx2 - rx1))
    ca, sa = math.cos(math.radians(init_rot)), math.sin(math.radians(init_rot))
    tx1, ty1 = rx1 * init_scale, ry1 * init_scale
    init_dx = c1['mx'] - (tx1 * ca - ty1 * sa)
    init_dy = c1['my'] - (tx1 * sa + ty1 * ca)

    def cost_f(params):
        dx, dy, rot, scale = params
        ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        fx = (rx * scale) * ca - (ry * scale) * sa + dx
        fy = (rx * scale) * sa + (ry * scale) * ca + dy
        return np.sum(np.min(cdist(ctrl_coords, np.column_stack((fx, fy))), axis=1)**2)

    res = minimize(cost_f, [init_dx, init_dy, init_rot, init_scale], method='Nelder-Mead')
    final_dx, final_dy, final_rot, final_scale = res.x
    ca, sa = math.cos(math.radians(final_rot)), math.sin(math.radians(final_rot))

    # Získání finálních souřadnic celé trasy
    all_fx = (rx * final_scale) * ca - (ry * final_scale) * sa + final_dx
    all_fy = (rx * final_scale) * sa + (ry * final_scale) * ca + final_dy

    # --- FILTRACE DAT ---
    data_body = []
    for i in range(1, len(pts)):
        fx, fy = all_fx[i], all_fy[i]
        mp = Point(fx, fy)
        
        t = "Bily les"
        for k, poly in merged_geom.items():
            if poly.contains(mp): t = k; break
        
        dt = (pts[i].time - pts[i-1].time).total_seconds()
        ds = pts[i-1].distance_2d(pts[i])
        
        if dt > 0 and ds > 0:
            data_body.append({'Teren': t, 'dt': dt, 'ds': ds, 'x': fx, 'y': fy})

    if not data_body: continue
    df = pd.DataFrame(data_body)
    df['Block_ID'] = (df['Teren'] != df['Teren'].shift(1)).cumsum()
    
    povolene_body = []
    zahozeno_casem = 0
    zahozeno_chybou = 0

    for bid, group in df.groupby('Block_ID'):
        # Filtr 1: Minimální čas v terénu
        if group['dt'].sum() < MIN_SEKUND_V_TERENU: 
            zahozeno_casem += len(group)
            continue
        
        for _, r in group.iterrows():
            tempo = (1000 / (r['ds'] / r['dt'])) / 60
            
            # Filtr 2: Dohledávky a zmatení
            if 2.0 < tempo < MAX_TEMPO_CHYBA:
                povolene_body.append(r)
            else:
                zahozeno_chybou += 1

    df_povoleno = pd.DataFrame(povolene_body)
    pocet_povoleno = len(df_povoleno) if not df_povoleno.empty else 0

    print(f"   -> Uznáno bodů do analytiky: {pocet_povoleno}")
    print(f"   -> Zahozeno (krátký úsek): {zahozeno_casem} | Zahozeno (dohledávka/chůze): {zahozeno_chybou}")

    # --- VYKRESLENÍ DIAGNOSTIKY PRO JEDNOHO ZÁVODNÍKA ---
    fig, ax = plt.subplots(figsize=(14, 10))
    fig.canvas.manager.set_window_title(f'DIAGNOSTIKA: {jmeno} (ZAVŘI KŘÍŽKEM PRO DALŠÍHO)')

    # Vykreslení mapy
    ax.plot(draw_data["Voda"][0], draw_data["Voda"][1], color='dodgerblue', linewidth=2, alpha=0.5)
    ax.plot(draw_data["Hustnik 3 (Tmave)"][0], draw_data["Hustnik 3 (Tmave)"][1], color='darkgreen', linewidth=1.5, alpha=0.3)
    ax.plot(draw_data["Paseky"][0], draw_data["Paseky"][1], color='gold', linewidth=1.5, alpha=0.2)
    ax.plot(draw_data["Cesta (Zpevnena)"][0], draw_data["Cesta (Zpevnena)"][1], color='black', linewidth=3, alpha=0.4)
    ax.plot(draw_data["Cesta (Lesni)"][0], draw_data["Cesta (Lesni)"][1], color='dimgray', linewidth=2, alpha=0.4)
    for c in controls: ax.plot(c['mx'], c['my'], marker='o', markersize=14, color='magenta', fillstyle='none')

    # Tenká šedá čára ukazuje celou původní trasu (i se smazanými body)
    ax.plot(all_fx, all_fy, color='black', linewidth=0.5, alpha=0.3, label="Zahozená/Původní trasa")

    # Vykreslení obarvených bodů, které přežily filtr
    if not df_povoleno.empty:
        for ter, color in barvy_terenu.items():
            subset = df_povoleno[df_povoleno['Teren'] == ter]
            if not subset.empty:
                ax.scatter(subset['x'], subset['y'], c=color, label=ter, s=25, edgecolors='none', zorder=5)

    ax.set_title(f"Závodník: {jmeno} | Platných bodů: {pocet_povoleno} | Zahozeno kvůli dohledávce/chůzi: {zahozeno_chybou}\n(Až zkontroluješ, ZAVŘI OKNO a ukáže se další)")
    ax.legend(loc='upper left', framealpha=1.0)
    ax.axis('equal'); ax.grid(True, linestyle=':', alpha=0.6)

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
    
    plt.show()  # Zastaví a čeká na zavření

print("\n✅ Všichni závodníci byli diagnostikováni!")