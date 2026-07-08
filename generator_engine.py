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

def dijkstra_heatmap(grid, elev, source, mask, gs, nasobic_meritka, kopce_vaha=25.0, direction='forward'):
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
            wall_check = grid[mid_y, mid_x] < 9000.0
            cy = cy[wall_check]
            cx = cx[wall_check]
            ny = ny[wall_check]
            nx = nx[wall_check]
            mid_y = mid_y[wall_check]
            mid_x = mid_x[wall_check]
            terren_cost = grid[cy, cx] * 0.2 + grid[mid_y, mid_x] * 0.3 + grid[ny, nx] * 0.5
        else:
            terren_cost = grid[cy, cx] * 0.35 + grid[ny, nx] * 0.65
            
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
        hill_multiplier[up_mask] += (sklon_ef * kopce_vaha)
        
        down_mask = sklon < -0.05
        sklon_down = -sklon[down_mask] - 0.05
        hill_multiplier[down_mask] += (sklon_down * (kopce_vaha * 0.3))
        
        final_cost = terren_cost * hill_multiplier * dist_m

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
        cesta.append((cy, cx))
        ny, nx = parents_y[cy, cx], parents_x[cy, cx]
        if ny == -1 or nx == -1:
            return None
        cy, cx = ny, nx
        steps += 1
        
    cesta.append((sy, sx))
    cesta.reverse()
    return cesta


def vyhlad_cestu(cesta, grid, vyhlazeni=3):
    if len(cesta) < 3 or vyhlazeni < 1:
        return cesta

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
                    best_jump = jump
                    break
                    
        i += best_jump
        vyhlazena.append(cesta[i])
        
    return vyhlazena

def penalizuj_grid(grid, trasa, sirka_px):
    h, w = grid.shape
    grid_pen = grid.copy()

    total_pts = len(trasa)
    if total_pts == 0:
        return grid_pen

    trasa_maska = np.zeros((h, w), dtype=bool)
    ochrana = max(5, int(total_pts * 0.20)) 
    
    for i in range(ochrana, total_pts - ochrana):
        py, px = trasa[i]
        y_int = max(0, min(h - 1, int(py)))
        x_int = max(0, min(w - 1, int(px)))
        trasa_maska[y_int, x_int] = True

    if not np.any(trasa_maska):
        py, px = trasa[total_pts // 2]
        trasa_maska[max(0, min(h-1, int(py))), max(0, min(w-1, int(px)))] = True

    struct = np.ones((3, 3), dtype=bool)
    iteraci = max(1, sirka_px // 2)
    zona = binary_dilation(trasa_maska, structure=struct, iterations=iteraci)

    y_start, x_start = trasa[0]
    y_cil, x_cil = trasa[-1]
    
    ochranny_polomer = max(15, int(total_pts * 0.20))
    
    Y, X = np.ogrid[:h, :w]
    zona[(Y - y_start)**2 + (X - x_start)**2 < ochranny_polomer**2] = False
    zona[(Y - y_cil)**2 + (X - x_cil)**2 < ochranny_polomer**2] = False

    grid_pen[zona] *= 1.10
    return grid_pen


def merit_podobnost(cesta_nova, prijate_cesty, h, w, radius):
    if not prijate_cesty:
        return 0.0
    maska = np.zeros((h, w), dtype=bool)
    r = radius
    for co in prijate_cesty:
        for py, px in co[::4]:
            y, x = int(py), int(px)
            maska[
                max(0, y - r): min(h, y + r + 1),
                max(0, x - r): min(w, x + r + 1),
            ] = True
    nova_arr = np.array(cesta_nova, dtype=int)
    py = np.clip(nova_arr[:, 0], 0, h - 1)
    px = np.clip(nova_arr[:, 1], 0, w - 1)
    sdil = np.sum(maska[py, px])
    return sdil / max(1, len(cesta_nova))
