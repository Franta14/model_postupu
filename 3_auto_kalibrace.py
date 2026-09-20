import cv2
import numpy as np
import os
import pickle
import config
from shapely.geometry import LineString

def run_auto_calibration():
    print("Spoustim automatickou OpenCV kalibraci (Fazova korelace)...")
    
    map_name = os.path.splitext(os.path.basename(config.OMAP_FILE))[0]
    cache_dir = os.path.join(config.CACHE_DIR, map_name)
    
    # 1. Načtení PNG mapy a vytvoření masky tmavých objektů (cesty, zdi)
    png_path = config.PNG_FILE
    if not os.path.exists(png_path):
        print(f"Nelze najit obrazek {png_path}")
        return
        
    img_bgr = cv2.imread(png_path)
    if img_bgr is None:
        print("Chyba pri nacitani obrazku OpenCV.")
        return
        
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    
    # Vyfiltrujeme tmavé pixely (černá a velmi tmavá hnědá - hodnota pod 130)
    # Binary INV znamená, že černé cesty budou v masce BÍLÉ (255)
    _, mask_png = cv2.threshold(gray, 130, 255, cv2.THRESH_BINARY_INV)
    mask_png = mask_png.astype(np.float32)
    
    # 2. Načtení středových linií a kalibrace z OMAPu
    cesty_pkl = os.path.join(cache_dir, "cesty_vektory.pkl")
    kalib_npy = os.path.join(cache_dir, "kalibrace.npy")
    
    if not os.path.exists(cesty_pkl) or not os.path.exists(kalib_npy):
        print("Chybi data z cache (spust nejprve setup_mapa.py)")
        return
        
    with open(cesty_pkl, "rb") as f:
        cesty_centerlines = pickle.load(f)
        
    kalibrace = np.load(kalib_npy)
    cal_a, cal_b, cal_c, cal_d, cal_e, cal_f = kalibrace
    
    # Inverzní afinní matice (z OMAP do PNG)
    A = np.array([[cal_a, cal_b], [cal_d, cal_e]])
    A_inv = np.linalg.inv(A)
    
    # 3. Vykreslení vektorů z OMAPu do prázdného plátna (stejná velikost jako PNG)
    mask_vector = np.zeros_like(mask_png)
    
    drawn_lines = 0
    for pts in cesty_centerlines:
        if isinstance(pts, list) and len(pts) >= 2:
            pixel_pts = []
            for mx, my in pts:
                b = np.array([mx - cal_c, my - cal_f])
                col, row = A_inv.dot(b)
                pixel_pts.append([int(col), int(row)])
                
            pts_arr = np.array(pixel_pts, np.int32)
            pts_arr = pts_arr.reshape((-1, 1, 2))
            
            # Kreslíme čáru tlustou 3 pixely bílou barvou
            cv2.polylines(mask_vector, [pts_arr], False, 255, thickness=3)
            drawn_lines += 1
            
    mask_vector = mask_vector.astype(np.float32)
    print(f"   Vykresleno {drawn_lines} vektorových cest do porovnávací masky.")
    
    # 4. Fázová korelace
    print("   Počítám fázovou korelaci (subpixelový posun)...")
    # Hanningovo okno potlačí okrajové artefakty
    hanning_window = cv2.createHanningWindow((mask_png.shape[1], mask_png.shape[0]), cv2.CV_32F)
    shift, response = cv2.phaseCorrelate(mask_vector, mask_png, hanning_window)
    
    dx, dy = shift
    print(f"Zjištěný chybějící posun: X = {dx:.2f} px, Y = {dy:.2f} px")
    print(f"   (Síla shody: {response*100:.1f} %)")
    
    # Pokud je shoda úplně nesmyslná (třeba posun o 1000 pixelů), omezíme to
    MAX_SHIFT = 50.0
    if abs(dx) > MAX_SHIFT or abs(dy) > MAX_SHIFT:
        print(f"VAROVANI: Vypocitany posun je prilis velky (> {MAX_SHIFT} px). Offset se nenastavi.")
        dx, dy = 0.0, 0.0
        
    # 5. Uložení offsetu
    offset_file = os.path.join(cache_dir, "kalibrace_offset.npy")
    np.save(offset_file, np.array([dx, dy], dtype=np.float32))
    print(f"Offset uložen do {offset_file}. Bude automaticky načten Liveloxem i Kurátorem!")

if __name__ == "__main__":
    run_auto_calibration()
