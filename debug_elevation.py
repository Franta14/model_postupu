import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

# Pokusime se nacist config z aktualni slozky
try:
    import config
    map_image_file = config.PNG_FILE
    map_name = getattr(config, 'MAP_NAME', "Homolka_Vojirov_20240917")
except ImportError:
    # Fallback, kdyby config.py nesel nacist
    map_image_file = "Homolka_Vojirov_20240917.png"
    map_name = "Homolka_Vojirov_20240917"

def main():
    cache_dir = os.path.join("cache", map_name)
    
    # Nacteni dat
    elev_path = os.path.join(cache_dir, "vyskova_mapa.npy")
    meta_path = os.path.join(cache_dir, "cenova_mapa_meta.npy")
    cal_path = os.path.join(cache_dir, "kalibrace.npy")
    
    if not os.path.exists(elev_path):
        print(f"❌ Nenalezen soubor {elev_path}")
        return
        
    print(f"Načítám data pro mapu: {map_name}")
    elev_grid = np.load(elev_path)
    meta = np.load(meta_path)
    cal = np.load(cal_path)
    
    min_x, min_y, max_x, max_y, grid_size = meta
    cal_a, cal_b, cal_c, cal_d, cal_e, cal_f = cal
    
    print("Načítám obrázek mapy...")
    if not os.path.exists(map_image_file):
        print(f"❌ Nenalezen obrázek mapy: {map_image_file}")
        return
        
    img = mpimg.imread(map_image_file)
    
    print("Přepočítávám souřadnice pro překryv...")
    # Vytvoreni souradnic gridu
    h, w = elev_grid.shape
    grid_rows, grid_cols = np.mgrid[0:h, 0:w]
    
    # Prevod grid souradnic na S-JTSK (OOM)
    oom_x = min_x + grid_cols * grid_size
    oom_y = min_y + grid_rows * grid_size
    
    # Prevod S-JTSK na obrazove pixely pro zarovnani
    det = cal_a * cal_e - cal_b * cal_d
    img_cols = (cal_e * (oom_x - cal_c) - cal_b * (oom_y - cal_f)) / det
    img_rows = (cal_a * (oom_y - cal_f) - cal_d * (oom_x - cal_c)) / det
    
    print("Kreslím heatmapu a vrstevnice nad mapou (může to pár vteřin trvat)...")
    fig, ax = plt.subplots(figsize=(14, 10))
    
    # Zobrazeni orientacni mapy na pozadi
    ax.imshow(img)
    
    # Zvolime krok vrstevnic po 5 metrech
    elev_min = np.nanmin(elev_grid)
    elev_max = np.nanmax(elev_grid)
    levels = np.arange(np.floor(elev_min/2.5)*2.5, np.ceil(elev_max/2.5)*2.5 + 2.5, 2.5)
    
    # Vykresleni heatmapy vrstevnic (polopruhledne barevne plochy)
    contourf = ax.contourf(img_cols, img_rows, elev_grid, levels=levels, alpha=0.4, cmap='jet')
    
    # Vykresleni zvyraznenych hlavnich vrstevnic presne z modelu
    contours = ax.contour(img_cols, img_rows, elev_grid, levels=levels, colors='black', linewidths=0.8, alpha=0.7)
    
    # Popisky k vrstevnicim
    ax.clabel(contours, inline=True, fontsize=9, fmt='%1.0f m')
    
    # Pridani legendy (colorbar)
    cbar = plt.colorbar(contourf, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Nadmořská výška dle modelu DMR5G (m)", rotation=270, labelpad=15)
    
    ax.set_title("Ověření přesnosti výškového modelu vůči orienťácké mapě", fontsize=14, fontweight='bold')
    ax.axis('off')
    
    plt.tight_layout()
    print("Hotovo! Zobrazuji okno...")
    plt.show()

if __name__ == "__main__":
    main()
