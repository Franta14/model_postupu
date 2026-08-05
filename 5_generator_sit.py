import xml.etree.ElementTree as ET
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep
import time
from scipy.ndimage import binary_dilation, binary_erosion

# =====================================================================
# --- ⚙️ NASTAVENÍ ---
# =====================================================================
omap_file = 'Homolka_Vojirov_20240917.omap'
GRID_SIZE_M = 0.5  # Rozlišení mřížky: 0.5 metru (Skvělý detail)
SIRKA_CESTY_BUFFER = 0.5
SIRKA_ZDI_BUFFER = 1.0  # 🧱 DŮLEŽITÉ: Zeď musí být dost široká, aby se nedala podběhnout diagonálně

# 🧠 ZLATÝ STANDARD TERÉNŮ (Cena za krok)
COST_DICT = {
    "Cesta (Zpevnena)": 0.700,   # Výrazně zlevněno (předtím 0.915)
    "Cesta (Lesni)": 0.750,      # (předtím 0.965)
    "Pesina": 0.820,             # (předtím 1.027)
    "Prusek": 0.950,             # (předtím 1.105)
    "Paseky": 1.080,
    "Bily les": 1.172,           # Necháno jako kotva (rozmezí cesta-les je teď mnohem větší)
    "Bazina": 1.317,
    "Voda": 1.318,
    "Hustnik 1 (Svetly)": 1.360,
    "Podrost (Srafy)": 1.418,
    "Hustnik 2 (Stredni)": 1.600, # Lehce zdraženo z 1.502
    "Hustnik 3 (Tmave)": 2.200,   # Výrazně zdraženo z 1.830
    "Kamenne pole": 1.840,
    
    "Kamen (Bod)": 2.500,         # Drobné kameny a srázky (1-2 metry vteřiny zpoždění při přímém přeběhu)
    "Velky kamen (Bod)": 3.000,   # Větší kameny (výraznější zpomalení)
    "Ryha / Potok": 5.000,        # Úzká linie. Přeskočení sebere běžci cca 1.5 - 2 vteřiny
    "Nebezpecna bazina": 4.000,   # ISOM 310, silně zpomalující bažina
    
    # 🧱 NEPRŮCHODNÉ PŘEKÁŽKY (Zeď)
    "Nepruchodna zed / plot": 9999.0,
    "Nepruchodna budova / zakaz": 9999.0,
    "Nepruchodna voda": 9999.0
}
DEFAULT_COST = COST_DICT["Bily les"]

# =====================================================================
# 1. NAČTENÍ MAPY A PŘÍPRAVA POLYGONŮ
# =====================================================================
print("🚀 Startuji Fázi 1: Rastrizace mapy do cenové mřížky...")
print("🗺️ Načítám vektorová data z OCADu...")

tree = ET.parse(omap_file)
root = tree.getroot()
symbol_map = {elem.attrib.get('id'): elem.attrib.get('code') for elem in root.iter() if 'symbol' in elem.tag.lower()}

kategorie = {k: [] for k in COST_DICT.keys()}

for obj in root.iter():
    if 'object' in obj.tag.lower():
        # Uřízneme desetinnou část kódu (např. 516.1 -> 516), ať nám to chytá vše
        isom = symbol_map.get(obj.attrib.get('symbol', ""), "").split('.')[0]
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
        
        # 📍 BODOVÉ OBJEKTY (Kameny, kupky)
        if len(pts) == 1:
            ter_bod = None
            buffer_size = 0.5
            if isom in ['204', '112', '113']: # Kámen, kupka, prohlubeň
                ter_bod = "Kamen (Bod)"
                buffer_size = 1.0  # rádius 1m
            elif isom in ['205', '206']: # Velký kámen, obrovský kámen
                ter_bod = "Velky kamen (Bod)"
                buffer_size = 1.5  # rádius 1.5m

            if ter_bod:
                # Obalíme bod bufferem a přidáme jako polygon
                kategorie[ter_bod].append(Point(pts[0]).buffer(buffer_size))

        # 📏 ČÁROVÉ OBJEKTY
        if len(pts) >= 2:
            ter_lin = None
            if isom in ['501', '502', '503']: ter_lin = "Cesta (Zpevnena)"
            elif isom == '504': ter_lin = "Cesta (Lesni)"
            elif isom in ['505', '506', '507']: ter_lin = "Pesina"
            elif isom in ['508', '509']: ter_lin = "Prusek"
            elif isom in ['114', '115', '304', '305', '306']: ter_lin = "Ryha / Potok"
            # 🧱 Přidány neprůchodné čáry: Sráz(201), Vysoký plot(516), Zeď(518)
            elif isom in ['201', '516', '518']: ter_lin = "Nepruchodna zed / plot"
            
            if ter_lin: 
                if ter_lin == "Nepruchodna zed / plot":
                    kategorie[ter_lin].append(LineString(pts).buffer(SIRKA_ZDI_BUFFER))
                elif ter_lin == "Ryha / Potok":
                    # Potok/Rýha má úzký buffer, funguje jako ostrá bariéra
                    kategorie[ter_lin].append(LineString(pts).buffer(0.3))
                else:
                    kategorie[ter_lin].append(LineString(pts).buffer(SIRKA_CESTY_BUFFER))

        # 🔲 POLYGONY
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
            elif isom == '311': ter_pol = "Bazina" 
            elif isom == '310': ter_pol = "Nebezpecna bazina" 
            # 🧱 Přidána neprůchodná voda
            elif isom in ['301', '302']: ter_pol = "Nepruchodna voda"
            elif isom.startswith('30'): ter_pol = "Voda"
            # 🧱 Přidány neprůchodné objekty: Olivová(520), Budova(521), Křížkování(526, 709)
            elif isom in ['520', '521', '526', '709']: ter_pol = "Nepruchodna budova / zakaz"
            
            if ter_pol: 
                kategorie[ter_pol].append(poly)

merged_geom = {}
prepared_geom = {}
for k, v in kategorie.items():
    if v:
        union_poly = unary_union(v)
        merged_geom[k] = union_poly
        prepared_geom[k] = prep(union_poly) 

# =====================================================================
# 2. DEFINICE MŘÍŽKY
# =====================================================================
all_polygons = [geom for geom in merged_geom.values() if not geom.is_empty]
if not all_polygons:
    print("❌ Na mapě se nepodařilo najít žádné objekty!")
    exit()

vse_dohromady = unary_union(all_polygons)
min_x, min_y, max_x, max_y = vse_dohromady.bounds

width = int(np.ceil((max_x - min_x) / GRID_SIZE_M))
height = int(np.ceil((max_y - min_y) / GRID_SIZE_M))

print(f"📐 Mapa ohraničena: X({min_x:.1f} až {max_x:.1f}), Y({min_y:.1f} až {max_y:.1f})")
print(f"📏 Vytvářím mřížku o velikosti {width} x {height} políček (Celkem {width * height} bodů).")

# =====================================================================
# 3. PLNĚNÍ MŘÍŽKY (OPRAVENÝ Z-INDEX)
# =====================================================================
cost_grid = np.full((height, width), DEFAULT_COST, dtype=np.float32)
start_time = time.time()

# ⚠️ ZÁSADNÍ OPRAVA: Zdi musí být úplně první, aby přebily cesty i hustníky
priority_order = [
    "Nepruchodna zed / plot", "Nepruchodna budova / zakaz", "Nepruchodna voda",
    "Cesta (Zpevnena)", "Cesta (Lesni)", "Pesina", "Prusek", 
    "Ryha / Potok", "Velky kamen (Bod)", "Kamen (Bod)",
    "Voda", "Nebezpecna bazina", "Kamenne pole", "Bazina", 
    "Hustnik 3 (Tmave)", "Hustnik 2 (Stredni)", "Podrost (Srafy)", 
    "Hustnik 1 (Svetly)", "Paseky"
]

print("⏳ Začínám sypat data do matice (Může to chvíli trvat)...")

for y_idx in range(height):
    real_y = min_y + (y_idx * GRID_SIZE_M)
    if y_idx % 200 == 0:
        print(f"   -> Zpracováno {y_idx}/{height} řádků...")

    for x_idx in range(width):
        real_x = min_x + (x_idx * GRID_SIZE_M)
        pt = Point(real_x, real_y)
        
        for teren in priority_order:
            if teren in prepared_geom and prepared_geom[teren].contains(pt):
                cost_grid[y_idx, x_idx] = COST_DICT[teren]
                break

end_time = time.time()
print(f"✅ Hrubá mřížka vypočítána za {end_time - start_time:.1f} vteřin.")

# =====================================================================
# 3b. MAGIE: DILATACE + EROZE (Slepení a vycentrování čar)
# =====================================================================
print("🪄 Aplikuji dilataci a erozi (Slepení a centrování tenkých čar)...")

kernel = np.ones((3, 3), bool)

maska_cest_hruba = (cost_grid > 0.8) & (cost_grid < 1.1)
maska_cest_dilatace = binary_dilation(maska_cest_hruba, structure=kernel)
maska_cest_eroze = binary_erosion(maska_cest_dilatace, structure=kernel, iterations=1)

kernel_skeleton = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool) 
maska_cest_skeleton = binary_erosion(maska_cest_eroze, structure=kernel_skeleton, iterations=1)

# POZOR NA PŘEPSÁNÍ ZDI: Propíšeme cesty zpět, ALE nesmíme jimi smazat zdi (skály a ploty)
for y in range(height):
    for x in range(width):
        if maska_cest_skeleton[y, x] and cost_grid[y, x] < 9000.0:
            cost_grid[y, x] = COST_DICT["Cesta (Lesni)"]

print("✅ Čárkované cesty úspěšně vycentrovány na šířku 1 pixelu a propojeny!")

# =====================================================================
# 4. ULOŽENÍ DAT
# =====================================================================
print("💾 Ukládám cenovou matici do souborů...")
np.save('cenova_mapa.npy', cost_grid)
metadata = np.array([min_x, min_y, max_x, max_y, GRID_SIZE_M])
np.save('cenova_mapa_meta.npy', metadata)

# =====================================================================
# 5. VIZUALIZACE
# =====================================================================
print("👀 Otevírám teplotní mapu (Heatmap)... ZAVŘI KŘÍŽKEM pro ukončení.")

fig, ax = plt.subplots(figsize=(12, 10))
fig.canvas.manager.set_window_title('Cenová mřížka pro A*')

# Capneme maximální hodnotu barvy pro vizualizaci na 2.0 (jinak by 9999 svítilo a zbytek mapy zčernal)
im = ax.imshow(np.clip(cost_grid, 0, 2.0), origin='lower', cmap='terrain_r', extent=[min_x, max_x, min_y, max_y])
cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
cbar.set_label('Cena za krok (Bílá svítivá oblaka = Neprůchodné ZDI)')

ax.set_title("Orienťácká mapa očima algoritmu A* (Neprůchodné objekty blokují cestu!)")
ax.set_xlabel("X souřadnice")
ax.set_ylabel("Y souřadnice")

plt.tight_layout()
plt.show()