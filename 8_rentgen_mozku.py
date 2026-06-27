import numpy as np
import matplotlib.pyplot as plt
import heapq
import math
from PIL import Image

# Nacteni dat a kalibrace
cost_grid_base = np.load("cenova_mapa.npy")
elev_grid = np.load("vyskova_mapa.npy")
meta = np.load("cenova_mapa_meta.npy")
min_x, min_y, max_x, max_y, grid_size = meta
height, width = cost_grid_base.shape
scale_x, scale_y, off_x, off_y = np.load("kalibrace.npy")

def img_to_grid(u, v):
    x, y = u * scale_x + off_x, v * scale_y + off_y
    return max(0, min(height - 1, int(y))), max(0, min(width - 1, int(x)))

def astar(grid, start, goal):
    directions = [(0, 1, grid_size), (1, 0, grid_size), (0, -1, grid_size), (-1, 0, grid_size),
                  (1, 1, grid_size * 1.414), (-1, 1, grid_size * 1.414), (1, -1, grid_size * 1.414), (-1, -1, grid_size * 1.414)]
    open_set = []
    heapq.heappush(open_set, (0.0, start))
    came_from, g_score = {}, {start: 0.0}

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
        for dy, dx, dist in directions:
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < height and 0 <= nx < width:
                dz = elev_grid[ny, nx] - elev_grid[cy, cx]
                penalty = (dz * 4.0) if dz > 0.3 else (abs(dz) * 1.0 if dz < -0.6 else 0)
                step_effort = (dist * grid[ny, nx]) + penalty
                tentative_g = g_score[current] + step_effort

                if (ny, nx) not in g_score or tentative_g < g_score[(ny, nx)]:
                    came_from[(ny, nx)], g_score[(ny, nx)] = current, tentative_g
                    h = math.hypot(goal[1] - nx, goal[0] - ny) * grid_size * 0.915
                    heapq.heappush(open_set, (tentative_g + h, (ny, nx)))
    return None

# KROK 1: Kliknuti na PNG mapu
img = Image.open("mapa.png")
fig1, ax1 = plt.subplots(figsize=(10, 8))
ax1.imshow(img)
ax1.set_title("1. Klikni START a CÍL")
plt.tight_layout()
pts = plt.ginput(2, timeout=-1)
plt.close(fig1)

if len(pts) == 2:
    s_y, s_x = img_to_grid(pts[0][0], pts[0][1])
    g_y, g_x = img_to_grid(pts[1][0], pts[1][1])
    
    print("⏳ Počítám hlavní trasu (Bez vyhlazování a bez penalizací okolí)...")
    cesta = astar(cost_grid_base, (s_y, s_x), (g_y, g_x))
    
    # KROK 2: Vykreslení přímo do RAW dat
    fig2, ax2 = plt.subplots(figsize=(12, 10))
    # Použijeme vysokokontrastní zobrazení (cesty budou tmavé, les světlý)
    cmap = ax2.imshow(cost_grid_base, cmap='terrain_r', vmax=1.5)
    fig2.colorbar(cmap, ax=ax2, label="Cena terénu")
    
    if cesta:
        cx, cy = [p[1] for p in cesta], [p[0] for p in cesta]
        ax2.plot(cx, cy, color='red', linewidth=2, label="Skutečná myšlenka AI")
        ax2.plot(s_x, s_y, 'mo', markersize=10, label="Start")
        ax2.plot(g_x, g_y, 'm*', markersize=12, label="Cíl")
        
    ax2.set_title("RENTGEN: Takto vidí terén a trasu počítač")
    ax2.legend()
    plt.show()