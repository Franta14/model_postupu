import os
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image

try:
    import config
    MAP_IMAGE = config.PNG_FILE
    OMAP_FILE = config.OMAP_FILE
except ImportError:
    MAP_IMAGE = "mapa.png"
    OMAP_FILE = "Homolka_Vojirov_20240917.omap"

CACHE_DIR = os.path.join("cache", os.path.splitext(os.path.basename(OMAP_FILE))[0])
LIDAR_FILE = os.path.join(CACHE_DIR, "vyskova_mapa.npy")
META_FILE = os.path.join(CACHE_DIR, "cenova_mapa_meta.npy")

def main():
    print("Nacitam data pro finalni vizualni kontrolu...")
    meta = np.load(META_FILE)
    min_x, min_y, max_x, max_y, grid_size = meta[0], meta[1], meta[2], meta[3], meta[4]
    
    lidar_grid = np.load(LIDAR_FILE)
    
    img = Image.open(MAP_IMAGE)
    
    h, w = lidar_grid.shape
    x = np.linspace(min_x, max_x, w)
    y = np.linspace(min_y, max_y, h)
    X, Y = np.meshgrid(x, y)
    
    fig, ax = plt.subplots(figsize=(15, 10))
    
    # 1. Kreslime puvodni PNG mapu do pozadi
    print("Vykresluji originalni OMAP mapu do pozadi...")
    ax.imshow(img, extent=(min_x, max_x, min_y, max_y))
    
    # 2. Pomoci ciste matematiky "vykrojime" z naseho 3D modelu (lidar_grid) vrstevnice
    # Tim, ze jsme do modelu zadali ekvidistanci 5 metru, mela by fuknce contour 
    # pro krok 5.0 metru najit EXACTNE stejny tvar, jaky je nakresleny v OMAP mape.
    print("Generuji matematicke vrstevnice z vytvoreneho 3D modelu...")
    min_z = np.nanmin(lidar_grid)
    max_z = np.nanmax(lidar_grid)
    
    # Pevny krok vzdy po 5 metrech (napr. 500.0, 505.0, 510.0...)
    levels = np.arange(np.floor(min_z / 5.0) * 5.0, np.ceil(max_z / 5.0) * 5.0 + 5.0, 5.0)
    
    # Nakreslime je modrou polopruhlednou barvou, abys videl ty hnede pod nima
    CS = ax.contour(X, Y, lidar_grid, levels=levels, colors='blue', linewidths=1.5, alpha=0.8)
    
    # 3. Pridame na modre cary primo text s jejich vypocitanou vyskou!
    print("Vkladam na cary texty s prirazenymi vyskami...")
    ax.clabel(CS, inline=True, fontsize=10, fmt='%1.0f m', colors='darkblue')
    
    ax.set_title("FINÁLNÍ KONTROLA: Modré čáry = 3D model | Hnědé čáry = OMAP | Čísla = Vypočítané výšky")
    ax.set_xlabel("X (metry)")
    ax.set_ylabel("Y (metry)")
    
    print("Zobrazuji okno... Pokud se modre cary presne kryji s hnedymi, vyhrali jsme!")
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
