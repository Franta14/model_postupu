import os
import json
import glob
import numpy as np
from PIL import Image, ImageDraw
import shutil
import math

maps_to_export = [
    {
        "map_id": "homolka",
        "map_name": "Homolka",
        "terrain": "cesko",
        "cache_dir": "cache/Homolka_Vojirov_20240917",
        "png_file": "mapa.png",
        "pgw_file": "mapa.pgw"
    },
    {
        "map_id": "holna",
        "map_name": "Holná",
        "terrain": "cesko",
        "cache_dir": "cache/Holna_20240916",
        "png_file": "Holna.png",
        "pgw_file": "Holna.pgw"
    },
    {
        "map_id": "bilaskala",
        "map_name": "Bílá skála",
        "terrain": "cesko",
        "cache_dir": "cache/bilaskala",
        "png_file": "bilaskala.png",
        "pgw_file": "bilaskala.pgw"
    }
]

def draw_leg_image(p1, p2, routes, filename, orig_img, kalibrace, circle_scale):
    cal_a, cal_b, cal_c, cal_d, cal_e, cal_f = kalibrace
    def grid_to_img(r, c):
        x = col = cal_a * c + cal_b * r + cal_c
        y = row = cal_d * c + cal_e * r + cal_f
        return (int(x), int(y))

    img = orig_img.copy()
    draw = ImageDraw.Draw(img, 'RGBA')
    
    c1, r1 = grid_to_img(p1['gy'], p1['gx'])
    c2, r2 = grid_to_img(p2['gy'], p2['gx'])
    
    min_c = min(c1, c2) - 400
    max_c = max(c1, c2) + 400
    min_r = min(r1, r2) - 400
    max_r = max(r1, r2) + 400

    for route in routes:
        for py, px in route:
            c, r = grid_to_img(py, px)
            if c < min_c + 300: min_c = c - 300
            if c > max_c - 300: max_c = c + 300
            if r < min_r + 300: min_r = r - 300
            if r > max_r - 300: max_r = r + 300
            
    PURPLE = (200, 0, 200, 255)
    radius = int(35.0 * circle_scale)
    thickness = max(3, int(radius / 7))
    
    colors = [(255, 0, 0, 150), (0, 0, 255, 150), (0, 255, 0, 150)]
    for i, route in enumerate(routes):
        if not route: continue
        color = colors[i % len(colors)]
        img_route = [grid_to_img(gy, gx) for gy, gx in route]
        if len(img_route) > 1:
            draw.line(img_route, fill=color, width=8, joint='curve')
            
    dist = np.sqrt((c2-c1)**2 + (r2-r1)**2)
    if dist > radius * 2:
        dx, dy = (c2-c1)/dist, (r2-r1)/dist
        start_line = (c1 + dx*radius, r1 + dy*radius)
        end_line = (c2 - dx*radius, r2 - dy*radius)
        draw.line([start_line, end_line], fill=PURPLE, width=4)
        
    angle = math.atan2(r2-r1, c2-c1)
    R = radius * 1.15
    angle1 = angle
    angle2 = angle + 2 * math.pi / 3
    angle3 = angle - 2 * math.pi / 3
    
    p1_t = (c1 + math.cos(angle1)*R, r1 + math.sin(angle1)*R)
    p2_t = (c1 + math.cos(angle2)*R, r1 + math.sin(angle2)*R)
    p3_t = (c1 + math.cos(angle3)*R, r1 + math.sin(angle3)*R)
    draw.polygon([p1_t, p2_t, p3_t], outline=PURPLE, fill=None, width=thickness)
    
    draw.ellipse([c2-radius, r2-radius, c2+radius, r2+radius], outline=PURPLE, width=thickness)

    min_c, min_r = max(0, min_c), max(0, min_r)
    max_c, max_r = min(img.width, max_c), min(img.height, max_r)
    crop = img.crop((min_c, min_r, max_c, max_r))
    
    if crop.width > 1200 or crop.height > 1200:
        crop.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        
    crop.save(filename, "PNG", optimize=True)

def regenerate():
    Image.MAX_IMAGE_PIXELS = None
    for m in maps_to_export:
        print(f"Regenerating PNGs for {m['map_name']}...")
        if not os.path.exists(m['png_file']):
            print(f"Missing {m['png_file']}, skipping.")
            continue
            
        orig_img = Image.open(m['png_file'])
        
        try:
            with open(m['pgw_file'], 'r') as f:
                px_size = abs(float(f.readline().strip()))
        except:
            px_size = 0.846
            
        kalibrace = np.load(os.path.join(m['cache_dir'], "kalibrace.npy"))
        
        json_dir = os.path.join(m['cache_dir'], "schvalene_postupy")
        archiv_dir = os.path.join(m['cache_dir'], "archiv_postupu")
        
        if not os.path.exists(json_dir):
            continue
            
        json_files = glob.glob(os.path.join(json_dir, "*.json"))
        for jf in json_files:
            with open(jf, 'r') as f:
                data = json.load(f)
            
            basename = os.path.basename(jf)
            png_basename = "schvaleno_" + basename.replace(".json", ".png")
            png_path = os.path.join(archiv_dir, png_basename)
            
            p1 = data['start']
            p2 = data['end']
            routes = [v['cesta'] for v in data.get('variants', [])]
            
            circle_scale = m.get('circle_scale', 1.0)
            draw_leg_image(p1, p2, routes, png_path, orig_img, kalibrace, circle_scale)
            print(f"Regenerated {png_basename}")

if __name__ == '__main__':
    regenerate()
