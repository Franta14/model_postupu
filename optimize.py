import re

with open('6_finalni_stavitel.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'import itertools' not in content:
    content = content.replace('import math', 'import math\nimport itertools')

new_astar = """def astar(grid, start, goal, allow_detours=False):
    height, width = grid.shape
    directions = [
        (0, 1, grid_size),
        (1, 0, grid_size),
        (0, -1, grid_size),
        (-1, 0, grid_size),
        (1, 1, grid_size * 1.414),
        (-1, 1, grid_size * 1.414),
        (1, -1, grid_size * 1.414),
        (-1, -1, grid_size * 1.414),
    ]
    
    # Rychlejší 1D pole (seznam) místo slovníků pro extrémně rychlý lookup v Pythonu
    total_cells = height * width
    g_score = [float('inf')] * total_cells
    came_from = [-1] * total_cells
    
    y1, x1 = start
    y2, x2 = goal
    start_idx = y1 * width + x1
    g_score[start_idx] = 0.0
    
    open_set = []
    counter = itertools.count()
    heapq.heappush(open_set, (0.0, next(counter), start))
    
    # Předvýpočet konstant
    dx_cary = x2 - x1
    dy_cary = y2 - y1
    delka_cary = math.hypot(dx_cary, dy_cary)
    sila_azimutu = 0.0015
    inv_delka_cary = 1.0 / delka_cary if delka_cary > 0 else 0.0
    
    heuristic_weight = 0.40 if allow_detours else 0.95
    heur_factor = grid_size * heuristic_weight

    while open_set:
        _, _, current = heapq.heappop(open_set)
        cy, cx = current
        
        if current == goal:
            path = []
            curr_idx = cy * width + cx
            while curr_idx != start_idx:
                py = curr_idx // width
                px = curr_idx % width
                path.append((py, px))
                curr_idx = came_from[curr_idx]
            path.append(start)
            path.reverse()
            return path
            
        curr_idx = cy * width + cx
        current_g = g_score[curr_idx]
        grid_cy_cx = grid[cy, cx]
        elev_cy_cx = elev_grid[cy, cx]
        is_current_road = grid_cy_cx < 1.05
        
        prev_idx = came_from[curr_idx]
        if prev_idx != -1:
            prev_y = prev_idx // width
            prev_x = prev_idx % width
            prev_dy = cy - prev_y
            prev_dx = cx - prev_x
            has_prev = True
        else:
            prev_dy, prev_dx = 0, 0
            has_prev = False

        for dy, dx, dist in directions:
            ny = cy + dy
            nx = cx + dx
            
            if 0 <= ny < height and 0 <= nx < width:
                grid_ny_nx = grid[ny, nx]
                terren_cost = (grid_ny_nx + grid_cy_cx) * 0.5
                
                if terren_cost >= 9000.0:
                    continue
                
                dz = elev_grid[ny, nx] - elev_cy_cx
                sklon = dz / dist
                
                if sklon > 0:
                    hill_multiplier = 1.0 + (sklon * 0.5) + (25.0 * (sklon * sklon))
                elif sklon < 0:
                    if sklon >= -0.40:
                        hill_multiplier = 1.0 + (sklon * 0.4)
                    else:
                        hill_multiplier = 0.72 + ((abs(sklon) - 0.40) * 1.1)
                else:
                    hill_multiplier = 1.0
                    
                if allow_detours:
                    magnet_multiplier = 1.0
                else:
                    if inv_delka_cary > 0:
                        odklon_px = abs(dx_cary * (y1 - ny) - dy_cary * (x1 - nx)) * inv_delka_cary
                        magnet_multiplier = 1.0 + min(0.15, odklon_px * sila_azimutu)
                    else:
                        magnet_multiplier = 1.0
                        
                turn_penalty = 0.0
                if has_prev and is_current_road and (grid_ny_nx < 1.05):
                    if dy != prev_dy or dx != prev_dx:
                        turn_penalty = dist * 0.05
                        
                step_effort = (dist * terren_cost * hill_multiplier * magnet_multiplier) + turn_penalty
                tentative_g = current_g + step_effort
                
                ny_nx_idx = ny * width + nx
                if tentative_g < g_score[ny_nx_idx]:
                    came_from[ny_nx_idx] = curr_idx
                    g_score[ny_nx_idx] = tentative_g
                    
                    h = math.hypot(x2 - nx, y2 - ny) * heur_factor
                    heapq.heappush(open_set, (tentative_g + h, next(counter), (ny, nx)))
                    
    return None"""

pattern = re.compile(r'def astar\(grid, start, goal, allow_detours=False\):.*?return None', re.DOTALL)
content, num_subs = pattern.subn(new_astar, content)

with open('6_finalni_stavitel.py', 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Updated successfully, {num_subs} replacements made.")
