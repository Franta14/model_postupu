import numpy as np
from scipy.interpolate import griddata
import time

print("Generuji data...")
grid_h, grid_w = 1400, 1400
y, x = np.mgrid[0:grid_h, 0:grid_w]
# Nahodnych 120 000 bodu vrstevnic
num_pts = 120000
pts_y = np.random.randint(0, grid_h, num_pts)
pts_x = np.random.randint(0, grid_w, num_pts)
vals = np.random.rand(num_pts)

points = np.column_stack((pts_y, pts_x))
print("Interpoluji griddata...")
t0 = time.time()
grid_z = griddata(points, vals, (y, x), method='linear')
print(f"Hotovo za {time.time()-t0:.2f} s")
