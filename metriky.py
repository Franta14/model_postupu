import math
import numpy as np
from scipy.ndimage import map_coordinates

def spocitat_metriky(cesta, working_grid_base, elev_grid, grid_size, nasobic_meritka, val_kopce=5.0):
    """Vypocet vzdalenosti, prevyseni, usili (s penalizacemi pro algoritmus i bez nich pro cas) a podilu cest pro trasu."""
    vzd = prev = usili = usili_real = road_dist = 0.0
    
    # --- VÝPOČET NASTOUPANÉHO PŘEVÝŠENÍ ---
    if len(cesta) > 0:
        # Bilineární interpolace výšky podél trasy
        y_c = [p[0] for p in cesta]
        x_c = [p[1] for p in cesta]
        z_raw = map_coordinates(elev_grid, [y_c, x_c], order=1)
        
        # Odstraněno: pohyblivý průměr (uniform_filter1d).
        # Na lomených úsečkách s řídkými lomy tvořil fantomové kopce. 
        # elev_grid je z výroby (v setup_mapa.py) dostatečně vyhlazen.
        z_smooth = z_raw.astype(np.float64)
        
        # Kumulativní nastoupané metry: součet kladných výškových přírůstků
        NOISE_THRESHOLD = 0.1  # metrů
        prev = 0.0
        for i in range(1, len(z_smooth)):
            dz = z_smooth[i] - z_smooth[i - 1]
            if dz > NOISE_THRESHOLD:
                prev += dz
    else:
        z_smooth = []
    # -----------------------------
    
    for j in range(1, len(cesta)):
        p1, p2 = cesta[j - 1], cesta[j]
        dy_px = p2[0] - p1[0]
        dx_px = p2[1] - p1[1]
        dist_px = math.hypot(dy_px, dx_px)
        dg = dist_px * grid_size
        dist_m = dg * nasobic_meritka
        vzd += dist_m
        
        y1, x1 = int(p1[0]), int(p1[1])
        y2, x2 = int(p2[0]), int(p2[1])
        
        is_rc = working_grid_base[y1, x1] < 1.09
        is_rn = working_grid_base[y2, x2] < 1.09
        
        c1 = min(3.0, working_grid_base[y1, x1])
        c2 = min(3.0, working_grid_base[y2, x2])
        
        # Použijeme průměr počátečního a koncového bodu úseku, stejně jako Dijkstra
        # Vyhýbáme se mezikrokům zaokrouhleným přes int(), které by cestu mohly minout.
        terren_cost = c1 * 0.5 + c2 * 0.5
        is_rm = is_rn
            
        is_runner_on_road = is_rc
        is_runner_next_road = is_rn and is_rm
        
        z1 = z_smooth[j - 1]
        z2 = z_smooth[j]
        dz = z2 - z1
        
        sklon = dz / dist_m if dist_m > 0.1 else 0.0
        
        # Ochrana proti mikroschodum a SRTM anomaliim
        # Původně tu byl limit 8 % pro cesty, ale to ničilo tempo na reálně prudkých cestách.
        # Nyní aplikujeme stejný limit 40 % na cesty i les (cesty se vyhladí díky z_smooth).
        is_on_road = c1 < 1.22 and c2 < 1.22
        max_sklon = 0.40
        min_sklon = -0.40
        sklon = max(min_sklon, min(max_sklon, sklon))
        
        if sklon > 0.02:
            sklon_efektivni = sklon - 0.02
            # Mírná penalizace kopců (cesta do kopce < les po rovině)
            lin_penalta = val_kopce * 1.5 * sklon_efektivni
            if sklon_efektivni > 0.15:
                exp_penalta = val_kopce * 5.0 * ((sklon_efektivni - 0.15) ** 1.5)
            else:
                exp_penalta = 0.0
            hm = 1.0 + lin_penalta + exp_penalta
        elif sklon < -0.02:
            limit_zrychleni = -0.25
            if sklon >= limit_zrychleni:
                hm = 1.0 + (sklon * 0.5)
            else:
                maximalni_zrychleni = 1.0 + (limit_zrychleni * 0.5)
                prebytek_sklonu = abs(sklon) - abs(limit_zrychleni)
                hm = maximalni_zrychleni + (prebytek_sklonu * 1.5)
        else:
            hm = 1.0
            
        step_effort_base = dist_m * terren_cost * hm
        step_effort_algo = step_effort_base
        
        if is_runner_on_road and is_runner_next_road:
            step_effort_algo *= 0.95  # bylo 0.87 - snizen agresivni bonus za cestu
            road_dist += dist_m
        elif is_runner_on_road and not is_runner_next_road:
            step_effort_algo += dist_m * 0.15
            
        usili += step_effort_algo
        usili_real += step_effort_base
        
    road_ratio = road_dist / vzd if vzd > 0 else 0.0
    return vzd, prev, usili, usili_real, road_ratio

def vypocti_cas(usili_real, zakladni_tempo_min, zakladni_tempo_sec):
    # Zakladni tempo je zadano v min a sec na kilometr na idealni ceste (coz ma cost 0.965)
    # Z usili_real (ktere je v podstate modifikovana vzdalenost vc. prevyseni a podkladu) 
    # dostaneme celkovy cas.
    # Zakladni tempo v sekundach na metr:
    sec_per_km = zakladni_tempo_min * 60 + zakladni_tempo_sec
    sec_per_m = sec_per_km / 1000.0
    
    # usili_real je usili v metrech s prihlednutim k terenu a prevyseni
    # Nyní se vše počítá vůči zpevněné cestě s koeficientem 1.00 (předtím to byla lesní cesta 0.965).
    # Takže usili_real se rovnou násobí základním časem v sec/m.
    celkove_sekundy = usili_real * sec_per_m
    return celkove_sekundy

def formatuj_cas(sekundy):
    minuty = int(sekundy // 60)
    zbyvajici_sekundy = int(sekundy % 60)
    return f"{minuty}:{zbyvajici_sekundy:02d}"
