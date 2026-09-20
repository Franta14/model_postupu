import json, glob, os, numpy as np
from scipy.ndimage import map_coordinates, gaussian_filter
import config

cache_dir = os.path.join(config.CACHE_DIR, os.path.splitext(os.path.basename(config.OMAP_FILE))[0])
postupy = sorted(glob.glob(os.path.join(cache_dir, 'postupy', '*.json')))

elev_grid = np.load(os.path.join(cache_dir, 'vyskova_mapa.npy'))
elev_grid = gaussian_filter(elev_grid, sigma=2)

print(f'Celkem postupu: {len(postupy)}')
print(f'Elev grid range: {elev_grid.min():.1f} - {elev_grid.max():.1f} m\n')

nulove_prevyseni = []
nenulovych = 0

for path in postupy[:50]:  # zkontrolujeme prvnich 50
    with open(path, 'r', encoding='utf-8') as f:
        p = json.load(f)
    
    variants = p.get('variants', [])
    for i, v in enumerate(variants):
        cesta = v.get('cesta', [])
        prevyseni_ulozene = v.get('prevyseni_m', None)
        
        if not cesta:
            continue
            
        y_c = [pt[0] for pt in cesta]
        x_c = [pt[1] for pt in cesta]
        z_raw = map_coordinates(elev_grid, [y_c, x_c], order=1)
        climb_raw = sum(max(0, z_raw[i]-z_raw[i-1]) for i in range(1, len(z_raw)))
        
        if prevyseni_ulozene == 0 or prevyseni_ulozene is None:
            nulove_prevyseni.append({
                'file': os.path.basename(path),
                'variant': i,
                'prevyseni_ulozene': prevyseni_ulozene,
                'climb_raw': round(climb_raw, 1),
                'z_min': round(float(z_raw.min()), 1),
                'z_max': round(float(z_raw.max()), 1),
            })
        else:
            nenulovych += 1

print(f'Nenulove prevyseni (OK): {nenulovych}')
print(f'Nulove/None prevyseni (BUG): {len(nulove_prevyseni)}')
print()
for item in nulove_prevyseni[:10]:
    print(item)
