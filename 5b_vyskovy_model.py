import math
import os
import time
import xml.etree.ElementTree as ET

import numpy as np
import matplotlib.pyplot as plt
from pyproj import Transformer
from scipy.optimize import least_squares, minimize
from scipy.spatial import cKDTree

# --- NASTAVENI ---
xyz_soubor = "DMR5G.xyz"
import config
xml_file = config.XML_FILE  # IOF CourseData s Position + MapPosition

# Doladeni kalibrace oproti cistemu Nelder-Meadu:
# 1) least_squares (TRF) = presne L2 minima stejneho modelu (casto par metru lepe)
# 2) volitelne robustni loss: zmensi vliv 1-2 outlier kontrol
USE_LEAST_SQUARES_REFINE = True
# map. jednotky cca metry: ~3 = body s chybou >3 m tahnou mene; 0 = vypnout robustni cast
ROBUST_F_SCALE = 0.0  # napr. 2.0 az 4.0, nebo 0.0

print("🚀 Startuji Fázi 2: Tvorba 3D výškového modelu s Auto-Zarovnáním...")

# =====================================================================
# 1. NAČTENÍ MŘÍŽKY MAPY
# =====================================================================
try:
    cost_grid = np.load('cenova_mapa.npy')
    meta = np.load('cenova_mapa_meta.npy')
    min_x, min_y, max_x, max_y, grid_size = meta
    height, width = cost_grid.shape
except FileNotFoundError:
    print("❌ Chybí cenova_mapa.npy. Spusť nejprve Fázi 1.")
    exit()

# =====================================================================
# 2. VÝPOČET POSUNU (S-JTSK -> Lokální OCAD/OOM)
# =====================================================================
print("🌍 Počítám přesný přesun mezi státním systémem S-JTSK a lokální mapou...")
try:
    tree_xml = ET.parse(xml_file)
    root_xml = tree_xml.getroot()
    ns = {'ns': 'http://www.orienteering.org/datastandard/3.0'}
    controls_sjtsk = []
    controls_ocad = []
    
    # Transformátor z klasické GPS (WGS84) do S-JTSK (Křovákovo zobrazení)
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:5514", always_xy=True)
    
    for ctrl in root_xml.findall('.//ns:Control', ns):
        pos = ctrl.find('ns:Position', ns)
        mpos = ctrl.find('ns:MapPosition', ns)
        if pos is not None and mpos is not None:
            lon, lat = float(pos.attrib['lng']), float(pos.attrib['lat'])
            mx, my = float(mpos.attrib['x']), float(mpos.attrib['y'])
            
            # Zjistíme státní souřadnice pro kontrolu
            sjtsk_y, sjtsk_x = transformer.transform(lon, lat)
            controls_sjtsk.append([sjtsk_y, sjtsk_x])
            controls_ocad.append([mx, my])
            
    controls_sjtsk = np.array(controls_sjtsk)
    controls_ocad = np.array(controls_ocad)
except Exception as e:
    print(f"❌ Chyba při čtení XML kontrol: {e}")
    exit()

# Matematicka kalibrace: similituda  (s * R * p + t), p = (-sj_y, -sj_x) komponenty
rx = -controls_sjtsk[:, 0]
ry = -controls_sjtsk[:, 1]


def vycisli_fxy(p):
    dx, dy, rot, sc = p
    rad = math.radians(rot)
    ca, sa = math.cos(rad), math.sin(rad)
    fx = (rx * sc) * ca - (ry * sc) * sa + dx
    fy = (rx * sc) * sa + (ry * sc) * ca + dy
    return fx, fy


def cost_f(params):
    dx, dy, rot, scale = params
    fx, fy = vycisli_fxy((dx, dy, rot, scale))
    return np.sum((fx - controls_ocad[:, 0]) ** 2 + (fy - controls_ocad[:, 1]) ** 2)


def vektor_odesky(p, ocad):
    fx, fy = vycisli_fxy(p)
    return np.concatenate([fx - ocad[:, 0], fy - ocad[:, 1]])


x0 = np.array(
    [controls_ocad[0, 0] - rx[0], controls_ocad[0, 1] - ry[0], 0.0, 1.0], dtype=float
)
res_nm = minimize(cost_f, x0, method="Nelder-Mead")
p_best = res_nm.x

if USE_LEAST_SQUARES_REFINE and len(controls_ocad) >= 3:
    loss = "linear"
    f_scale = 1.0
    if ROBUST_F_SCALE and ROBUST_F_SCALE > 0:
        loss = "soft_l1"
        f_scale = float(ROBUST_F_SCALE)
    res_ls = least_squares(
        lambda p: vektor_odesky(p, controls_ocad),
        p_best,
        method="trf",
        xtol=1e-9,
        ftol=1e-9,
        gtol=1e-9,
        max_nfev=5000,
        loss=loss,
        f_scale=f_scale,
    )
    p_best = res_ls.x

final_dx, final_dy, final_rot, final_scale = p_best
ca, sa = math.cos(math.radians(final_rot)), math.sin(math.radians(final_rot))

# diagnostika: RMSE v map. jednotkach (u tebe zhruba metry)
fx_r, fy_r = vycisli_fxy(p_best)
chyby = np.hypot(fx_r - controls_ocad[:, 0], fy_r - controls_ocad[:, 1])
rmse = float(np.sqrt(np.mean(chyby**2)))
print(f"   Kalibrace: RMSE={rmse:.3f} (map. jednotky), {len(controls_ocad)} kontrol")

# =====================================================================
# 3. FILTRACE A TRANSFORMACE LiDAR BODŮ
# =====================================================================
center_sjtsk_y = np.mean(controls_sjtsk[:, 0])
center_sjtsk_x = np.mean(controls_sjtsk[:, 1])
vyskove_body_ocad = []

print("⏳ Otevírám laserová data a přetahuji je na mapu (To chvíli zabere)...")
start_time = time.time()

if not os.path.exists(xyz_soubor):
    print(f"❌ Nemohu najít soubor '{xyz_soubor}'.")
    exit()

with open(xyz_soubor, 'r') as f:
    for line in f:
        parts = line.strip().split()
        if len(parts) >= 3:
            try:
                sj_y, sj_x, z = float(parts[0]), float(parts[1]), float(parts[2])
                # 1. Hrubý filtr: bereme jen okruh ~3 km kolem středu mapy (zahodíme zbytek ČR)
                if abs(sj_y - center_sjtsk_y) < 3000 and abs(sj_x - center_sjtsk_x) < 3000:
                    # 2. Matematický posun na přesné lokální souřadnice tvé mapy
                    lx = -sj_y
                    ly = -sj_x
                    fx = (lx * final_scale) * ca - (ly * final_scale) * sa + final_dx
                    fy = (lx * final_scale) * sa + (ly * final_scale) * ca + final_dy
                    
                    # 3. Jemný filtr na přesný rámeček (s přesahem 50m)
                    if (min_x - 50) <= fx <= (max_x + 50) and (min_y - 50) <= fy <= (max_y + 50):
                        vyskove_body_ocad.append([fx, fy, z])
            except ValueError:
                pass

vyskove_body_ocad = np.array(vyskove_body_ocad)
print(f"✅ Vymodelováno {len(vyskove_body_ocad)} přesných 3D bodů pod tvou mapou.")

if len(vyskove_body_ocad) == 0:
    print("❌ CHYBA: Z laserových dat nezbyl ani jeden bod! Zřejmě jsi z ČÚZK stáhl jiný čtverec, než ve kterém je les.")
    exit()

# =====================================================================
# 4. KD-TREE A INTERPOLACE (Výroba sítě)
# =====================================================================
print("🌲 Stavím prostorový KD-Tree pro extrémně rychlé hledání...")
strom_vysek = cKDTree(vyskove_body_ocad[:, :2])

print("⛰️ Pokládám výškovou peřinu na naši cenovou šachovnici...")
x_coords = min_x + np.arange(width) * grid_size
y_coords = min_y + np.arange(height) * grid_size
xx, yy = np.meshgrid(x_coords, y_coords)
grid_points = np.c_[xx.ravel(), yy.ravel()]

vzdalenosti, indexy_nejblizsich = strom_vysek.query(grid_points)
z_values = vyskove_body_ocad[indexy_nejblizsich, 2]
vyskova_matice = z_values.reshape((height, width))

end_time = time.time()
print(f"✅ Hotovo! 3D model lesa vygenerován za {end_time - start_time:.1f} vteřin.")

# Uložení dat pro algoritmus A*
np.save('vyskova_mapa.npy', vyskova_matice)

# =====================================================================
# 5. VIZUALIZACE A KONTROLA
# =====================================================================
print("\n👀 Otevírám 3D model terénu... ZAVŘI KŘÍŽKEM pro ukončení.")

fig, ax = plt.subplots(figsize=(12, 10))
fig.canvas.manager.set_window_title('Výškový model (LiDAR) vs Kontroly')

im = ax.imshow(vyskova_matice, origin='lower', cmap='plasma', extent=[min_x, max_x, min_y, max_y])
contours = ax.contour(xx, yy, vyskova_matice, levels=int((np.max(vyskova_matice) - np.min(vyskova_matice)) / 5), 
                      colors='black', linewidths=0.5, alpha=0.6)
ax.clabel(contours, inline=True, fontsize=8, fmt='%1.0f m')

# Vykreslení kontrol jako důkaz, že to lícujeme správně!
ax.scatter(controls_ocad[:, 0], controls_ocad[:, 1], color='magenta', s=80, label='Kontroly')

cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
cbar.set_label('Nadmořská výška (m.n.m.)')
ax.set_title(f"LiDAR vs kontroly  |  RMSE kalibrace {rmse:.2f} (map. j.)")
ax.legend()

plt.tight_layout()
plt.show()