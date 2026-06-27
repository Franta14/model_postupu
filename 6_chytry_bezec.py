import numpy as np
import matplotlib.pyplot as plt
import heapq
import math
import time

print("🚀 Startuji Chytrého Běžce (A* s fyzikou převýšení)...")

# =====================================================================
# 1. NAČTENÍ DAT (Okamžité načtení z paměti)
# =====================================================================
try:
    cost_grid = np.load('cenova_mapa.npy')
    elev_grid = np.load('vyskova_mapa.npy')
    meta = np.load('cenova_mapa_meta.npy')
    min_x, min_y, max_x, max_y, grid_size = meta
    height, width = cost_grid.shape
except FileNotFoundError:
    print("❌ Chybí .npy soubory. Ujisti se, že jsi spustil Fázi 1 i Fázi 2.")
    exit()

print(f"🗺️ Spojuji Cenovou mapu a 3D model: {width}x{height} políček.")

# =====================================================================
# 2. DEFINICE MOZKU (Algoritmus A* s fyzikou)
# =====================================================================
def astar_search(cost_grid, elev_grid, start_idx, goal_idx):
    # (dy, dx, fyzická_vzdálenost_na_mřížce)
    directions = [
        (0, 1, grid_size), (1, 0, grid_size), (0, -1, grid_size), (-1, 0, grid_size),
        (1, 1, grid_size * 1.414), (-1, 1, grid_size * 1.414), 
        (1, -1, grid_size * 1.414), (-1, -1, grid_size * 1.414)
    ]

    open_set = []
    heapq.heappush(open_set, (0.0, start_idx))
    
    came_from = {}
    g_score = {start_idx: 0.0}
    
    # 🏃‍♂️ PARAMETRY FYZIKY ZÁVODNÍKA
    # Zpevněná cesta má v tvé tabulce hodnotu 0.915
    min_terrain_cost = 0.915 
    PENALIZACE_KOPCE = 10.0  # 1 výškový metr = 10 metrů běhu navíc
    
    def heuristic(node):
        # Heuristika = ideální vzdálenost vzdušnou čarou (bez kopců) * nejrychlejší terén
        vzdalenost = math.hypot(goal_idx[0] - node[0], goal_idx[1] - node[1]) * grid_size
        return vzdalenost * min_terrain_cost

    print("   ⏳ Prohledávám 3D les, analyzuji převýšení a hustníky...")
    start_time = time.time()
    
    while open_set:
        _, current = heapq.heappop(open_set)
        
        if current == goal_idx:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start_idx)
            path.reverse()
            
            print(f"   ✅ Ideální stopa nalezena za {time.time() - start_time:.2f} vteřin!")
            return path, g_score[goal_idx]
            
        cy, cx = current
        current_elev = elev_grid[cy, cx]
        
        for dy, dx, dist_meters in directions:
            ny, nx = cy + dy, cx + dx
            
            if 0 <= ny < height and 0 <= nx < width:
                terrain_cost = cost_grid[ny, nx]
                next_elev = elev_grid[ny, nx]
                
                # Výpočet převýšení pro tento krok
                dz = next_elev - current_elev
                
                # 💡 TOBLEROVA/NAISMITHOVA FUNKCE (Cena kroku)
                elev_penalty = 0
                if dz > 0:
                    elev_penalty = dz * PENALIZACE_KOPCE # Stoupání hrozně bolí
                elif dz < -0.5:
                    elev_penalty = abs(dz) * 2.0 # Prudké klesání taky trochu brzdí (musíš brzdit stehna)
                
                # Finální "Úsilí" na tento krok (Ekvivalent metrů po rovině na cestě)
                step_effort = (dist_meters * terrain_cost) + elev_penalty
                
                tentative_g = g_score[current] + step_effort
                neighbor = (ny, nx)
                
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score = tentative_g + heuristic(neighbor)
                    heapq.heappush(open_set, (f_score, neighbor))
                    
    print("   ❌ Cesta nenalezena (bod je nepřístupný).")
    return None, float('inf')

# =====================================================================
# 3. INTERAKTIVNÍ KLIKÁNÍ DO MAPY
# =====================================================================
print("\n👀 Otevírám mapu...")
print("👉 1. Klikni na START")
print("👉 2. Klikni na CÍL (Ideálně zkus kliknout tak, aby mezi body byl kopec!)")

fig, ax = plt.subplots(figsize=(14, 10))
fig.canvas.manager.set_window_title('Umělý Stavitel Tratí: A* s fyzikou')

# Spojíme vizuálně Terén a Výšku (Hillshade efekt)
dx, dy = np.gradient(elev_grid)
slope = np.pi/2. - np.arctan(np.sqrt(dx*dx + dy*dy))
aspect = np.arctan2(-dy, dx)
azimut = 315.0 * np.pi / 180.0
vyska_slunce = 45.0 * np.pi / 180.0
shaded = np.sin(vyska_slunce)*np.sin(slope) + np.cos(vyska_slunce)*np.cos(slope)*np.cos(azimut - aspect)

ax.imshow(cost_grid, origin='lower', cmap='terrain_r', extent=[min_x, max_x, min_y, max_y], alpha=0.6)
ax.imshow(shaded, origin='lower', cmap='gray', extent=[min_x, max_x, min_y, max_y], alpha=0.4)

ax.set_title("1. Klikni START | 2. Klikni CÍL")
plt.tight_layout()

# Čekáme na 2 kliknutí
points = plt.ginput(2, timeout=-1)

if len(points) == 2:
    start_real, goal_real = points
    
    start_x_idx = max(0, min(width - 1, int((start_real[0] - min_x) / grid_size)))
    start_y_idx = max(0, min(height - 1, int((start_real[1] - min_y) / grid_size)))
    goal_x_idx = max(0, min(width - 1, int((goal_real[0] - min_x) / grid_size)))
    goal_y_idx = max(0, min(height - 1, int((goal_real[1] - min_y) / grid_size)))
    
    cesta_pixely, usili_skore = astar_search(cost_grid, elev_grid, (start_y_idx, start_x_idx), (goal_y_idx, goal_x_idx))
    
    if cesta_pixely:
        cesta_real_x = [min_x + (px[1] * grid_size) for px in cesta_pixely]
        cesta_real_y = [min_y + (px[0] * grid_size) for px in cesta_pixely]
        
        # Analýza trasy
        realna_delka_m = 0
        nastoupano_m = 0
        for i in range(1, len(cesta_pixely)):
            p1, p2 = cesta_pixely[i-1], cesta_pixely[i]
            # Vzdálenost
            realna_delka_m += math.hypot(p1[0]-p2[0], p1[1]-p2[1]) * grid_size
            # Převýšení
            dz = elev_grid[p2[0], p2[1]] - elev_grid[p1[0], p1[1]]
            if dz > 0: nastoupano_m += dz
            
        # Odhad času: Pokud zpevněná cesta (0.915) trvá špičkovému běžci např. 4:00/km (240s/1000m = 0.24s na bod úsilí)
        # Tento koeficient můžeme později přesně zkalibrovat!
        odhad_sekundy = usili_skore * 0.24 
        minuty = int(odhad_sekundy // 60)
        sekundy = int(odhad_sekundy % 60)
        
        ax.plot(start_real[0], start_real[1], marker='o', markersize=12, color='magenta', label='Start')
        ax.plot(goal_real[0], goal_real[1], marker='o', markersize=12, color='magenta', fillstyle='none', markeredgewidth=3, label='Cíl')
        
        ax.plot(cesta_real_x, cesta_real_y, color='red', linewidth=3, label='Nejrychlejší postup')
        ax.plot(cesta_real_x, cesta_real_y, color='yellow', linewidth=1)
        
        titulek = f"Délka: {realna_delka_m:.0f}m | Převýšení: +{nastoupano_m:.0f}m | Odhad času: {minuty}:{sekundy:02d}"
        ax.set_title(titulek, fontsize=14, fontweight='bold')
        ax.legend(loc="upper left")
        
        plt.draw()
        print(f"\n📊 STATISTIKA POSTUPU:")
        print(f"   📏 Uběhnutá vzdálenost: {realna_delka_m:.0f} metrů")
        print(f"   ⛰️ Nastoupáno: +{nastoupano_m:.0f} metrů")
        print(f"   ⏱️ Teoretický čas elity: {minuty}:{sekundy:02d}")
        
        plt.show()

else:
    print("Skript ukončen.")