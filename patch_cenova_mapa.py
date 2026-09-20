"""
patch_cenova_mapa.py
====================
Rychly patch stávající cenové mřížky bez nutnosti přegenerování:
  1. ISOM 301 (řeky/jezera): 9999 → 4.0  (překonatelné brodění)
  2. ISOM 202 (skálu/srázy): buffer 1.0m zakryl sousední cesty → obnova
  3. Recovery: obnoví všechny 9999 buňky, které leží uvnitř cestního polygonu

Spuštění:  python patch_cenova_mapa.py
"""

import os, sys, time
import numpy as np
import xml.etree.ElementTree as ET
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep
import config

# ── Cesty k souborům ──────────────────────────────────────────────────────────
map_name  = os.path.splitext(os.path.basename(config.OMAP_FILE))[0]
cache_dir = os.path.join(config.CACHE_DIR, map_name)

cenova_path = os.path.join(cache_dir, "cenova_mapa.npy")
meta_path   = os.path.join(cache_dir, "cenova_mapa_meta.npy")

if not os.path.exists(cenova_path):
    print(f"❌ Soubor {cenova_path} nenalezen. Spustte nejprve setup_mapa.py.")
    sys.exit(1)

print("📂 Načítám stávající cenovou mřížku...")
cost_grid = np.load(cenova_path)
meta = np.load(meta_path)
min_x, min_y, max_x, max_y, grid_size = meta
height, width = cost_grid.shape
print(f"   Grid: {width}×{height}  |  9999 buněk: {int(np.sum(cost_grid >= 9000)):,}")

# ── Načtení vektorových dat z OMAP ───────────────────────────────────────────
print(f"\n📖 Čtu OMAP: {config.OMAP_FILE} ...")
tree = ET.parse(config.OMAP_FILE)
root = tree.getroot()

symbol_map = {}
for elem in root.iter():
    if 'symbol' in elem.tag.lower():
        s_id = elem.attrib.get('id')
        s_code = elem.attrib.get('code')
        if s_id and s_code:
            symbol_map[s_id] = s_code.split('.')[0]

# Polygony cest a pěšin (pro recovery)
cesta_polys   = []
# Polygony ISOM 301 (řeky/jezera, dříve 9999 → teď 4.0)
reka_polys    = []

SIRKA_CESTY = 0.5   # shodné se setup_mapa.py

for obj in root.iter():
    if 'object' not in obj.tag.lower():
        continue
    s_id = obj.attrib.get('symbol', '')
    isom = symbol_map.get(s_id, '')

    pts = []
    for child in obj:
        if 'coords' in child.tag.lower() and child.text:
            for p in child.text.strip().split(';'):
                parts = p.strip().split()
                if len(parts) >= 2:
                    try:
                        pts.append((float(parts[0]) / 1000, -float(parts[1]) / 1000))
                    except ValueError:
                        pass
            break

    if not pts:
        continue

    # Čárové objekty cest → buffer → polygon (pro recovery)
    if len(pts) >= 2 and isom in ['501', '502', '503', '504', '505', '506', '507', '508', '509']:
        cesta_polys.append(LineString(pts).buffer(SIRKA_CESTY))

    # Polygony ISOM 301 (vodn ploch) → překlasifikujeme na průchozí
    if len(pts) >= 3 and isom == '301':
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        reka_polys.append(poly)

print(f"   Cestní polygony: {len(cesta_polys)}")
print(f"   Vodní plochy ISOM 301: {len(reka_polys)}")

# ── PATCH 1: Obnova cestních buněk pod 9999 ───────────────────────────────────
print("\n🔧 PATCH 1: Obnova cestních buněk překrytých zdí/srázy...")
t0 = time.time()

if cesta_polys:
    merged_cesty = unary_union(cesta_polys)
    prep_cesty   = prep(merged_cesty)

    wall_ys, wall_xs = np.where(cost_grid >= 9000.0)
    recovered = 0

    for i in range(len(wall_ys)):
        real_x = min_x + wall_xs[i] * grid_size
        real_y = min_y + wall_ys[i] * grid_size
        pt = Point(real_x, real_y)
        if prep_cesty.contains(pt):
            cost_grid[wall_ys[i], wall_xs[i]] = 0.75  # lesní cesta
            recovered += 1

    print(f"   ✅ Obnoveno {recovered:,} buněk ({time.time()-t0:.1f}s)")
else:
    print("   ⚠️  Žádné cestní polygony nenalezeny, recovery přeskočeno.")

# ── PATCH 2: Překlasifikace ISOM 301 (řeky/jezera) z 9999 → 4.0 ─────────────
print("\n🔧 PATCH 2: Překlasifikace ISOM 301 (řeky/jezera): 9999 → 4.0 ...")
t0 = time.time()

if reka_polys:
    merged_reky = unary_union(reka_polys)
    prep_reky   = prep(merged_reky)

    # Znovu načteme wall buňky (po recovery mohou být jiné)
    wall_ys2, wall_xs2 = np.where(cost_grid >= 9000.0)
    reka_changed = 0

    for i in range(len(wall_ys2)):
        real_x = min_x + wall_xs2[i] * grid_size
        real_y = min_y + wall_ys2[i] * grid_size
        pt = Point(real_x, real_y)
        if prep_reky.contains(pt):
            cost_grid[wall_ys2[i], wall_xs2[i]] = 4.0
            reka_changed += 1

    print(f"   ✅ Překlasifikováno {reka_changed:,} buněk řek/jezer ({time.time()-t0:.1f}s)")
else:
    print("   ⚠️  Žádné ISOM 301 polygony nenalezeny.")

# ── Výsledná statistika ───────────────────────────────────────────────────────
print(f"\n📊 Statistiky po patchi:")
print(f"   Neprůchodné buňky (9999): {int(np.sum(cost_grid >= 9000)):,}")
print(f"   Cestní buňky (< 0.87):   {int(np.sum(cost_grid < 0.87)):,}")
print(f"   Říční buňky (== 4.0):    {int(np.sum(cost_grid == 4.0)):,}")

# ── Záloha a uložení ──────────────────────────────────────────────────────────
backup_path = cenova_path.replace(".npy", "_backup.npy")
if not os.path.exists(backup_path):
    import shutil
    shutil.copy2(cenova_path, backup_path)
    print(f"\n💾 Záloha uložena: {backup_path}")

np.save(cenova_path, cost_grid)
print(f"✅ Opravená cenová mřížka uložena: {cenova_path}")
print("\n👉 Dalsi krok: python 9_generator_postupu.py")
