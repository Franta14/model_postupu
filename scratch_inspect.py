"""Rychla diagnostika noveho vyskoveho modelu."""
import os, numpy as np, config

map_name = os.path.splitext(os.path.basename(config.OMAP_FILE))[0]
cache_dir = os.path.join("cache", map_name)

elev = np.load(os.path.join(cache_dir, "vyskova_mapa.npy"))
print(f"Grid: {elev.shape}")
print(f"Elevation range: {elev.min():.1f} - {elev.max():.1f} m")

# Distribution check
ekv = config.EKVIDISTANCE_M
unique_elevs, counts = np.unique(np.round(elev, 1), return_counts=True)
top = np.argsort(-counts)[:10]
print(f"\nTop 10 most common elevations:")
for i in top:
    print(f"  {unique_elevs[i]:.1f} m: {counts[i]} cells ({counts[i]/elev.size*100:.1f}%)")

# Check contour pixel elevations
contour_raster = np.load(os.path.join(cache_dir, "contour_raster.npy"))
c_mask = contour_raster > 0
c_elevs = elev[c_mask]
remainder = np.mod(c_elevs, ekv)
print(f"\nNa vrstevnicovych pixelech:")
print(f"  Elevation remainder (mod {ekv}): mean={remainder.mean():.3f}, std={remainder.std():.3f}")
print(f"  (blizko 0 = izolinie modelu sedi s OMAP vrstevnicemi)")
