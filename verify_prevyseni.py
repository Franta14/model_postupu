import numpy as np, json, os, glob
from scipy.ndimage import gaussian_filter
import metriky, config

cache_dir = os.path.join(config.CACHE_DIR, os.path.splitext(os.path.basename(config.OMAP_FILE))[0])
cost_grid = np.load(os.path.join(cache_dir, 'cenova_mapa.npy'))
elev_grid = np.load(os.path.join(cache_dir, 'vyskova_mapa.npy'))
elev_grid = gaussian_filter(elev_grid, sigma=2)

postupy = sorted(glob.glob(os.path.join(cache_dir, 'postupy', '*.json')))[:8]

all_ok = True
for path in postupy:
    with open(path, 'r', encoding='utf-8') as f:
        p = json.load(f)
    variants = p.get('variants', [])
    print(os.path.basename(path))
    for i, v in enumerate(variants[:3]):
        cesta = v.get('cesta', [])
        if not cesta:
            continue
        vzd, prev, usili, usili_real, road_ratio = metriky.spocitat_metriky(
            cesta, cost_grid, elev_grid, 0.5, config.NASOBIC_MERITKA, val_kopce=5.0
        )
        ulozene = v.get('prevyseni_m')
        ok = "OK" if round(prev) > 0 else "BUG=0"
        if round(prev) == 0:
            all_ok = False
        print(f"  Var {i}: delka={round(vzd)}m, prevyseni_NOVE={round(prev)}m, prevyseni_ULOZENE={ulozene}  [{ok}]")
    print()

print("=== VYSLEDEK ===")
print("Vsechny nenulove:" if all_ok else "STALE NULOVE PREVYSENI!")
