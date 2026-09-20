import numpy as np
from scipy.ndimage import binary_dilation, gaussian_filter

def vytvor_masku_elipsy(start, goal, h, w, rozsireni=0.45):
    """
    Vektorizovana tvorba binarni masky povolene oblasti (elipsa).
    """
    y0, x0 = start
    y1, x1 = goal

    Y, X = np.ogrid[:h, :w]
    
    dist_start = np.sqrt((X - x0)**2 + (Y - y0)**2)
    dist_goal  = np.sqrt((X - x1)**2 + (Y - y1)**2)
    
    dist_centers = np.sqrt((x1 - x0)**2 + (y1 - y0)**2)
    if dist_centers == 0:
        dist_centers = 1.0 
        
    mask = (dist_start + dist_goal) <= (dist_centers * (1.0 + rozsireni))
    return mask

def dijkstra_heatmap(grid, elev, source, mask, gs, nasobic_meritka, kopce_vaha=5.0, direction='forward', crossing_grid=None):
    """
    Vektorizovana Dijkstra expanze pres celou povolenou oblast.
    """
    h, w = grid.shape
    sy, sx = source

    DIRECTIONS = [
        (0, 1, gs, False), (1, 0, gs, False), (0, -1, gs, False), (-1, 0, gs, False),
        (1, 1, gs * 1.4142, False), (-1, 1, gs * 1.4142, False), 
        (1, -1, gs * 1.4142, False), (-1, -1, gs * 1.4142, False),
        (1, 2, gs * 2.2361, True), (2, 1, gs * 2.2361, True),
        (-1, 2, gs * 2.2361, True), (-2, 1, gs * 2.2361, True),
        (1, -2, gs * 2.2361, True), (2, -1, gs * 2.2361, True),
        (-1, -2, gs * 2.2361, True), (-2, -1, gs * 2.2361, True)
    ]

    y_coords, x_coords = np.nonzero(mask)

    row_indices = []
    col_indices = []
    data_weights = []
    
    for dy, dx, step_dist, is_knight in DIRECTIONS:
        valid = (y_coords + dy >= 0) & (y_coords + dy < h) & (x_coords + dx >= 0) & (x_coords + dx < w)
        cy = y_coords[valid]
        cx = x_coords[valid]
        ny = cy + dy
        nx = cx + dx
        
        valid_dest = mask[ny, nx]
        cy = cy[valid_dest]
        cx = cx[valid_dest]
        ny = ny[valid_dest]
        nx = nx[valid_dest]
        
        if len(cy) == 0:
            continue

        if is_knight:
            mid_y = cy + (dy // 2)
            mid_x = cx + (dx // 2)
            mid_y2 = cy + (dy - dy // 2)
            mid_x2 = cx + (dx - dx // 2)
            # Kontrolujeme OBE stredni bunky rytirskych skoku (prev. pruchod stikem)
            wall_check = (grid[mid_y, mid_x] < 9000.0) & (grid[mid_y2, mid_x2] < 9000.0)
            cy = cy[wall_check]
            cx = cx[wall_check]
            ny = ny[wall_check]
            nx = nx[wall_check]
            mid_y = mid_y[wall_check]
            mid_x = mid_x[wall_check]
            terren_cost = grid[cy, cx] * 0.5 + grid[ny, nx] * 0.5  # symetricky prumer
        else:
            terren_cost = grid[cy, cx] * 0.5 + grid[ny, nx] * 0.5  # symetricky prumer (bylo 0.35/0.65)
            
        valid_terren = terren_cost < 9000.0
        cy = cy[valid_terren]
        cx = cx[valid_terren]
        ny = ny[valid_terren]
        nx = nx[valid_terren]
        terren_cost = terren_cost[valid_terren]
        if is_knight:
            mid_y = mid_y[valid_terren]
            mid_x = mid_x[valid_terren]
        
        if len(cy) == 0:
            continue

        if direction == 'forward':
            dz = elev[ny, nx] - elev[cy, cx]
        else:
            dz = elev[cy, cx] - elev[ny, nx]

        dist_m = step_dist * nasobic_meritka
        sklon = dz / dist_m
        hill_multiplier = np.ones_like(sklon)
        
        up_mask = sklon > 0.02
        sklon_ef = sklon[up_mask] - 0.02
        lin_penalta = kopce_vaha * 1.5 * sklon_ef
        exp_penalta = np.zeros_like(sklon_ef)
        
        steep = sklon_ef > 0.15
        if np.any(steep):
            exp_penalta[steep] = kopce_vaha * 5.0 * ((sklon_ef[steep] - 0.15) ** 1.5)
        hill_multiplier[up_mask] = 1.0 + lin_penalta + exp_penalta
        
        down_mask = sklon < -0.02
        sklon_down = sklon[down_mask]
        limit_zrychleni = -0.25
        
        mild_down = sklon_down >= limit_zrychleni
        steep_down = ~mild_down
        
        hm_down = np.empty_like(sklon_down)
        hm_down[mild_down] = 1.0 + (sklon_down[mild_down] * 0.5)
        
        maximalni_zrychleni = 1.0 + (limit_zrychleni * 0.5)
        prebytek_sklonu = np.abs(sklon_down[steep_down]) - np.abs(limit_zrychleni)
        hm_down[steep_down] = maximalni_zrychleni + (prebytek_sklonu * 1.5)
        hill_multiplier[down_mask] = hm_down
        
        final_cost = terren_cost * hill_multiplier * dist_m
        
        # Psychologicka lepivost cest (Path Stickiness)
        # Pokud bezec stoji na ceste (odpor <= 1.15) a dalsi krok vede mimo cestu do lesa/hustniku (odpor > 1.15),
        # dostane jednorazovou penalizaci ekvivalentni cca 5 vterinam (15 metru).
        # Algoritmus tak neopusti cestu kvuli par vterinam zkratky.
        cost_current = grid[cy, cx]
        cost_next = grid[ny, nx]
        leaves_path = (cost_current <= 1.15) & (cost_next > 1.15)
        final_cost = final_cost + (leaves_path * 15.0)

        # Additivni penalizace za krizovani liniove prekazky (prikop, sraz)
        # Pridate se cena prekazky k cene hrany jako ekvivalentni metry
        if crossing_grid is not None:
            cross_pen = np.maximum(crossing_grid[cy, cx], crossing_grid[ny, nx])
            final_cost = final_cost + cross_pen * nasobic_meritka

        u = cy * w + cx
        v = ny * w + nx
        row_indices.append(u)
        col_indices.append(v)
        data_weights.append(final_cost)

    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra as sp_dijkstra
    
    N = h * w
    if not row_indices:
        return np.full((h, w), np.inf, dtype=np.float64), np.full((h, w), -1, dtype=np.int32), np.full((h, w), -1, dtype=np.int32)
        
    row_arr = np.concatenate(row_indices)
    col_arr = np.concatenate(col_indices)
    data_arr = np.concatenate(data_weights)
    
    adj = coo_matrix((data_arr, (row_arr, col_arr)), shape=(N, N)).tocsr()
    source_idx = sy * w + sx
    
    dist, preds = sp_dijkstra(adj, directed=True, indices=source_idx, return_predecessors=True)
    dist_map = dist.reshape((h, w))
    
    py = preds // w
    px = preds % w
    py[preds == -9999] = -1
    px[preds == -9999] = -1
    
    return dist_map, py.reshape((h, w)), px.reshape((h, w))


def trasuj_cestu(parents_y, parents_x, start, goal):
    """
    Zpetne trasovani pomoci predchudcu.
    """
    cesta = []
    cy, cx = goal
    sy, sx = start
    
    max_steps = parents_y.shape[0] * parents_y.shape[1]
    steps = 0
    while (cy != sy or cx != sx) and steps < max_steps:
        cesta.append((int(cy), int(cx)))
        ny, nx = parents_y[cy, cx], parents_x[cy, cx]
        if ny == -1 or nx == -1:
            return None
        cy, cx = ny, nx
        steps += 1
        
    cesta.append((int(sy), int(sx)))
    cesta.reverse()
    return cesta


def vyhlad_cestu(cesta, grid, vyhlazeni=3):
    if len(cesta) < 3 or vyhlazeni < 1:
        return cesta

    h, w = grid.shape
    vyhlazena = [cesta[0]]
    i = 0
    N = len(cesta)
    
    while i < N - 1:
        best_jump = 1
        for jump in range(vyhlazeni + 1, 1, -1):
            if i + jump < N:
                pt1 = cesta[i]
                pt2 = cesta[i + jump]
                steps = max(abs(pt2[0]-pt1[0]), abs(pt2[1]-pt1[1]))
                
                wall_hit = False
                for step in range(1, steps):
                    r = int(pt1[0] + step * (pt2[0]-pt1[0]) / steps)
                    c = int(pt1[1] + step * (pt2[1]-pt1[1]) / steps)
                    if grid[r, c] > 1.8:
                        wall_hit = True
                        break
                        
                if not wall_hit:
                    # Ochrana cest: pokud puvodni usek vede po ceste/pesine,
                    # nepovolime zkratku ktera opousti cestu do lesa
                    on_road = True
                    for k in range(jump + 1):
                        idx = i + k
                        if idx >= N:
                            break
                        ry = max(0, min(h - 1, int(cesta[idx][0])))
                        rx = max(0, min(w - 1, int(cesta[idx][1])))
                        if grid[ry, rx] >= 1.22:
                            on_road = False
                            break
                    
                    if on_road and steps > 0:
                        leaves_road = False
                        for step in range(1, steps):
                            r = int(pt1[0] + step * (pt2[0]-pt1[0]) / steps)
                            c = int(pt1[1] + step * (pt2[1]-pt1[1]) / steps)
                            r = max(0, min(h - 1, r))
                            c = max(0, min(w - 1, c))
                            if grid[r, c] >= 1.22:
                                leaves_road = True
                                break
                        if leaves_road:
                            continue  # Preskocime tento skok, zkusime kratsi
                    
                    best_jump = jump
                    break
                    
        i += best_jump
        vyhlazena.append(cesta[i])
        
    return vyhlazena

def rozbij_primky(cesta, grid, meritko_m, max_len_m=50, max_offset_m=5.0, max_cost=1.25):
    """
    Geometricky naruší dlouhé rovné úseky (např. v bílém lese = cost <= 1.25).
    Pokud algoritmus běží více než max_len_m po přímce, vychýlí se o max_offset_m.
    Ověřuje, zda ve směru vychýlení není neprůchodný objekt (kupka, hustník = cost > max_cost).
    """
    if len(cesta) < 10:
        return cesta
        
    h, w = grid.shape
    vysledek = [cesta[0]]
    sign = 1.0
    
    # Udržujeme sledovaný rovný úsek
    start_idx = 0
    
    for i in range(1, len(cesta)):
        p_start = cesta[start_idx]
        p_curr = cesta[i]
        
        # Geometrická vzdálenost od startu úseku
        dist = np.hypot(p_curr[0]-p_start[0], p_curr[1]-p_start[1]) * meritko_m
        
        # Zkontrolujeme, zda se trasa už přirozeně nezalomila
        # (skutečná ujetá vzdálenost vs vzdušná vzdálenost na úseku)
        ujeta_vzdalenost = 0
        for k in range(start_idx, i):
            ujeta_vzdalenost += np.hypot(cesta[k+1][0]-cesta[k][0], cesta[k+1][1]-cesta[k][1]) * meritko_m
            
        if ujeta_vzdalenost > dist * 1.1:
            # Trasa se zalomila přirozeně, resetujeme sledování
            for k in range(start_idx + 1, i + 1):
                vysledek.append(cesta[k])
            start_idx = i
            continue
            
        if dist >= max_len_m:
            # Kontrola, jestli aspoň jeden bod neleží na rychlém povrchu (např. silnice, pěšina).
            # Bílý les má cost 1.22. Pokud je cost < 1.22, jde o cestu nebo rychlý průsek.
            je_na_rychlem_povrchu = False
            for k in range(start_idx, i + 1):
                cy = int(np.clip(cesta[k][0], 0, h - 1))
                cx = int(np.clip(cesta[k][1], 0, w - 1))
                if grid[cy, cx] < 1.22:
                    je_na_rychlem_povrchu = True
                    break
                    
            if je_na_rychlem_povrchu:
                # Trasa běží (byť částečně) po cestě/průseku. Přímku zachováme.
                for k in range(start_idx + 1, i + 1):
                    vysledek.append(cesta[k])
                start_idx = i
                continue
                
            # Máme dlouhou přímku v pomalém lese! Najdeme její prostředek (na indexu i-dist//2)
            mid_idx = (start_idx + i) // 2
            
            p1 = cesta[start_idx]
            p2 = cesta[i]
            
            # Směr vektoru
            dy = p2[0] - p1[0]
            dx = p2[1] - p1[1]
            L = np.hypot(dy, dx)
            
            if L > 0:
                ny, nx = -dx / L, dy / L
                offset_px = max_offset_m / meritko_m
                
                # Zkusíme stranu A
                ty1 = int(np.clip(cesta[mid_idx][0] + ny * offset_px * sign, 0, h-1))
                tx1 = int(np.clip(cesta[mid_idx][1] + nx * offset_px * sign, 0, w-1))
                
                # Zkusíme stranu B
                ty2 = int(np.clip(cesta[mid_idx][0] - ny * offset_px * sign, 0, h-1))
                tx2 = int(np.clip(cesta[mid_idx][1] - nx * offset_px * sign, 0, w-1))
                
                best_y, best_x = -1, -1
                
                # Jsou cílové body v "bílém lese" (tj. žádné hustníky a kupky)?
                safe1 = grid[ty1, tx1] <= max_cost
                safe2 = grid[ty2, tx2] <= max_cost
                
                if safe1:
                    best_y, best_x = ty1, tx1
                elif safe2:
                    best_y, best_x = ty2, tx2
                    sign = -sign  # Pokud se musel vyhnout na druhou, otočíme budoucí fázi
                
                # Pokud jsme našli bezpečný offset, přidáme body do výsledku a zlomíme to
                if best_y != -1:
                    # Body před středem
                    for k in range(start_idx + 1, mid_idx):
                        vysledek.append(cesta[k])
                    # Vložíme "zlom"
                    vysledek.append((best_y, best_x))
                    # Body za středem
                    for k in range(mid_idx + 1, i + 1):
                        vysledek.append(cesta[k])
                        
                    sign = -sign # Střídání levá/pravá
                    start_idx = i
                    continue
                    
            # Pokud se to nepovedlo vychýlit (z obou stran je zeď/hustník), pokračujeme normálně
            for k in range(start_idx + 1, i + 1):
                vysledek.append(cesta[k])
            start_idx = i
            
    # Přidání zbylých bodů
    for k in range(start_idx + 1, len(cesta)):
        vysledek.append(cesta[k])
        
    return vysledek


def penalizuj_grid(grid_pen_in, trasa, sirka_px, grid=None):
    """
    Zdrazuje oblast kolem trasy v penalizovanem gridu.
    grid_pen_in: grid ktery se bude menit (kopia cost_grid uz mozna penalizovana)
    grid:        puvodni cost_grid pro terrain-aware rozhodovani (volitelny)
                 Pokud je predany, cesty a pesiny (cost < 0.87) se nepenalizuji.
    """
    h, w = grid_pen_in.shape
    grid_pen = grid_pen_in.copy()

    total_pts = len(trasa)
    if total_pts == 0:
        return grid_pen

    trasa_maska = np.zeros((h, w), dtype=bool)
    ochrana = max(5, int(total_pts * 0.20))

    for i in range(ochrana, total_pts - ochrana):
        py, px = trasa[i]
        y_int = max(0, min(h - 1, int(py)))
        x_int = max(0, min(w - 1, int(px)))
        # Nepenalizujeme cesty a pesiny (cost < 1.22) -- tam je sdileni prirozene.
        # Zdrazujeme pouze lesni/terenni bunky, kde existuje skutecna volba postupu.
        if grid is None or grid[y_int, x_int] >= 1.22:
            trasa_maska[y_int, x_int] = True

    if not np.any(trasa_maska):
        py, px = trasa[total_pts // 2]
        trasa_maska[max(0, min(h-1, int(py))), max(0, min(w-1, int(px)))] = True

    struct = np.ones((3, 3), dtype=bool)
    iteraci = max(1, sirka_px // 2)
    zona = binary_dilation(trasa_maska, structure=struct, iterations=iteraci)

    # Ochranný radius kolem startu a cile (tam nikdy penalizace)
    y_start, x_start = trasa[0]
    y_cil, x_cil = trasa[-1]
    ochranny_polomer = max(15, int(total_pts * 0.20))
    Y, X = np.ogrid[:h, :w]
    zona[(Y - y_start)**2 + (X - x_start)**2 < ochranny_polomer**2] = False
    zona[(Y - y_cil)**2 + (X - x_cil)**2 < ochranny_polomer**2] = False

    # Finalni ochrana: nepsat penalizaci na cestni bunky ani pres dilataci zony
    if grid is not None:
        zona[grid < 1.22] = False

    grid_pen[zona] *= 1.35  # Mierne zvyseno (bylo 1.30) -- kompenzace za mensi plochu penalizace
    return grid_pen


def analyzuj_podobnost(cesta_nova, prijate_cesty, meritko_m, threshold_m=25.0):
    """
    Vrátí metriky podobnosti mezi novou cestou a všemi přijatými cestami.
    Vrací tuple: (max_rozkol_m, avg_rozkol_m, shared_ratio)
    - max_rozkol_m: Maximální vzdálenost 'břicha' (jako původní max_rozkol)
    - avg_rozkol_m: Průměrná odlehlost varianty (pro zajímavost)
    - shared_ratio: Kolik procent délky (0.0 až 1.0) leží blíže než threshold_m od jakékoliv staré cesty.
    """
    if not prijate_cesty:
        return 9999.0, 9999.0, 0.0
        
    from scipy.spatial import cKDTree
    vsechny_body = []
    for c in prijate_cesty:
        # Krokujeme po 2 bodech pro rychlost
        vsechny_body.extend(c[::2])
        
    if not vsechny_body: 
        return 9999.0, 9999.0, 0.0
        
    tree = cKDTree(vsechny_body)
    nova_body = cesta_nova[::2]
    if not nova_body:
        return 0.0, 0.0, 1.0
    
    # Pro každý bod nové cesty najdeme nejbližší bod ze všech přijatých cest
    distances, _ = tree.query(nova_body)
    
    max_dist_px = np.max(distances)
    avg_dist_px = np.mean(distances)
    
    threshold_px = threshold_m / meritko_m
    shared_points = np.sum(distances < threshold_px)
    shared_ratio = shared_points / len(nova_body)
    
    return max_dist_px * meritko_m, avg_dist_px * meritko_m, float(shared_ratio)

def zjisti_narocnost_primky(p1, p2, cost_grid, elev_grid, grid_size, nasobic_meritka, louka_mask=None):
    """
    Vyhodnotí přímý směr a vrátí Obstacle Score (čím vyšší, tím zajímavější překážka).
    Zahrnuje převýšení (priorita), hustníky, detekci blízkých cest (Asfaltový magnet) 
    a omezuje postupy jdoucí velkou část přes louku.
    """
    h, w = cost_grid.shape
    dist_grid = np.sqrt((p1['gx'] - p2['gx'])**2 + (p1['gy'] - p2['gy'])**2)
    if dist_grid < 1:
        return -1.0

    n_points = int(dist_grid * 2) # vzorkování 2x na buňku
    if n_points < 2:
        n_points = 2

    y_coords = np.linspace(p1['gy'], p2['gy'], n_points)
    x_coords = np.linspace(p1['gx'], p2['gx'], n_points)
    
    y_int = np.clip(y_coords.astype(int), 0, h - 1)
    x_int = np.clip(x_coords.astype(int), 0, w - 1)

    costs = cost_grid[y_int, x_int]
    elevs = elev_grid[y_int, x_int]

    # 1. KOPEC/ÚDOLÍ SKÓRE (Přeběh přes překážku)
    elev_diffs = np.diff(elevs)
    elev_gain = np.sum(elev_diffs[elev_diffs > 0])
    elev_loss = np.sum(np.abs(elev_diffs[elev_diffs < 0]))
    
    dist_m = dist_grid * grid_size * nasobic_meritka
    if dist_m < 50:
        return -1.0
        
    # K oběhnutí musí překážka stát v cestě = nahoru i dolů.
    elev_crossing = min(elev_gain, elev_loss)
    # Nastoupané/naklesané metry přes překážku přepočítané na km. 
    # Extrémní váha 10.0, protože tohle dělá ty nejlepší volby postupů.
    kopec_skore = (elev_crossing / (dist_m / 1000.0)) * 10.0

    # 2. HUSTNÍK SKÓRE (Zábrana uprostřed)
    # Bereme jen 10% až 90% délky postupu, aby to nebyly jen hustníky na samotné kontrole.
    start_idx = int(n_points * 0.1)
    end_idx = int(n_points * 0.9)
    if start_idx < end_idx:
        costs_middle = costs[start_idx:end_idx]
    else:
        costs_middle = costs

    # Zastropujeme vodu na 3.0 (temný hustník)
    valid_costs = np.clip(costs_middle, 0, 3.0)
    avg_cost = np.mean(valid_costs)
    
    # Detekce opravdu ošklivých kousků (Hustník 2 a víc, tj. > 2.0)
    thicket_ratio = np.sum(valid_costs >= 2.0) / len(valid_costs) if len(valid_costs) > 0 else 0
    
    # Skóre je kombinace průměrné zhoršené průchodnosti a bonusu za extrémní hustník
    hustnik_skore = max(0.0, avg_cost - 1.17) * 100.0 + (thicket_ratio * 300.0)

    # 3. ASFALTOVÝ MAGNET
    # Hustota cest v širším obdélníku kolem postupu (cca 200m = 40 buněk)
    padding_cells = 40
    y_min = max(0, min(p1['gy'], p2['gy']) - padding_cells)
    y_max = min(h, max(p1['gy'], p2['gy']) + padding_cells)
    x_min = max(0, min(p1['gx'], p2['gx']) - padding_cells)
    x_max = min(w, max(p1['gx'], p2['gx']) + padding_cells)
    
    subgrid = cost_grid[y_min:y_max, x_min:x_max]
    if subgrid.size > 0:
        # Hledáme zpevněné cesty, lesní cesty a pěšiny (cost <= 1.11)
        asfalt_pixels = np.sum(subgrid <= 1.11) 
        road_ratio = asfalt_pixels / subgrid.size
        # Pokud je v oblasti víc jak 5% cest, dostane max bonus 30 bodů
        asfalt_skore = min(road_ratio * 20.0, 1.0) * 30.0
    else:
        asfalt_skore = 0.0

    # 4. LOUKA PENALIZACE (Zákaz běhání přes otevřené prostory)
    # Zkontrolujeme, kolik procent ze středních 80 % přímky leží na louce
    louka_penalizace = 0.0
    if louka_mask is not None:
        if start_idx < end_idx:
            l_mask_middle = louka_mask[y_int[start_idx:end_idx], x_int[start_idx:end_idx]]
        else:
            l_mask_middle = louka_mask[y_int, x_int]
            
        if len(l_mask_middle) > 0:
            louka_ratio = np.sum(l_mask_middle) / len(l_mask_middle)
            
            # Povolíme více louky u dlouhých postupů, kde se jí těžko vyhýbá
            dist_m = dist_grid * grid_size * nasobic_meritka
            max_louka = 0.40 if dist_m > 1200 else 0.25
            
            # Pokud přímka běží víc než dovoleno po louce, brutálně ji penalizujeme
            if louka_ratio > max_louka:
                louka_penalizace = -1000.0

    total_score = kopec_skore + hustnik_skore + asfalt_skore + louka_penalizace
    return total_score


def snap_na_cesty(cesta, grid, road_lines_grid, max_snap=1.5):
    """
    Vizualni snap: body trasy ktere lezi na ceste/pesine (cost < 1.05)
    se posunuou na nejblizsi OMAP vektorovou osu cesty.
    Lesni useky zustavaji beze zmeny. Metriky se nepocitaji z tohoto
    vystupu, takze to neovlivni zadne vypocty.
    
    cesta: list of (gy, gx) grid coordinates
    grid: cost grid
    road_lines_grid: list of Shapely LineString v grid souradnicich
    max_snap: max vzdalenost snapu v bunkach gridu (default 1.5 = 7.5m)
    """
    if not road_lines_grid or len(cesta) < 2:
        return cesta

    from shapely.geometry import Point as ShapelyPoint
    from shapely.strtree import STRtree

    tree = STRtree(road_lines_grid)

    h, w = grid.shape
    result = list(cesta)  # kopie - original zustava nezmenen

    for i in range(1, len(result) - 1):  # Start a cil nesnappujeme
        gy, gx = result[i]
        y_int = max(0, min(h - 1, int(gy)))
        x_int = max(0, min(w - 1, int(gx)))

        # Snap jen na cestach/pesinach
        if grid[y_int, x_int] > 1.05:
            continue

        pt = ShapelyPoint(gx, gy)

        # Nejblizsi cesta (Shapely STRtree)
        nearest_idx = tree.nearest(pt)
        nearest_line = road_lines_grid[nearest_idx]
        proj_dist = nearest_line.project(pt)
        nearest_pt = nearest_line.interpolate(proj_dist)

        dist = pt.distance(nearest_pt)
        if dist < max_snap:
            result[i] = (nearest_pt.y, nearest_pt.x)

    return result
