import xml.etree.ElementTree as ET
import gpxpy
import pandas as pd
import math
import numpy as np
import os
import argparse
from datetime import datetime
import matplotlib.pyplot as plt
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union
from scipy.optimize import minimize
from scipy.spatial.distance import cdist

# --- ⚙️ NASTAVENÍ ---
omap_file = 'Homolka_Vojirov_20240917.omap'
xml_file = 'Vel.xml'
slozka_gpx = 'vstupy'  # 👈 Zpět na tvoji složku s GPX!

REF_LAT, REF_LON = 49.02982779, 14.9847593
EKVIDISTANCE_M = 5.0
MIN_SEKUND_V_TERENU = 0.2  
SIRKA_CESTY_BUFFER = 1.7
LINIE_ALIGN_MAX_UHEL_STUPNE = 45.0
LINIE_TANGENTA_DELKA_M = 0.8
MAX_TEMPO_CHYBA = 16.0  
MIN_BODU_PRO_LESNI_REFERENCI = 25
MIN_BODU_PRO_REF_TEREN = 20
MIN_BODU_PRO_KOMBINOVANOU_REFERENCI = 40
RYCHLE_REF_TERENY = ["Cesta (Lesni)", "Pesina", "Cesta (Zpevnena)"]
OCEKAVANE_PORADI_TERENU = [
    "Cesta (Zpevnena)", "Cesta (Lesni)", "Pesina", "Prusek", "Paseky",
    "Bily les", "Hustnik 1 (Svetly)", "Podrost (Srafy)", "Hustnik 2 (Stredni)", "Hustnik 3 (Tmave)"
]
POUZIT_STRIKTNI_FILTR_PORADI = True
MIN_BODU_PRO_STRIKTNI_TEREN = 8

parser = argparse.ArgumentParser(
    description="Plne automatizovana tymova analytika orientacniho behu."
)
parser.add_argument(
    "--diag",
    choices=["ano", "ne"],
    help="Zapnout diagnosticke mapy (ano/ne). Pokud neni zadano, zepta se skript interaktivne."
)
args = parser.parse_args()

if args.diag is None:
    odpoved_diagnostika = input(
        "Chceš zobrazit diagnostické trasy závodníků? (ano/ne): "
    ).strip().lower()
    ZOBRAZIT_DIAGNOSTIKU_ZAVODNIKU = odpoved_diagnostika in {"a", "ano", "y", "yes"}
else:
    ZOBRAZIT_DIAGNOSTIKU_ZAVODNIKU = args.diag == "ano"

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

barvy_terenu = {
    'Bily les': 'cyan', 'Cesta (Zpevnena)': 'black', 'Cesta (Lesni)': 'fuchsia',
    'Pesina': 'blue', 'Prusek': 'silver', 'Hustnik 1 (Svetly)': 'lime',
    'Hustnik 2 (Stredni)': 'forestgreen', 'Hustnik 3 (Tmave)': 'darkgreen',
    'Podrost (Srafy)': 'olive', 'Kamenne pole': 'red', 'Paseky': 'orange',
    'Voda': 'blue', 'Bazina': 'deepskyblue'
}

# =====================================================================
# 1. NAČTENÍ SPOLEČNÝCH DAT (MAPA + KONTROLY)
# =====================================================================
print("🚀 Startuji Plně Automatizovanou Týmovou Analytiku s Gumováním...")

tree_xml = ET.parse(xml_file)
root_xml = tree_xml.getroot()
ns = {'ns': 'http://www.orienteering.org/datastandard/3.0'}
controls = []
for ctrl in root_xml.findall('.//ns:Control', ns):
    pos = ctrl.find('ns:Position', ns)
    mpos = ctrl.find('ns:MapPosition', ns)
    if pos is not None and mpos is not None:
        controls.append({'lat': float(pos.attrib['lat']), 'lon': float(pos.attrib['lng']), 
                         'mx': float(mpos.attrib['x']), 'my': float(mpos.attrib['y'])})

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

kategorie = {"Cesta (Zpevnena)": [], "Cesta (Lesni)": [], "Pesina": [], "Prusek": [], "Voda": [], "Bazina": [],
             "Paseky": [], "Kamenne pole": [], "Hustnik 1 (Svetly)": [], "Hustnik 2 (Stredni)": [], 
             "Hustnik 3 (Tmave)": [], "Podrost (Srafy)": [], "Vrstevnice": []}
linearni_tereny = ["Cesta (Zpevnena)", "Cesta (Lesni)", "Pesina", "Prusek"]
linie_osy = {k: [] for k in linearni_tereny}

draw_data = {k: ([], []) for k in kategorie.keys() if k != "Vrstevnice"}

print("🗺️ Zpracovávám mapový podklad (ISOM kódy a vrstevnice)...")
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
            if isom in ['101', '102', '103']: kategorie["Vrstevnice"].append(LineString(pts))
            else:
                ter_lin = None
                if isom in ['501', '502', '503']: ter_lin = "Cesta (Zpevnena)"
                elif isom == '504': ter_lin = "Cesta (Lesni)"
                elif isom in ['505', '506', '507']: ter_lin = "Pesina"
                elif isom in ['508', '509']: ter_lin = "Prusek"
                elif isom == '309': ter_lin = "Bazina"  # Uzká bažina (liniový symbol)
                if ter_lin: 
                    osa = LineString(pts)
                    kategorie[ter_lin].append(osa.buffer(SIRKA_CESTY_BUFFER))
                    if ter_lin in linie_osy:
                        linie_osy[ter_lin].append(osa)
                    draw_data[ter_lin][0].extend(xs + [None])
                    draw_data[ter_lin][1].extend(ys + [None])

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
            elif isom in ['307', '308', '310']: ter_pol = "Bazina"
            elif isom.startswith('30'): ter_pol = "Voda"
            if ter_pol: 
                kategorie[ter_pol].append(poly)
                draw_data[ter_pol][0].extend(xs + [None])
                draw_data[ter_pol][1].extend(ys + [None])

merged_geom = {k: unary_union(v) if v else Polygon() for k, v in kategorie.items() if k != "Vrstevnice"}
vrstevnice_sit = unary_union(kategorie["Vrstevnice"]) if kategorie["Vrstevnice"] else LineString()
MIN_COS_UHEL_LINIE = math.cos(math.radians(LINIE_ALIGN_MAX_UHEL_STUPNE))

def je_pohyb_podel_linie(px, py, vx, vy, terrain):
    if terrain not in linie_osy or not linie_osy[terrain]:
        return False

    move_norm = math.hypot(vx, vy)
    if move_norm < 1e-6:
        return False

    bod = Point(px, py)
    best_cos = -1.0

    for linie in linie_osy[terrain]:
        if bod.distance(linie) > SIRKA_CESTY_BUFFER * 1.4:
            continue

        proj = linie.project(bod)
        p_a = linie.interpolate(max(0.0, proj - LINIE_TANGENTA_DELKA_M))
        p_b = linie.interpolate(min(linie.length, proj + LINIE_TANGENTA_DELKA_M))
        tx = p_b.x - p_a.x
        ty = p_b.y - p_a.y
        tan_norm = math.hypot(tx, ty)
        if tan_norm < 1e-6:
            continue

        cos_uhel = abs((vx * tx + vy * ty) / (move_norm * tan_norm))
        if cos_uhel > best_cos:
            best_cos = cos_uhel

    return best_cos >= MIN_COS_UHEL_LINIE

def isotonic_increasing(values, weights):
    blocks = []
    for v, w in zip(values, weights):
        blocks.append({'sum_w': float(w), 'sum_vw': float(v) * float(w), 'count': 1})
        while len(blocks) >= 2:
            prev = blocks[-2]['sum_vw'] / blocks[-2]['sum_w']
            curr = blocks[-1]['sum_vw'] / blocks[-1]['sum_w']
            if prev <= curr:
                break
            b = blocks.pop()
            a = blocks.pop()
            blocks.append({
                'sum_w': a['sum_w'] + b['sum_w'],
                'sum_vw': a['sum_vw'] + b['sum_vw'],
                'count': a['count'] + b['count']
            })

    out = []
    for b in blocks:
        val = b['sum_vw'] / b['sum_w']
        out.extend([val] * b['count'])
    return out

def koriguj_summary_podle_poradi(summary, counts):
    dostupne = [t for t in OCEKAVANE_PORADI_TERENU if t in summary.index and counts.get(t, 0) > 0]
    if len(dostupne) < 2:
        return summary.copy(), 0

    raw_vals = [float(summary[t]) for t in dostupne]
    raw_w = [float(max(1, counts.get(t, 1))) for t in dostupne]
    iso_vals = isotonic_increasing(raw_vals, raw_w)
    poruseni = sum(1 for i in range(len(raw_vals) - 1) if raw_vals[i] > raw_vals[i + 1])

    corrected = summary.copy()
    for t, v in zip(dostupne, iso_vals):
        corrected.loc[t] = v
    return corrected, poruseni

def vyber_validni_tereny_striktne(summary, counts):
    validni = [t for t in OCEKAVANE_PORADI_TERENU if t in summary.index and counts.get(t, 0) >= MIN_BODU_PRO_STRIKTNI_TEREN]
    odebrane = []
    if len(validni) < 2:
        return set(validni), odebrane

    while True:
        poruseni = []
        for i in range(len(validni) - 1):
            t_a = validni[i]
            t_b = validni[i + 1]
            if float(summary[t_a]) > float(summary[t_b]):
                poruseni.append((t_a, t_b))

        if not poruseni:
            break

        t_a, t_b = poruseni[0]
        # Striktní pravidlo: z porušující dvojice odstraníme méně robustní terén.
        kandidat_drop = t_a if counts.get(t_a, 0) <= counts.get(t_b, 0) else t_b
        validni.remove(kandidat_drop)
        odebrane.append(kandidat_drop)

        if len(validni) < 2:
            break

    return set(validni), odebrane

# =====================================================================
# 2. AUTOMATICKÉ ZPRACOVÁNÍ ZÁVODNÍKŮ (GPX)
# =====================================================================
vysledky_tym = {}
vizualizace_zavodniku = {} 
tymove_spolehlive_ref = []

if not os.path.exists(slozka_gpx): os.makedirs(slozka_gpx)
gpx_soubory = [f for f in os.listdir(slozka_gpx) if f.endswith('.gpx')]

if not gpx_soubory:
    print(f"⚠️ Ve složce '{slozka_gpx}' nejsou žádné .gpx soubory!")
    exit()

for soubor in gpx_soubory:
    jmeno = soubor.replace('.gpx', '').upper()
    print(f"\n🏃 Analyzuji: {jmeno}")
    
    with open(os.path.join(slozka_gpx, soubor), 'r', encoding='utf-8') as f:
        gpx = gpxpy.parse(f)
    pts = [p for t in gpx.tracks for s in t.segments for p in s.points if p.time]
    
    rx = np.array([(p.longitude - REF_LON) * 111320 * math.cos(math.radians(REF_LAT)) for p in pts])
    ry = np.array([(p.latitude - REF_LAT) * 111320 for p in pts])

    # --- KROK A: HRUBÝ AUTO-SNAP (Měřítko a otočení) ---
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
        rad = math.radians(rot)
        ca, sa = math.cos(rad), math.sin(rad)
        fx = (rx * scale) * ca - (ry * scale) * sa + dx
        fy = (rx * scale) * sa + (ry * scale) * ca + dy
        return np.sum(np.min(cdist(ctrl_coords, np.column_stack((fx, fy))), axis=1)**2)

    res = minimize(cost_f, [init_dx, init_dy, init_rot, init_scale], method='Nelder-Mead')
    final_dx, final_dy, final_rot, final_scale = res.x
    ca, sa = math.cos(math.radians(final_rot)), math.sin(math.radians(final_rot))

    base_fx = (rx * final_scale) * ca - (ry * final_scale) * sa + final_dx
    base_fy = (rx * final_scale) * sa + (ry * final_scale) * ca + final_dy

    # --- KROK B: LOKÁLNÍ GUMOVÁNÍ (Přicucnutí přímo na kontroly) ---
    track_x = np.copy(base_fx)
    track_y = np.copy(base_fy)
    
    pins = []
    for c in controls:
        cx, cy = c['mx'], c['my']
        dists = np.hypot(track_x - cx, track_y - cy)
        min_idx = np.argmin(dists)
        if dists[min_idx] < 80.0:  # Snapne, pokud je to blíž než 80m
            pins.append((min_idx, cx, cy))
            
    pins.sort(key=lambda p: p[0])
    
    unique_pins = []
    for p in pins:
        if not unique_pins or unique_pins[-1][0] != p[0]:
            unique_pins.append(p)
    pins = unique_pins

    new_x = np.copy(track_x)
    new_y = np.copy(track_y)

    if len(pins) >= 2:
        print(f"   🧲 Gumičkou přišpendleno k {len(pins)} kontrolám...")
        
        idx0, cx0, cy0 = pins[0]
        off_x0 = cx0 - track_x[idx0]
        off_y0 = cy0 - track_y[idx0]
        for i in range(0, idx0):
            new_x[i] += off_x0
            new_y[i] += off_y0

        for i in range(len(pins) - 1):
            idxA, cxA, cyA = pins[i]
            idxB, cxB, cyB = pins[i+1]
            
            off_xA = cxA - track_x[idxA]
            off_yA = cyA - track_y[idxA]
            off_xB = cxB - track_x[idxB]
            off_yB = cyB - track_y[idxB]
            
            for j in range(idxA, idxB + 1):
                if idxB == idxA: t = 0
                else: t = (j - idxA) / (idxB - idxA)
                new_x[j] = track_x[j] + off_xA * (1 - t) + off_xB * t
                new_y[j] = track_y[j] + off_yA * (1 - t) + off_yB * t

        idx_last, cx_last, cy_last = pins[-1]
        off_x_last = cx_last - track_x[idx_last]
        off_y_last = cy_last - track_y[idx_last]
        for i in range(idx_last + 1, len(track_x)):
            new_x[i] += off_x_last
            new_y[i] += off_y_last

    all_fx = new_x
    all_fy = new_y

    # --- KROK C: EXTRAKCE DAT TERÉNU A FILTRACE ---
    data_body = []
    for i in range(1, len(pts)):
        fx, fy = all_fx[i], all_fy[i]
        vx = all_fx[i] - all_fx[i-1]
        vy = all_fy[i] - all_fy[i-1]
        mp = Point(fx, fy)
        
        t = "Bily les"
        if merged_geom["Cesta (Zpevnena)"].contains(mp) and je_pohyb_podel_linie(fx, fy, vx, vy, "Cesta (Zpevnena)"):
            t = "Cesta (Zpevnena)"
        elif merged_geom["Cesta (Lesni)"].contains(mp) and je_pohyb_podel_linie(fx, fy, vx, vy, "Cesta (Lesni)"):
            t = "Cesta (Lesni)"
        elif merged_geom["Pesina"].contains(mp) and je_pohyb_podel_linie(fx, fy, vx, vy, "Pesina"):
            t = "Pesina"
        elif merged_geom["Prusek"].contains(mp) and je_pohyb_podel_linie(fx, fy, vx, vy, "Prusek"):
            t = "Prusek"
        elif merged_geom["Bazina"].contains(mp): t = "Bazina"
        elif merged_geom["Voda"].contains(mp): t = "Voda"
        elif merged_geom["Kamenne pole"].contains(mp): t = "Kamenne pole"
        elif merged_geom["Hustnik 3 (Tmave)"].contains(mp): t = "Hustnik 3 (Tmave)"
        elif merged_geom["Hustnik 2 (Stredni)"].contains(mp): t = "Hustnik 2 (Stredni)"
        elif merged_geom["Hustnik 1 (Svetly)"].contains(mp): t = "Hustnik 1 (Svetly)"
        elif merged_geom["Podrost (Srafy)"].contains(mp): t = "Podrost (Srafy)"
        elif merged_geom["Paseky"].contains(mp): t = "Paseky"
        
        dt = (pts[i].time - pts[i-1].time).total_seconds()
        ds = pts[i-1].distance_2d(pts[i])
        
        if dt > 0 and ds > 0:
            data_body.append({'Teren': t, 'dt': dt, 'ds': ds, 'x': fx, 'y': fy})

    if not data_body: continue
    df = pd.DataFrame(data_body)
    df['Block_ID'] = (df['Teren'] != df['Teren'].shift(1)).cumsum()
    
    final_rows = []
    zahozene_chyby = 0

    for bid, group in df.groupby('Block_ID'):
        if group['dt'].sum() < MIN_SEKUND_V_TERENU: continue
        
        prevyseni = 0
        if len(group) >= 2:
            line = LineString(list(zip(group['x'], group['y'])))
            pruseciky = line.intersection(vrstevnice_sit)
            if pruseciky.geom_type == 'Point': prevyseni = EKVIDISTANCE_M
            elif pruseciky.geom_type == 'MultiPoint': prevyseni = len(pruseciky.geoms) * EKVIDISTANCE_M
        
        sklon = (prevyseni / group['ds'].sum() * 100) if group['ds'].sum() > 0 else 0
        
        for _, r in group.iterrows():
            tempo = (1000 / (r['ds'] / r['dt'])) / 60
            if 2.0 < tempo < MAX_TEMPO_CHYBA:
                final_rows.append({'Teren': r['Teren'], 'Tempo': tempo, 'Sklon': sklon, 'x': r['x'], 'y': r['y']})
            elif tempo >= MAX_TEMPO_CHYBA:
                zahozene_chyby += 1

    print(f"   🧹 Odfiltrováno {zahozene_chyby} bodů (dohledávky, chůze).")

    if not final_rows: continue
    df_res = pd.DataFrame(final_rows)
    
    vizualizace_zavodniku[jmeno] = {'fx': all_fx, 'fy': all_fy, 'df': df_res}
    
    rovina = df_res[df_res['Sklon'] < 2.5].groupby('Teren')['Tempo'].median()
    gap_vals = []
    for _, r in df_res.iterrows():
        ref = rovina.get(r['Teren'], r['Tempo'])
        if r['Sklon'] < 2.5:
            gap_vals.append(r['Tempo'])
        elif r['Tempo'] > ref: gap_vals.append(r['Tempo'] / (1 + (r['Sklon'] * 0.04)))
        else: gap_vals.append(r['Tempo'] * (1 + (r['Sklon'] * 0.02)))
            
    df_res['GAP'] = gap_vals
    summary = df_res.groupby('Teren')['GAP'].median()
    counts = df_res.groupby('Teren')['GAP'].size()

    if POUZIT_STRIKTNI_FILTR_PORADI:
        validni_tereny, odebrane_tereny = vyber_validni_tereny_striktne(summary, counts)
        if validni_tereny:
            df_res = df_res[df_res['Teren'].isin(validni_tereny) | ~df_res['Teren'].isin(OCEKAVANE_PORADI_TERENU)].copy()
            if odebrane_tereny:
                unikatni_odebrane = list(dict.fromkeys(odebrane_tereny))
                print(f"   🚧 Striktní filtr pořadí: vyřazeno {', '.join(unikatni_odebrane)}")
            summary = df_res.groupby('Teren')['GAP'].median()
            counts = df_res.groupby('Teren')['GAP'].size()
        else:
            print("   🚧 Striktní filtr pořadí: nedostatek robustních terénů, filtr přeskočen.")

    summary_korig, poruseni_poradi = koriguj_summary_podle_poradi(summary, counts)
    summary_pro_ref = summary_korig if poruseni_poradi > 0 else summary

    # Robustní reference: preferuj lesní cestu jen při dostatku dat.
    if counts.get("Cesta (Lesni)", 0) >= MIN_BODU_PRO_LESNI_REFERENCI:
        base = summary_pro_ref["Cesta (Lesni)"]
        reference_info = f"Cesta (Lesni), n={int(counts.get('Cesta (Lesni)', 0))}"
        tymove_spolehlive_ref.append(float(base))
    else:
        dostupne_ref = [t for t in RYCHLE_REF_TERENY if t in summary_pro_ref and counts.get(t, 0) >= MIN_BODU_PRO_REF_TEREN]
        total_ref_bodu = int(sum(counts.get(t, 0) for t in dostupne_ref))

        if dostupne_ref and total_ref_bodu >= MIN_BODU_PRO_KOMBINOVANOU_REFERENCI:
            vahy = np.array([counts[t] for t in dostupne_ref], dtype=float)
            hodnoty = np.array([summary_pro_ref[t] for t in dostupne_ref], dtype=float)
            base = float(np.average(hodnoty, weights=vahy))
            reference_info = f"Kombinace {', '.join(dostupne_ref)}, n={total_ref_bodu}"
            tymove_spolehlive_ref.append(float(base))
        elif tymove_spolehlive_ref:
            base = float(np.median(tymove_spolehlive_ref))
            reference_info = f"Tymovy fallback (median spolehlivych referenci), n={len(tymove_spolehlive_ref)}"
        elif counts.get("Pesina", 0) >= MIN_BODU_PRO_REF_TEREN:
            base = summary_pro_ref["Pesina"]
            reference_info = f"Pesina, n={int(counts.get('Pesina', 0))}"
        elif counts.get("Cesta (Zpevnena)", 0) >= MIN_BODU_PRO_REF_TEREN:
            base = summary_pro_ref["Cesta (Zpevnena)"]
            reference_info = f"Cesta (Zpevnena), n={int(counts.get('Cesta (Zpevnena)', 0))}"
        elif "Bily les" in summary_pro_ref:
            base = summary_pro_ref["Bily les"] * 0.85
            reference_info = f"Bily les*0.85, n={int(counts.get('Bily les', 0))}"
        else:
            base = float(summary_pro_ref.min())
            reference_info = "minimum dostupnych terenů"

    if poruseni_poradi > 0:
        print(f"   🔧 Pořadí terénů: korigováno {poruseni_poradi} porušení (pouze pro výpočet reference).")

    print(f"   📐 Reference GAP: {reference_info} -> {base:.2f}")
        
    vysledky_tym[jmeno] = (summary / base).round(2)

# =====================================================================
# 3. POSTUPNÁ VIZUÁLNÍ KONTROLA ZÁVODNÍKŮ
# =====================================================================
if ZOBRAZIT_DIAGNOSTIKU_ZAVODNIKU:
    print("\n👀 Otevírám postupnou vizuální kontrolu.")
    print("   -> Zazoomuj a ověř, že nagumovaná trasa sedí na kontrolách.")
    print("   -> ❌ ZAVŘI OKNO (křížkem) pro zobrazení dalšího závodníka!")

    for jmeno, data_zavodnika in vizualizace_zavodniku.items():
        fig, ax = plt.subplots(figsize=(16, 10))
        fig.canvas.manager.set_window_title(f'🔎 DIAGNOSTIKA: {jmeno} (ZAVŘI KŘÍŽKEM PRO DALŠÍHO)')

        # Vykreslení podkladu
        ax.plot(draw_data["Voda"][0], draw_data["Voda"][1], color='dodgerblue', linewidth=2, alpha=0.5)
        ax.plot(draw_data["Hustnik 3 (Tmave)"][0], draw_data["Hustnik 3 (Tmave)"][1], color='darkgreen', linewidth=1.5, alpha=0.3)
        ax.plot(draw_data["Paseky"][0], draw_data["Paseky"][1], color='gold', linewidth=1.5, alpha=0.2)
        ax.plot(draw_data["Cesta (Zpevnena)"][0], draw_data["Cesta (Zpevnena)"][1], color='black', linewidth=3, alpha=0.4)
        ax.plot(draw_data["Cesta (Lesni)"][0], draw_data["Cesta (Lesni)"][1], color='dimgray', linewidth=2, alpha=0.4)
        
        for c in controls: 
            ax.plot(c['mx'], c['my'], marker='o', markersize=14, color='magenta', fillstyle='none', markeredgewidth=2)

        # Celá nagumovaná trasa jako tenká šedá čára
        ax.plot(data_zavodnika['fx'], data_zavodnika['fy'], color='black', linewidth=0.5, alpha=0.3, label="Nagumovaná celá trasa")

        # Barevné tečky terénů
        df_plot = data_zavodnika['df']
        for ter, color in barvy_terenu.items():
            subset = df_plot[df_plot['Teren'] == ter]
            if not subset.empty:
                ax.scatter(subset['x'], subset['y'], c=color, label=ter, s=25, edgecolors='none', zorder=5)

        ax.set_title(f"Závodník: {jmeno}\n❌ Až zkontroluješ tečky a napnutí kontrol, ZAVŘI OKNO pro pokračování!")
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

# =====================================================================
# 4. FINÁLNÍ VÝPIS TABULKY
# =====================================================================
print("\n" + "="*80)
print("🏆 CELKOVÁ TÝMOVÁ ANALÝZA RELATIVNÍCH RYCHLOSTÍ")
print("   Základ (1.00x) = Cesta (Lesni) s odfiltrovaným převýšením (GAP)")
print("="*80)

df_tabulka = pd.DataFrame(vysledky_tym)

if not df_tabulka.empty:
    # Anonymizace: místo jmen/GPX názvů použij číselné sloupce.
    df_tabulka.columns = [str(i) for i in range(1, len(df_tabulka.columns) + 1)]
    df_tabulka['CELKOVÝ PRŮMĚR'] = df_tabulka.mean(axis=1).round(2)
    df_tabulka = df_tabulka.sort_values(by='CELKOVÝ PRŮMĚR')

    excel_tabulka = df_tabulka.round(2).copy()
    excel_tabulka.index.name = "TERÉN"
    cas = datetime.now().strftime("%Y%m%d_%H%M%S")
    vystup_xlsx = f"vystup_tymova_analytika_{cas}.xlsx"
    vystup_csv = f"vystup_tymova_analytika_{cas}.csv"

    # Vždy ukládáme do nového souboru s časovým razítkem.
    try:
        excel_tabulka.to_excel(vystup_xlsx, sheet_name="Tymova analytika")
        print(f"💾 Excel soubor uložen: {vystup_xlsx}")
    except ModuleNotFoundError:
        excel_tabulka.to_csv(vystup_csv, sep=';', decimal=',', encoding='utf-8-sig')
        print("⚠️ Chybí balíček openpyxl pro .xlsx export.")
        print(f"💾 Uložen náhradní Excel-kompatibilní CSV: {vystup_csv}")
        print("   Tip: pro .xlsx spusť `pip install openpyxl`.")

    print("📋 Přehled v konzoli:")
    print(excel_tabulka.to_string())
    print("="*80 + "\n")
else:
    print("Nepodařilo se zpracovat žádná data.")