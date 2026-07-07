import os
import math
import json
import numpy as np
import xml.etree.ElementTree as ET
from scipy.spatial import KDTree
from collections import defaultdict, Counter

try:
    import config
    OMAP_FILE = config.OMAP_FILE
except ImportError:
    OMAP_FILE = "Homolka_Vojirov_20240917.omap"

CACHE_DIR = os.path.join("cache", os.path.splitext(os.path.basename(OMAP_FILE))[0])
GROUPS_FILE = os.path.join(CACHE_DIR, "vrstevnice_groups.json")
META_FILE = os.path.join(CACHE_DIR, "cenova_mapa_meta.npy")
LIDAR_FILE = os.path.join(CACHE_DIR, "vyskova_mapa.npy")

EKVIDISTANCE = 5.0
SAMPLE_DIST = 15.0
RAY_LENGTH = 150.0
RAY_STEP = 2.0

def load_meta():
    meta = np.load(META_FILE)
    return {
        'min_x': meta[0], 'min_y': meta[1],
        'max_x': meta[2], 'max_y': meta[3],
        'grid_size': meta[4]
    }

def extract_coords(coords_text):
    pts = []
    if ';' in coords_text:
        for part in coords_text.strip().split(';'):
            nums = part.strip().split()
            if len(nums) >= 2:
                try: pts.append((float(nums[0]) / 1000.0, -float(nums[1]) / 1000.0))
                except ValueError: pass
    else:
        nums = coords_text.strip().split()
        for i in range(0, len(nums) - 1, 2):
            try: pts.append((float(nums[i]) / 1000.0, -float(nums[i+1]) / 1000.0))
            except ValueError: pass
    return pts

def get_lidar_height(pt, meta, lidar_grid):
    grid_x = int((pt[0] - meta['min_x']) / meta['grid_size'])
    grid_y = int((pt[1] - meta['min_y']) / meta['grid_size'])
    h, w = lidar_grid.shape
    if 0 <= grid_x < w and 0 <= grid_y < h:
        val = lidar_grid[grid_y, grid_x]
        if not np.isnan(val):
            return val
        else:
            return -999 # nan
    return -888 # out of bounds

def resample_line(pts, sample_dist):
    if len(pts) < 2: return []
    samples = []
    
    is_closed = False
    area = 0.0
    if np.linalg.norm(pts[0] - pts[-1]) < 1e-3:
        is_closed = True
        for i in range(len(pts)-1):
            area += pts[i][0]*pts[i+1][1] - pts[i+1][0]*pts[i][1]
        area /= 2.0
        
    dist_along = 0.0
    for i in range(len(pts) - 1):
        segment = pts[i+1] - pts[i]
        seg_len = np.linalg.norm(segment)
        if seg_len < 1e-6: continue
        
        dir_vec = segment / seg_len
        normal = np.array([-dir_vec[1], dir_vec[0]])
        
        remaining = seg_len
        p = pts[i]
        
        while dist_along + remaining >= sample_dist:
            step = sample_dist - dist_along
            p = p + dir_vec * step
            samples.append({'pt': p, 'normal': normal, 'is_closed': is_closed, 'area': area})
            remaining -= step
            dist_along = 0.0
            
        dist_along += remaining
            
    # Pokud je obrys prilis maly a nevysel ani jeden vzorek, vezmeme proste prostredni bod
    if not samples and len(pts) >= 2:
        mid_idx = len(pts) // 2
        segment = pts[mid_idx] - pts[mid_idx - 1]
        seg_len = np.linalg.norm(segment)
        if seg_len > 1e-6:
            dir_vec = segment / seg_len
            normal = np.array([-dir_vec[1], dir_vec[0]])
            samples.append({'pt': pts[mid_idx], 'normal': normal, 'is_closed': is_closed, 'area': area})
            
    return samples

def main():
    print("Startuji vypocet topologickeho stromu (Ray-Casting)...")
    meta = load_meta()
    lidar_grid = np.load(LIDAR_FILE)
    
    with open(GROUPS_FILE, 'r') as f:
        groups_data = json.load(f)
    
    group_map = {}
    for gid_str, cids in groups_data['groups'].items():
        for cid in cids:
            group_map[cid] = gid_str

    try:
        tree = ET.parse(OMAP_FILE)
        root = tree.getroot()
    except Exception as e:
        print(f"Chyba: {e}")
        return

    ns = {'ns': 'http://openorienteering.org/apps/mapper/xml/v2'}
    symbol_map = {}
    for sym_elem in root.findall('.//ns:symbol', ns) or root.findall('.//symbol'):
        s_id = sym_elem.attrib.get('id')
        s_code = sym_elem.attrib.get('code')
        if s_id and s_code:
            symbol_map[s_id] = s_code.split('.')[0]

    objects = root.findall('.//ns:object', ns) or root.findall('.//object')
    if not root.findall('.//ns:object', ns): ns = {}
    
    contours = {}
    for idx, obj in enumerate(objects):
        isom_code = None
        sym_child = obj.find('symbol' if not ns else 'ns:symbol', ns)
        if sym_child is not None and sym_child.text:
            isom_code = sym_child.text.strip().split('.')[0][:3]
        else:
            sym_attr = obj.attrib.get('symbol')
            if sym_attr:
                if sym_attr in symbol_map:
                    isom_code = symbol_map[sym_attr][:3]
                else:
                    isom_code = sym_attr.split('.')[0][:3]
                    
        if isom_code in ['101', '102']:
            coords_elem = obj.find('coords' if not ns else 'ns:coords', ns)
            if coords_elem is not None and coords_elem.text:
                pts = extract_coords(coords_elem.text)
                if len(pts) >= 2:
                    contours[idx] = np.array(pts)
                    
    # Vsechny body vsech skupin do KDTree pro detekci kolizi paprsku
    all_points = []
    all_gids = []
    
    group_samples = defaultdict(list)
    
    print("Vzorkuji vrstevnice...")
    for cid, pts in contours.items():
        if cid not in group_map: continue
        gid = group_map[cid]
        
        # Pridat do kdtree bodu (huste vzorkovani pro jistotu ze paprsek neproleti skrz)
        dense_samples = resample_line(pts, 2.0) # 2 metry rozestup
        for s in dense_samples:
            all_points.append(s['pt'])
            all_gids.append(gid)
            
        # Vzorkovat pro paprsky
        samples = resample_line(pts, SAMPLE_DIST)
        group_samples[gid].extend(samples)
        
    print(f"DEBUG: Nacteno bodu: {len(all_points)}")
    print(f"DEBUG: Skupin vzorku: {len(group_samples)}")
    
    if len(all_points) == 0:
        print("CHYBA: all_points je prazdne!")
        return
        
    pts_arr = np.array(all_points)
    tree_kd = KDTree(pts_arr)
    gids_arr = np.array(all_gids)
    
    print("Zahajuji Ray-Casting...")
    # vote_graph[A][B] = N -> Group A hlasuje, ze Group B je UPHILL od ni
    vote_graph = defaultdict(lambda: defaultdict(int))
    
    valid_normals = 0
    rays_hit = 0
    
    for gid, samples in group_samples.items():
        for s in samples:
            if s['normal'] is None: continue
            
            p = s['pt']
            n = s['normal']
            
            # Kterym smerem je do kopce?
            p_plus = p + n * 5.0
            p_minus = p - n * 5.0
            
            h_plus = get_lidar_height(p_plus, meta, lidar_grid)
            h_minus = get_lidar_height(p - n * 5.0, meta, lidar_grid)
            
            if h_plus is not None and h_minus is not None and h_plus not in [-999, -888] and h_minus not in [-999, -888]:
                valid_normals += 1
                
                # Pokud je gradient nulovy (nebo skoro nulovy), a jde o uzavreny obrys, 
                # radsi pouzijeme geometrii (vrcholek) nez nahodu
                if abs(h_plus - h_minus) < 0.1 and s['is_closed']:
                    inward_dir = n if s['area'] > 0 else -n
                    uphill_dir = inward_dir
                    downhill_dir = -inward_dir
                elif h_plus > h_minus:
                    uphill_dir = n
                    downhill_dir = -n
                else:
                    uphill_dir = -n
                    downhill_dir = n
            else:
                # Fallback pro chybejici data (nebo mimo mapu)
                if s['is_closed']:
                    inward_dir = n if s['area'] > 0 else -n
                    uphill_dir = inward_dir
                    downhill_dir = -inward_dir
                else:
                    uphill_dir = -n
                    downhill_dir = n
                
            # Cast ray UPHILL
            for step in np.arange(1.0, RAY_LENGTH, 1.0):
                ray_pt = p + uphill_dir * step
                dist, idx = tree_kd.query(ray_pt)
                if dist < 2.5:
                    hit_gid = gids_arr[idx]
                    if hit_gid != gid:
                        # hit_gid je nad nami. Takze hit_gid -> gid (hit_gid ma rodice gid, coz znamena ze gid je nize)
                        vote_graph[hit_gid][gid] += 1
                        rays_hit += 1
                        break
                        
            # Cast ray DOWNHILL
            for step in np.arange(1.0, RAY_LENGTH, 1.0):
                ray_pt = p + downhill_dir * step
                dist, idx = tree_kd.query(ray_pt)
                if dist < 2.5:
                    hit_gid = gids_arr[idx]
                    if hit_gid != gid:
                        # hit_gid je pod nami. Takze my -> hit_gid (my mame rodice hit_gid, coz znamena ze hit_gid je nize)
                        vote_graph[gid][hit_gid] += 1 
                        rays_hit += 1
                        break
                        
    if 'fail_oob' in locals():
        print(f"DEBUG: fail_oob={fail_oob}, fail_nan={fail_nan}")
    else:
        print("DEBUG: Zadne faily.")
        
    print(f"DEBUG: Vzorku s platnou normalou a LiDARem: {valid_normals}")
    print(f"DEBUG: Paprsku s uspesnym zasahem: {rays_hit}")
    print("Sestavuji finalni topologicky DAG...")
    
    with open(os.path.join(CACHE_DIR, "debug_vote_graph.json"), 'w') as f:
        json.dump({k: dict(v) for k, v in vote_graph.items()}, f, indent=2)
        
    # Pro kazdou group A najdeme tu nejcastejsi uphill group B
    parents = {}
    
    def would_create_cycle(child, parent):
        curr = parent
        visited = set()
        while curr:
            if curr == child: return True
            if curr in visited: return True # prevence nekonecne smycky pokud uz tam cyklus je
            visited.add(curr)
            if curr in parents:
                curr = parents[curr]
            else:
                break
        return False

    # Sestavime hrany sestupne podle poctu hlasu
    edges = []
    for gid, votes in vote_graph.items():
        for pid, v in votes.items():
            if v >= 1:
                edges.append((v, gid, pid))
                
    edges.sort(key=lambda x: x[0], reverse=True)
    
    for v, gid, pid in edges:
        if gid not in parents:
            if not would_create_cycle(gid, pid):
                parents[gid] = pid
            
    # Zjistime absolutni kotvy
    assigned_heights = {}
    
    # Vypocet medianu LiDARu pro kazdou skupinu jako zaloha
    group_medians = {}
    for gid, samples in group_samples.items():
        hs = []
        for s in samples:
            h = get_lidar_height(s['pt'], meta, lidar_grid)
            if h is not None: hs.append(h)
        if hs:
            group_medians[gid] = np.median(hs)
            
    print(f"Pocet relaci parent-child: {len(parents)}")
    
    # Prirazeni korenove vysky
    for gid in group_samples.keys():
        if gid not in parents: # Je to koren (uplne dole pod kopcem)
            if gid in group_medians:
                h = group_medians[gid]
                assigned_heights[gid] = round(h / EKVIDISTANCE) * EKVIDISTANCE
                
    # Traverzovani stromu
    changed = True
    while changed:
        changed = False
        for gid, pid in parents.items():
            if gid not in assigned_heights and pid in assigned_heights:
                assigned_heights[gid] = assigned_heights[pid] + EKVIDISTANCE
                changed = True
                
    # Fallback pro skupiny mimo strom
    # Fallback pro skupiny mimo strom
    for gid in group_samples.keys():
        if gid not in assigned_heights:
            if gid in group_medians:
                assigned_heights[gid] = round(group_medians[gid] / EKVIDISTANCE) * EKVIDISTANCE
            else:
                assigned_heights[gid] = 500.0

    # KONTROLA LOKALNICH MINIM (Depresi):
    # Pokud je nejaky koren uplne odriznuty (napr. dno doliku) a dostal 500.0 z chyby LiDARu,
    # mel by dostat vysku podle sveho souseda.
    print("Bezpecna kontrola a oprava anomalnich propadu (pouze pro izolované 500m kořeny)...")
    
    # Zjistime pro kazdy koren, kolik ma celkem potomku
    def get_descendants(root_gid):
        desc = set()
        to_visit = [root_gid]
        while to_visit:
            curr = to_visit.pop()
            for child, pid in parents.items():
                if pid == curr and child not in desc:
                    desc.add(child)
                    to_visit.append(child)
        return desc
        
    for gid in group_samples.keys():
        if gid not in parents and assigned_heights.get(gid) == 500.0:
            # Je to koren a ma 500.0
            desc = get_descendants(gid)
            # Pokud je to jen maly odriznuty kousek (napr. do 10 vrstevnic)
            if len(desc) < 10:
                pts = [s['pt'] for s in group_samples[gid]]
                if not pts: continue
                p = pts[0]
                
                # Najdeme nejblizsi bod z JINE skupiny, ktera NENI v teto komponente
                dist, idx = tree_kd.query(p, k=2000)
                for i in range(len(idx)):
                    neighbor_gid = gids_arr[idx[i]]
                    if neighbor_gid != gid and neighbor_gid not in desc and neighbor_gid in assigned_heights:
                        neigh_h = assigned_heights[neighbor_gid]
                        
                        if neigh_h == 500.0:
                            continue # Nenechame se zmast dalsim chybnym korenem
                            
                        print(f"DEBUG: koren {gid} ma souseda {neighbor_gid} s vyskou {neigh_h}")
                            
                        # Pokud je rozdil obrovsky (>= 10m je dost velky skok na zemi)
                        if abs(500.0 - neigh_h) >= 10.0:
                            print(f"   > Opravuji izolovany koren {gid} z 500.0m na {neigh_h}m (podle souseda {neighbor_gid})")
                            diff = neigh_h - 500.0
                            assigned_heights[gid] += diff
                            for cgid in desc:
                                assigned_heights[cgid] += diff
                        break

    print("Rasterizuji vysky vrstevnic do mrizky...")
    h_grid, w_grid = lidar_grid.shape
    vrstevnice_vysky = np.full((h_grid, w_grid), np.nan, dtype=np.float32)
    
    count = 0
    for cid, pts in contours.items():
        if cid not in group_map: continue
        gid = group_map[cid]
        h_val = assigned_heights[gid]
        
        for pt in pts:
            gx = int((pt[0] - meta['min_x']) / meta['grid_size'])
            gy = int((pt[1] - meta['min_y']) / meta['grid_size'])
            if 0 <= gx < w_grid and 0 <= gy < h_grid:
                # Rozmazneme trochu, aby cara nebyla derava
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        if 0 <= gx+dx < w_grid and 0 <= gy+dy < h_grid:
                            vrstevnice_vysky[gy+dy, gx+dx] = h_val
        count += 1
        
    # Ulozeni vektorovych vysek do JSONu pro primou aplikaci
    heights_out = os.path.join(CACHE_DIR, "assigned_heights.json")
    with open(heights_out, 'w') as f:
        json.dump(assigned_heights, f, indent=2)
    print(f"Ulozeny vektorove vysky do {heights_out}")
        
    out_file = os.path.join(CACHE_DIR, "vrstevnice_vysky.npy")
    np.save(out_file, vrstevnice_vysky)
    print(f"Ulozeno {count} vrstevnic do {out_file}")

if __name__ == "__main__":
    main()
