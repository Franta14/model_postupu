import xml.etree.ElementTree as ET
import pandas as pd
import math
import matplotlib.pyplot as plt
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union

# --- ⚙️ TVOJE ANALYTICKÁ PRAVIDLA ---
omap_file = 'Homolka_Vojirov_20240917.omap'
vstupni_trasa = 'nakalibrovana_trasa.csv'

SIRKA_CESTY_BUFFER = 0.2
MIN_SEKUND_V_TERENU = 5.0  
ZAHODIT_PRVNICH_MINUT = 13.0  
ZAHODIT_POSLEDNICH_MINUT = 0.0 
EKVIDISTANCE_M = 5.0  

print("1. Načítám mapu (Terény + Vrstevnice)...")
tree = ET.parse(omap_file)
root = tree.getroot()
symbol_map = {elem.attrib.get('id'): elem.attrib.get('code') for elem in root.iter() if 'symbol' in elem.tag.lower()}

kategorie = {
    "Cesta (Zpevnena)": [], "Cesta (Lesni)": [], "Pesina": [], "Prusek": [],               
    "Voda": [], "Paseky": [], "Kamenne pole": [],                 
    "Hustnik 1 (Svetly)": [], "Hustnik 2 (Stredni)": [], "Hustnik 3 (Tmave)": [],            
    "Podrost (Srafy)": [], "Vrstevnice": []
}
draw_data = {k: ([], []) for k in kategorie.keys() if k != "Vrstevnice"}

for obj in root.iter():
    if 'object' in obj.tag.lower():
        sym_id = obj.attrib.get('symbol')
        if not sym_id: continue
        isom = symbol_map.get(sym_id, "")
        if not isom: continue
        
        isom_cat = isom.split('.')[0] 
        pts, xs, ys = [], [], []
        for child in obj:
            if 'coords' in child.tag.lower() and child.text:
                for p in child.text.strip().split(';'):
                    parts = p.strip().split()
                    if len(parts) >= 2:
                        try:
                            x, y = float(parts[0]) / 1000, -float(parts[1]) / 1000
                            pts.append((x, y))
                            xs.append(x); ys.append(y)
                        except ValueError: pass
                break
        if not pts: continue

        if len(pts) >= 2:
            if isom_cat in ['101', '102', '103']: kategorie["Vrstevnice"].append(LineString(pts))
            else:
                ter_lin = None
                if isom_cat in ['501', '502', '503']: ter_lin = "Cesta (Zpevnena)"
                elif isom_cat == '504': ter_lin = "Cesta (Lesni)"
                elif isom_cat in ['505', '506', '507']: ter_lin = "Pesina"
                elif isom_cat in ['508', '509']: ter_lin = "Prusek"
                if ter_lin:
                    kategorie[ter_lin].append(LineString(pts).buffer(SIRKA_CESTY_BUFFER))
                    draw_data[ter_lin][0].extend(xs + [None]); draw_data[ter_lin][1].extend(ys + [None])

        if len(pts) >= 3:
            poly = Polygon(pts)
            if not poly.is_valid: poly = poly.buffer(0)
            ter_pol = None
            if isom_cat in ['403', '404']: ter_pol = "Paseky"
            elif isom_cat == '406': ter_pol = "Hustnik 1 (Svetly)"
            elif isom_cat == '408': ter_pol = "Hustnik 2 (Stredni)"
            elif isom_cat == '410': ter_pol = "Hustnik 3 (Tmave)"
            elif isom_cat in ['407', '409']: ter_pol = "Podrost (Srafy)"
            elif isom_cat in ['208', '209', '210', '211', '212']: ter_pol = "Kamenne pole"
            elif isom_cat.startswith('30'): ter_pol = "Voda"
            if ter_pol:
                kategorie[ter_pol].append(poly)
                draw_data[ter_pol][0].extend(xs + [None]); draw_data[ter_pol][1].extend(ys + [None])

merged_geom = {k: unary_union(v) if v else Polygon() for k, v in kategorie.items() if k != "Vrstevnice"}
vrstevnice_sit = unary_union(kategorie["Vrstevnice"]) if kategorie["Vrstevnice"] else LineString()

print("2. Čtu trasu z CSV...")
try: df_trasa = pd.read_csv(vstupni_trasa)
except FileNotFoundError: exit()

df_trasa['Time'] = pd.to_datetime(df_trasa['Time']) 
if len(df_trasa) > 0 and (ZAHODIT_PRVNICH_MINUT > 0 or ZAHODIT_POSLEDNICH_MINUT > 0):
    df_trasa = df_trasa[(df_trasa['Time'] >= df_trasa['Time'].iloc[0] + pd.Timedelta(minutes=ZAHODIT_PRVNICH_MINUT)) & 
                        (df_trasa['Time'] <= df_trasa['Time'].iloc[-1] - pd.Timedelta(minutes=ZAHODIT_POSLEDNICH_MINUT))].copy()

print("3. Přiřazuji terény k bodům...")
tereny_bodu = []
for _, row in df_trasa.iterrows():
    mp = Point(row['X'], row['Y'])
    t = "Bily les"
    if merged_geom["Cesta (Zpevnena)"].contains(mp): t = "Cesta (Zpevnena)"
    elif merged_geom["Cesta (Lesni)"].contains(mp): t = "Cesta (Lesni)"
    elif merged_geom["Pesina"].contains(mp): t = "Pesina"
    elif merged_geom["Prusek"].contains(mp): t = "Prusek"
    elif merged_geom["Voda"].contains(mp): t = "Voda"
    elif merged_geom["Kamenne pole"].contains(mp): t = "Kamenne pole"
    elif merged_geom["Hustnik 3 (Tmave)"].contains(mp): t = "Hustnik 3 (Tmave)"
    elif merged_geom["Hustnik 2 (Stredni)"].contains(mp): t = "Hustnik 2 (Stredni)"
    elif merged_geom["Hustnik 1 (Svetly)"].contains(mp): t = "Hustnik 1 (Svetly)"
    elif merged_geom["Podrost (Srafy)"].contains(mp): t = "Podrost (Srafy)"
    elif merged_geom["Paseky"].contains(mp): t = "Paseky"
    tereny_bodu.append(t)
df_trasa['Teren'] = tereny_bodu

print("4. Analyzuji sklon pomocí vrstevnic...")
df_trasa['Block_ID'] = (df_trasa['Teren'] != df_trasa['Teren'].shift(1)).cumsum()
analyzovana_data = []

for block_id, group in df_trasa.groupby('Block_ID'):
    if group['TimeDiff_s'].sum() < MIN_SEKUND_V_TERENU: continue
    teren_nazev = group['Teren'].iloc[0]
    vzdalenost_bloku = group['Dist_m'].sum()
    
    blok_prevyseni = 0
    if len(group) >= 2:
        pruseciky = LineString([(r['X'], r['Y']) for _, r in group.iterrows()]).intersection(vrstevnice_sit)
        if pruseciky.geom_type == 'Point': blok_prevyseni = EKVIDISTANCE_M
        elif pruseciky.geom_type == 'MultiPoint': blok_prevyseni = len(pruseciky.geoms) * EKVIDISTANCE_M

    sklon_pct = (blok_prevyseni / vzdalenost_bloku * 100) if vzdalenost_bloku > 0 else 0

    for _, row in group.iterrows():
        if row['TimeDiff_s'] > 0 and row['Dist_m'] > 0:
            tempo = (1000 / (row['Dist_m'] / row['TimeDiff_s'])) / 60
            if 2.0 < tempo < 40.0: 
                analyzovana_data.append({
                    'Terén': teren_nazev, 'X': row['X'], 'Y': row['Y'], 
                    'Tempo_min_km': tempo, 'Sklon_pct': sklon_pct
                })

df_final = pd.DataFrame(analyzovana_data)

print("\n" + "="*95)
print("🧠 5. VÝPOČET GAP (Úsilové tempo přepočtené absolutně na rovinu)")
print("="*95)

if not df_final.empty:
    # A. Najdeme referenční rovinatá tempa pro rozhodování (sklon < 2.5%)
    df_rovina = df_final[df_final['Sklon_pct'] < 2.5]
    rovina_tempa = df_rovina.groupby('Terén')['Tempo_min_km'].median()
    
    # B. Přepočet na GAP
    gap_tempa = []
    for _, row in df_final.iterrows():
        ter = row['Terén']
        sklon = row['Sklon_pct']
        raw_tempo = row['Tempo_min_km']
        
        if sklon < 2.5:
            gap_tempa.append(raw_tempo) # Rovina se nepřepočítává
        else:
            ref_tempo = rovina_tempa.get(ter, raw_tempo)
            if raw_tempo > ref_tempo:
                # Kopec tě zpomalil -> Vylepšíme tempo (Odmažeme kopec)
                # Odezva: cca 4% ztráta tempa na každý 1% sklon
                koeficient = 1 + (sklon * 0.04)
                gap_tempa.append(raw_tempo / koeficient)
            else:
                # Kopec tě zrychlil -> Zhoršíme tempo (Odstraníme pomoc gravitace)
                # Odezva: cca 2% zisk tempa na každý 1% sklon
                koeficient = 1 + (sklon * 0.02)
                gap_tempa.append(raw_tempo * koeficient)
                
    df_final['Tempo_GAP'] = gap_tempa
    
    # C. Agregace na jeden řádek
    summary_real = df_final.groupby("Terén")["Tempo_min_km"].median()
    summary_gap = df_final.groupby("Terén")["Tempo_GAP"].median().round(2).sort_values()
    counts = df_final["Terén"].value_counts()

    # Stanovení základního indexu
    base_gap = summary_gap.get("Cesta (Lesni)", summary_gap.min())
    
    print(f"📍 Standardizovaná reference: Cesta (Lesni) GAP = 1.00x\n")
    print(f"{'TERÉN'.ljust(22)} | {'REÁLNÝ PRŮMĚR'.ljust(15)} | {'PŘEPOČTENÝ GAP (Rovina)'.ljust(25)} | {'RELATIVNĚ'.ljust(10)} | BODŮ")
    print("-" * 95)
    
    for ter, gap_t in summary_gap.items():
        real_t = summary_real[ter]
        
        # Matematika na text pro reálné
        rm = int(real_t); rs = int((real_t - rm) * 60)
        # Matematika na text pro GAP
        gm = int(gap_t); gs = int((gap_t - gm) * 60)
        
        relativni = gap_t / base_gap
        
        print(f"{ter.ljust(22)} | {rm}:{rs:02d} /km         | 🚀 {gm}:{gs:02d} /km                 | {relativni:.2f}x      | {counts[ter]}")
else:
    print("Nedostatek dat.")
print("\n" + "="*95)

# Vykreslení zůstává stejné
fig, ax = plt.subplots(figsize=(14, 10))
fig.canvas.manager.set_window_title('Expertní Analytika - Obarvené Tempo')

ax.plot(draw_data["Voda"][0], draw_data["Voda"][1], color='dodgerblue', linewidth=2, alpha=0.5)
ax.plot(draw_data["Hustnik 1 (Svetly)"][0], draw_data["Hustnik 1 (Svetly)"][1], color='lightgreen', linewidth=1.5, alpha=0.3)
ax.plot(draw_data["Hustnik 2 (Stredni)"][0], draw_data["Hustnik 2 (Stredni)"][1], color='mediumseagreen', linewidth=1.5, alpha=0.4)
ax.plot(draw_data["Hustnik 3 (Tmave)"][0], draw_data["Hustnik 3 (Tmave)"][1], color='darkgreen', linewidth=1.5, alpha=0.5)
ax.plot(draw_data["Paseky"][0], draw_data["Paseky"][1], color='gold', linewidth=1.5, alpha=0.2)
ax.plot(draw_data["Cesta (Zpevnena)"][0], draw_data["Cesta (Zpevnena)"][1], color='black', linewidth=2.5, alpha=0.5)
ax.plot(draw_data["Cesta (Lesni)"][0], draw_data["Cesta (Lesni)"][1], color='dimgray', linewidth=2, alpha=0.5)
ax.plot(draw_data["Pesina"][0], draw_data["Pesina"][1], color='gray', linewidth=1.5, alpha=0.5)
ax.plot(draw_data["Prusek"][0], draw_data["Prusek"][1], color='silver', linewidth=1.5, alpha=0.5)
ax.plot(draw_data["Kamenne pole"][0], draw_data["Kamenne pole"][1], color='black', marker='^', markersize=2, linestyle='none', alpha=0.3)

colors = {'Bily les': 'cyan', 'Cesta (Zpevnena)': 'black', 'Cesta (Lesni)': 'darkgray', 'Pesina': 'gray', 'Prusek': 'silver', 'Hustnik 1 (Svetly)': 'lime', 'Hustnik 2 (Stredni)': 'forestgreen', 'Hustnik 3 (Tmave)': 'darkgreen', 'Podrost (Srafy)': 'olive', 'Kamenne pole': 'red', 'Paseky': 'orange'}
for ter, color in colors.items():
    subset = df_final[df_final['Terén'] == ter]
    if not subset.empty: ax.scatter(subset['X'], subset['Y'], c=color, label=ter, s=20, edgecolors='none', zorder=5)

ax.set_title(f"Vyfiltrovaná datová mapa (Min. v terénu: {MIN_SEKUND_V_TERENU} s)")
ax.legend(loc='upper left', framealpha=1.0)
ax.axis('equal'); ax.grid(True, linestyle=':', alpha=0.6)
plt.show()