import xml.etree.ElementTree as ET
import numpy as np
import os
import matplotlib.pyplot as plt

def bresenham_line(x0, y0, x1, y1):
    """
    Vygeneruje seznam gridových souřadnic úsečky z (x0, y0) do (x1, y1)
    """
    points = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    x, y = x0, y0
    sx = -1 if x0 > x1 else 1
    sy = -1 if y0 > y1 else 1
    
    if dx > dy:
        err = dx / 2.0
        while x != x1:
            points.append((x, y))
            err -= dy
            if err < 0:
                y += sy
                err += dx
            x += sx
        points.append((x, y))
    else:
        err = dy / 2.0
        while y != y1:
            points.append((x, y))
            err -= dx
            if err < 0:
                x += sx
                err += dy
            y += sy
        points.append((x, y))
    return points

def extract_coords(coords_text):
    """
    Vytáhne body ze stringu. Zvládne formát oddělený středníkem (X Y [flag];X Y)
    i formát čistých mezer (X1 Y1 X2 Y2 X3 Y3).
    """
    pts = []
    if ';' in coords_text:
        # Formát se středníky
        for part in coords_text.strip().split(';'):
            nums = part.strip().split()
            if len(nums) >= 2:
                try:
                    pts.append((float(nums[0]) / 1000.0, -float(nums[1]) / 1000.0))
                except ValueError:
                    pass
    else:
        # Formát s mezerami (nepřetržitý sled)
        nums = coords_text.strip().split()
        for i in range(0, len(nums) - 1, 2):
            try:
                pts.append((float(nums[i]) / 1000.0, -float(nums[i+1]) / 1000.0))
            except ValueError:
                pass
    return pts

def main():
    print("Startuji presnou rasterizaci vrstevnic z OMAP do 2D mrizky...")
    
    # 1. Načtení mapy (meta)
    try:
        cost_grid = np.load('cenova_mapa.npy')
        meta = np.load('cenova_mapa_meta.npy')
        min_x, min_y, max_x, max_y, grid_size = meta
        height, width = cost_grid.shape
    except FileNotFoundError:
        print("Chybi cenova_mapa.npy nebo meta. Spust nejprve Fazi 1.")
        return

    # Vytvoření prázdné masky
    contour_grid = np.zeros((height, width), dtype=np.uint8)
    
    import config
    omap_file = config.OMAP_FILE
    print(f"Nacitam XML soubor {omap_file}...")
    
    try:
        tree = ET.parse(omap_file)
        root = tree.getroot()
    except Exception as e:
        print(f"Chyba pri cteni {omap_file}: {e}")
        return

    # Pokud OMAP obsahuje ns
    ns = {'ns': 'http://openorienteering.org/apps/mapper/xml/v2'}
    
    # Mapování ID -> kód ISOM (pokud jsou symboly definovány na začátku souboru)
    symbol_map = {}
    for sym_elem in root.findall('.//ns:symbol', ns) or root.findall('.//symbol'):
        s_id = sym_elem.attrib.get('id')
        s_code = sym_elem.attrib.get('code')
        if s_id and s_code:
            symbol_map[s_id] = s_code.split('.')[0]

    count_processed = 0
    count_points = 0
    
    # 2. Iterace přes všechny objekty
    objects = root.findall('.//ns:object', ns)
    if not objects:
        objects = root.findall('.//object')
        ns = {} # Zřejmě neobsahuje namespace
        
    for obj in objects:
        isom_code = None
        
        # 1. Zkus najit <symbol> uvnitr
        sym_child = obj.find('symbol' if not ns else 'ns:symbol', ns)
        if sym_child is not None and sym_child.text:
            isom_code = sym_child.text.strip().split('.')[0][:3]
        else:
            # 2. Zkus mapovani pres atribut
            sym_attr = obj.attrib.get('symbol')
            if sym_attr:
                if sym_attr in symbol_map:
                    isom_code = symbol_map[sym_attr][:3]
                else:
                    isom_code = sym_attr.split('.')[0][:3]
                        
        if isom_code in ['101', '102']:
            # Načteme coords
            coords_elem = obj.find('coords' if not ns else 'ns:coords', ns)
            if coords_elem is not None and coords_elem.text:
                pts = extract_coords(coords_elem.text)
                
                # Geometrické propojení bodů Bresenhamem
                for i in range(len(pts) - 1):
                    x0_map, y0_map = pts[i]
                    x1_map, y1_map = pts[i+1]
                    
                    ix0 = int((x0_map - min_x) / grid_size)
                    iy0 = int((y0_map - min_y) / grid_size)
                    ix1 = int((x1_map - min_x) / grid_size)
                    iy1 = int((y1_map - min_y) / grid_size)
                    
                    # Nakresli čáru (řešíme bounds, aby nepadalo mimo)
                    line_pts = bresenham_line(ix0, iy0, ix1, iy1)
                    for (px, py) in line_pts:
                        if 0 <= px < width and 0 <= py < height:
                            contour_grid[py, px] = 1
                            count_points += 1
                
                count_processed += 1

    print(f"Extrahovano a vy-rasterizovano {count_processed} vrstevnicovych krivek ({count_points} pixelu).")
    
    np.save('vrstevnice_maska.npy', contour_grid)
    print("Ulozeno jako 'vrstevnice_maska.npy'")
    
    # 3. Kontrolní PNG
    print("Generuji kontrolni vizualizacni PNG obrazek pres original...")
    try:
        import matplotlib.image as mpimg
        img = mpimg.imread(config.PNG_FILE)
        
        # Převedeme numpy pole na plně průhledné RGB a červenou pro masku
        overlay = np.zeros((height, width, 4), dtype=np.float32)
        overlay[contour_grid == 1] = [1.0, 0.0, 0.0, 1.0] # Červená a 100% neprůhledná
        
        fig, ax = plt.subplots(figsize=(15, 15), dpi=150)
        ax.imshow(img, extent=[0, width, height, 0]) 
        # imshow na overlay musí odpovídat velikosti, pro jednoduchost to prolneme 
        ax.imshow(overlay, extent=[0, width, height, 0])
        ax.axis('off')
        
        out_png = 'kontrola_vrstevnice.png'
        plt.savefig(out_png, bbox_inches='tight', pad_inches=0)
        plt.close(fig)
        print(f"Obrazek ulozen jako {out_png}. Muzes zkontrolovat, ze to 1:1 sedi!")
    except Exception as e:
        print(f"Nepodarilo se vygenerovat kontrolni obrazek: {e}")

if __name__ == '__main__':
    main()
