import re

with open('6_finalni_stavitel.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove import itertools
content = content.replace('import math\nimport itertools', 'import math')

# Revert astar function
old_astar = """def astar(grid, start, goal):
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
    open_set = []
    heapq.heappush(open_set, (0.0, start))
    came_from = {}
    g_score = {start: 0.0}

    y1, x1 = start
    y2, x2 = goal
    delka_cary = math.hypot(x2 - x1, y2 - y1)
    sila_azimutu = 0.0015  # Silnejsi magnetismus k cili = mene divokych odbocek

    while open_set:
        _, current = heapq.heappop(open_set)
        if current == goal:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()
            return path

        cy, cx = current
        
        prev_node = came_from.get(current)
        if prev_node:
            prev_dy = cy - prev_node[0]
            prev_dx = cx - prev_node[1]
        else:
            prev_dy, prev_dx = 0, 0

        for dy, dx, dist in directions:
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < height and 0 <= nx < width:
                # Použijeme průměr ceny z aktuální a cílové buňky. Zabrání to 
                # umělým zubatým odskokům z lesa na cestu, protože skok na 
                # cestu bude stát i polovinu ceny lesa, odkud běžec odskakuje.
                terren_cost = (grid[ny, nx] + grid[cy, cx]) / 2.0

                if terren_cost >= 9000.0:
                    continue

                is_next_road = terren_cost < 1.05
                is_current_road = grid[cy, cx] < 1.05
                dz = elev_grid[ny, nx] - elev_grid[cy, cx]
                sklon = dz / dist

                if sklon > 0:
                    hill_multiplier = 1.0 + (sklon * 0.5) + (25.0 * (sklon ** 2))
                elif sklon < 0:
                    limit_zrychleni = -0.40
                    if sklon >= limit_zrychleni:
                        hill_multiplier = 1.0 + (sklon * 0.4)
                    else:
                        maximalni_zrychleni = 1.0 + (limit_zrychleni * 0.7)
                        prebytek_sklonu = abs(sklon) - abs(limit_zrychleni)
                        hill_multiplier = maximalni_zrychleni + (prebytek_sklonu * 1.1)
                else:
                    hill_multiplier = 1.0

                if delka_cary > 0:
                    odklon_px = (
                        abs((x2 - x1) * (y1 - ny) - (x1 - nx) * (y2 - y1)) / delka_cary
                    )
                else:
                    odklon_px = 0

                # Velmi jemna penalizace za vyboceni (max 15% prirazka), aby se vyplatilo obihat po ceste
                magnet_multiplier = 1.0 + min(0.15, odklon_px * sila_azimutu)
                
                turn_penalty = 0.0
                if is_current_road and is_next_road and prev_node:
                    if dy != prev_dy or dx != prev_dx:
                        turn_penalty = dist * 0.05
                        
                step_effort = (dist * terren_cost * hill_multiplier * magnet_multiplier) + turn_penalty

                # if is_current_road and not is_next_road:
                #     step_effort += PENALIZACE_OPUSTENI_CESTY

                tentative_g = g_score[current] + step_effort

                if (ny, nx) not in g_score or tentative_g < g_score[(ny, nx)]:
                    came_from[(ny, nx)] = current
                    g_score[(ny, nx)] = tentative_g
                    # Akcelerace A* (Weighted A*): Zvýšeno na 0.95. Tím algoritmus poběží mnohonásobně rychleji,
                    # protože se chová mnohem směrověji, namísto slepého prohledávání kruhu jako u Dijkstry.
                    h = math.hypot(goal[1] - nx, goal[0] - ny) * grid_size * 0.95
                    heapq.heappush(open_set, (tentative_g + h, (ny, nx)))

    return None"""

pattern_astar = re.compile(r'def astar\(grid, start, goal, allow_detours=False\):.*?return None', re.DOTALL)
content = pattern_astar.sub(old_astar, content)

# Revert spocitat_trasy loop
old_loop = """        print(f"   Generuji pool {POCET_GENERACI} prirozenych tras pomoci sumu...", flush=True)
        for gen_i in range(POCET_GENERACI):
            cesta_multiplier = 1.0  # Výchozí hodnota masky pro rychlé cesty
            
            # --- IMPLEMENTACE PROFILŮ BĚŽCŮ ---
            if gen_i % 3 == 0:
                # Profil "Hrubá síla": Les je zlevněn
                noise = rng.uniform(0.9, 1.1, working_grid_base.shape).astype(np.float32)
                noise = np.where(working_grid_base >= 1.05, noise * 0.8, noise)
            elif gen_i % 3 == 1:
                # Profil "Silničář": Extrémně zlevníme cesty pro prohledání dlouhých taktických obíhaček
                noise = rng.uniform(0.9, 1.1, working_grid_base.shape).astype(np.float32)
                cesta_multiplier = 0.55  # Snížíme náročnost cest (např. na 55 %), místo zdražování lesa
            else:
                # Profil "Normální variabilita"
                noise = rng.uniform(0.8, 1.3, working_grid_base.shape).astype(np.float32)

            # TERRAIN MASKING (Imunita liniových objektů):
            # Kde je cost < 1.05 (cesty), nahradíme šum konstantou (cesta_multiplier).
            # Zabrání se tak vzniku mikro-nerovností na cestách, a umožní zlevnění obíhaček.
            noise_maskovany = np.where(working_grid_base < 1.05, cesta_multiplier, noise)

            wg = np.where(working_grid_base < 9000.0, working_grid_base * noise_maskovany, working_grid_base)

            cesta = astar(wg, (s_y, s_x), (g_y, g_x))
            if cesta is None:
                continue"""

pattern_loop = re.compile(r'print\(f"   Generuji pool \{POCET_GENERACI\} prirozenych tras pomoci sumu...", flush=True\)\n        for gen_i in range\(POCET_GENERACI\):.*?continue', re.DOTALL)
content = pattern_loop.sub(old_loop, content)

with open('6_finalni_stavitel.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Reverted successfully")
