import os
import numpy as np
from scipy.interpolate import griddata
import matplotlib.pyplot as plt

try:
    import config
    OMAP_FILE = config.OMAP_FILE
except ImportError:
    OMAP_FILE = "Homolka_Vojirov_20240917.omap"

CACHE_DIR = os.path.join("cache", os.path.splitext(os.path.basename(OMAP_FILE))[0])
IN_GRID_FILE = os.path.join(CACHE_DIR, "vrstevnice_vysky.npy")
OUT_GRID_FILE = os.path.join(CACHE_DIR, "vyskova_mapa.npy")

def main():
    print("Nacitam mrizku s vrstevnicemi...")
    vysky = np.load(IN_GRID_FILE)
    
    # Najdeme vsechny body s hodnotou
    y_idxs, x_idxs = np.where(~np.isnan(vysky))
    z_vals = vysky[y_idxs, x_idxs]
    
    print(f"Pocet vzorku pro interpolaci: {len(z_vals)}")
    points = np.column_stack((x_idxs, y_idxs))
    
    # Vytvorime cilovou sit (celou mrizku)
    h, w = vysky.shape
    grid_x, grid_y = np.meshgrid(np.arange(w), np.arange(h))
    
    print("Vyplnuji prázdný prostor svahy (Delaunay/Linear)...")
    # Linear zajisti plynule naklonene roviny (svahy) mezi vrstevnicemi
    interpolated = griddata(points, z_vals, (grid_x, grid_y), method='linear')
    
    # Okraje, ktere nepokryje linear (mimo obalovy polygon vsech vrstevnic),
    # dodelame nearest (roztazeni okrajove vysky az do kraje papiru)
    print("Dopocitavam absolutni okraje mapy (Nearest)...")
    nans = np.isnan(interpolated)
    if np.any(nans):
        nearest = griddata(points, z_vals, (grid_x[nans], grid_y[nans]), method='nearest')
        interpolated[nans] = nearest
        
    print(f"Prepisuji stary LiDAR model za novy vektorovy: {OUT_GRID_FILE}...")
    np.save(OUT_GRID_FILE, interpolated)
    
    # Rychly render pro kontrolu, jestli jsou tam schody 
    # (pokud udelame contourf z interpolated s krokem 5, melo by to vytvorit puvodni mapu)
    print("Vykresluji 3D nahled (hillshade) pro kontrolu...")
    # Jednoduchy hillshade
    dx, dy = np.gradient(interpolated)
    slope = np.pi/2. - np.arctan(np.sqrt(dx*dx + dy*dy))
    aspect = np.arctan2(-dx, dy)
    azimuth = np.radians(315.0)
    altitude = np.radians(45.0)
    hillshade = np.sin(altitude)*np.sin(slope) + np.cos(altitude)*np.cos(slope)*np.cos(azimuth - aspect)
    
    plt.figure(figsize=(10, 10))
    plt.imshow(hillshade, cmap='gray', origin='lower')
    plt.title("Finalni Vektorovy 3D Model (Hillshade)")
    plt.axis('off')
    plt.savefig("final_3d_model.png", dpi=150, bbox_inches='tight')
    print("Nahled ulozen do final_3d_model.png")
    
    print("Vse uspesne dokonceno!")

if __name__ == "__main__":
    main()
