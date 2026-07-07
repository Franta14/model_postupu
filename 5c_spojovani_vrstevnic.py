import os
import sys
import math
import json
import xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial import KDTree

try:
    import config
    OMAP_FILE = config.OMAP_FILE
except ImportError:
    OMAP_FILE = "Homolka_Vojirov_20240917.omap"

CACHE_DIR = os.path.join("cache", os.path.splitext(os.path.basename(OMAP_FILE))[0])
META_FILE = os.path.join(CACHE_DIR, "cenova_mapa_meta.npy")

# --- Parametry ---
MAX_GAP_DISTANCE = 25.0  # metry, maximalni mezera ke spojeni
MAP_EDGE_MARGIN = 5.0    # metry, jak blizko musi byt konec k okraji mapy, aby se zakazal
MIN_SCORE = 10.0         # minimalni nutne skore pro spojeni
VECTOR_SMOOTH_DIST = 3.0 # metry, na jake vzdalenosti pocitame smer tecny (pro stabilitu)

# Ktere kody povazujeme za pravdepodobne prerusovace (bonus ke skore)
OBSTACLE_CODES = [
    '107', '109', '110', '111', '112', '113', '114', '115', # terenni tvary
    '201', '202', '204', '205', '206',                      # skaly, kameny
    '501', '502', '503', '504', '505', '506'                # cesty a pesiny
]

def load_meta():
    if not os.path.exists(META_FILE):
        return None
    meta = np.load(META_FILE)
    return {
        'min_x': meta[0], 'min_y': meta[1],
        'max_x': meta[2], 'max_y': meta[3]
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

def get_tangent(pts, is_start):
    """Vypocita smerovy vektor tecny konce. Smeruje VEN z cary."""
    if len(pts) < 2: return np.array([0.0, 0.0])
    
    if is_start:
        base_idx = 0
        direction = 1
    else:
        base_idx = len(pts) - 1
        direction = -1
        
    base_pt = pts[base_idx]
    dist = 0.0
    curr_idx = base_idx
    
    while 0 <= curr_idx < len(pts):
        dist = np.linalg.norm(pts[curr_idx] - base_pt)
        if dist >= VECTOR_SMOOTH_DIST:
            break
        curr_idx += direction
        
    if curr_idx < 0: curr_idx = 0
    if curr_idx >= len(pts): curr_idx = len(pts) - 1
    
    if curr_idx == base_idx:
        curr_idx = base_idx + direction
        if curr_idx < 0: curr_idx = 0
        if curr_idx >= len(pts): curr_idx = len(pts) - 1
        
    vec = base_pt - pts[curr_idx]
    norm = np.linalg.norm(vec)
    if norm < 1e-6: return np.array([1.0, 0.0])
    return vec / norm

def is_map_edge(pt, meta):
    """Zjisti zda bod neni prilis blizko hrany mapy."""
    if not meta: return False
    return (pt[0] <= meta['min_x'] + MAP_EDGE_MARGIN or
            pt[0] >= meta['max_x'] - MAP_EDGE_MARGIN or
            pt[1] <= meta['min_y'] + MAP_EDGE_MARGIN or
            pt[1] >= meta['max_y'] - MAP_EDGE_MARGIN)

def point_to_segment_dist(p, a, b):
    """Vzdalenost bodu p od usecky a-b."""
    ab = b - a
    t = np.dot(p - a, ab) / (np.dot(ab, ab) + 1e-9)
    t = max(0.0, min(1.0, t))
    closest = a + t * ab
    return np.linalg.norm(p - closest)

def calculate_score(end_a, end_b, obs_tree, obs_pts, all_contour_tree):
    """Vypocita skore pro spojeni dvou koncu."""
    dist = np.linalg.norm(end_a['pt'] - end_b['pt'])
    
    # 1. Pojistka 1: Absolutni imunita pro dotyk (0-distance)
    if dist < 0.1:
        return 10000.0
        
    if dist > MAX_GAP_DISTANCE: return -1000.0
    
    # 2. Uhlova shoda a Pojistka 3: Prisne uhlove veto
    vec_ab = end_b['pt'] - end_a['pt']
    vec_ab_norm = np.linalg.norm(vec_ab)
    dir_ab = vec_ab / vec_ab_norm
    dir_ba = -dir_ab
    
    # Dot produkty tecen vuci smeru mostu (idealne 1.0 = dokonale plynuly prechod)
    dot_a = np.dot(end_a['tangent'], dir_ab)
    dot_b = np.dot(end_b['tangent'], dir_ba)
    
    # Pojistka 3: Pokud je prechod ostry a nedava smysl plynule, Tvrde veto
    if dot_a < 0.0 or dot_b < 0.0:
        return -1000.0
        
    # 3. Pojistka 2: Topologicky stit (Zakaz krizeni)
    if all_contour_tree is not None:
        # Vzorkujeme usecku mostu. Vynechame okraje (aby nenahlasil start/cil jako prekazku).
        num_samples = max(3, int(dist))
        steps = np.linspace(0.1, 0.9, num=num_samples)
        for t in steps:
            sample_pt = end_a['pt'] + t * vec_ab
            dist_to_a = np.linalg.norm(sample_pt - end_a['pt'])
            dist_to_b = np.linalg.norm(sample_pt - end_b['pt'])
            
            # Ptame se stromu jen pokud jsme bezpecne daleko od koncu (jinak strom najde primo ty nase konce)
            if dist_to_a > 1.5 and dist_to_b > 1.5:
                closest_dist, _ = all_contour_tree.query(sample_pt)
                if closest_dist < 0.8: # Nabourali jsme do cizi vrstevnice
                    return -1000.0
                
    # --- Vypocet skore (pokud prosel pojistkami) ---
    
    # Vzdalenost skore (max 40 bodu)
    score_dist = 40.0 * (1.0 - (dist / MAX_GAP_DISTANCE))
    
    # Skore uhlu: az 60 bodu za dokonaly prechod
    angle_quality = (dot_a + dot_b) / 2.0
    score_angle = 60.0 * angle_quality
    
    score = score_dist + score_angle
    
    # Bonus za prekazku
    has_obstacle = False
    if obs_tree is not None:
        center_pt = (end_a['pt'] + end_b['pt']) / 2.0
        radius = (dist / 2.0) + 4.0
        idxs = obs_tree.query_ball_point(center_pt, radius)
        for i in idxs:
            if point_to_segment_dist(obs_pts[i], end_a['pt'], end_b['pt']) < 4.0:
                has_obstacle = True
                break
            
    if has_obstacle:
        score += 20.0
        
    return score

class UnionFind:
    def __init__(self):
        self.parent = {}
    def find(self, i):
        if i not in self.parent: self.parent[i] = i
        if self.parent[i] == i: return i
        self.parent[i] = self.find(self.parent[i])
        return self.parent[i]
    def union(self, i, j):
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i != root_j:
            self.parent[root_i] = root_j

def main():
    print("Startuji logiku spojovani vrstevnic...")
    meta = load_meta()
    
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
    obstacles = []
    
    print("Parsuji objekty z OMAP...")
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
                    
        # Detekce prekazek
        elif isom_code in OBSTACLE_CODES or obj.find('text' if not ns else 'ns:text', ns) is not None:
            coords_elem = obj.find('coords' if not ns else 'ns:coords', ns)
            if coords_elem is not None and coords_elem.text:
                pts = extract_coords(coords_elem.text)
                if len(pts) > 0:
                    # Ulozime teziste prekazky
                    center = np.mean(np.array(pts), axis=0)
                    obstacles.append(center)
                    
    print(f"Nalezeno {len(contours)} vrstevnicovych krivek a {len(obstacles)} pripadnych prekazek.")

    # Extrahovat volne konce
    endpoints = []
    
    for cid, pts in contours.items():
        # Zkontrolovat zda neni uzavrena smycka
        dist = np.linalg.norm(pts[0] - pts[-1])
        if dist < 0.1: continue # Uzavrena krivka nepotrebuje spojovat
        
        # Start
        t_start = get_tangent(pts, True)
        if not is_map_edge(pts[0], meta):
            endpoints.append({'cid': cid, 'is_start': True, 'pt': pts[0], 'tangent': t_start})
            
        # Konec
        t_end = get_tangent(pts, False)
        if not is_map_edge(pts[-1], meta):
            endpoints.append({'cid': cid, 'is_start': False, 'pt': pts[-1], 'tangent': t_end})
            
    print(f"Pocet volnych koncu pro spojovani: {len(endpoints)}")
    
    if len(endpoints) == 0:
        print("Zadne konce ke spojeni.")
        return

    # Vytvoreni KDTree pro rychle hledani sousedu a prekazek
    pts_arr = np.array([ep['pt'] for ep in endpoints])
    tree_kd = KDTree(pts_arr)
    
    obs_pts = np.array(obstacles) if obstacles else np.empty((0, 2))
    obs_tree = KDTree(obs_pts) if len(obs_pts) > 0 else None
    
    # Pojistka 2: Topologicky stit (vsechny vrstevnicove body)
    all_pts_list = list(contours.values())
    all_pts_arr = np.vstack(all_pts_list)
    all_contour_tree = KDTree(all_pts_arr)
    
    # Skupiny
    uf = UnionFind()
    for cid in contours.keys():
        uf.find(cid)
        
    pairs = []
    
    print("Hledam potencialni spojeni...")
    for i, ep_a in enumerate(endpoints):
        neighbors = tree_kd.query_ball_point(ep_a['pt'], MAX_GAP_DISTANCE)
        for j in neighbors:
            if i >= j: continue
            ep_b = endpoints[j]
            if ep_a['cid'] == ep_b['cid']: continue # Nespojovat sam sebe
            
            score = calculate_score(ep_a, ep_b, obs_tree, obs_pts, all_contour_tree)
            if score >= MIN_SCORE:
                pairs.append({'a': i, 'b': j, 'score': score, 'cid_a': ep_a['cid'], 'cid_b': ep_b['cid']})
                
    # Sort pairs by score (highest first)
    pairs.sort(key=lambda x: x['score'], reverse=True)
    
    # Greedy union
    used_endpoints = set()
    connections = []
    
    for pair in pairs:
        # Zkontrolujeme, zda uz konce nebyly nekam napojeny
        key_a = f"{pair['cid_a']}_{'s' if endpoints[pair['a']]['is_start'] else 'e'}"
        key_b = f"{pair['cid_b']}_{'s' if endpoints[pair['b']]['is_start'] else 'e'}"
        
        if key_a in used_endpoints or key_b in used_endpoints:
            continue
            
        # Povolit pouze pokud uz nejsou ve stejne skupine (zabraneni cyklum neni nutne spatne, ale zjednodusuje to)
        if uf.find(pair['cid_a']) == uf.find(pair['cid_b']):
            continue
            
        used_endpoints.add(key_a)
        used_endpoints.add(key_b)
        uf.union(pair['cid_a'], pair['cid_b'])
        
        connections.append({
            'pt_a': endpoints[pair['a']]['pt'],
            'pt_b': endpoints[pair['b']]['pt']
        })
        
    print(f"Provedeno {len(connections)} uspesnych slepeni!")
    
    # Zkompilovani skupin
    groups = {}
    for cid in contours.keys():
        root = uf.find(cid)
        if root not in groups:
            groups[root] = []
        groups[root].append(cid)
        
    print(f"Vysledek: {len(groups)} unikatnich souvislych skupin vrstevnic.")
    
    # Ulozeni vysledku
    output_data = {
        'groups': {str(k): [int(x) for x in v] for k, v in groups.items()},
        'connections': [[c['pt_a'].tolist(), c['pt_b'].tolist()] for c in connections]
    }
    
    out_file = os.path.join(CACHE_DIR, "vrstevnice_groups.json")
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(out_file, 'w') as f:
        json.dump(output_data, f)
        
    print(f"Vysledek ulozen do {out_file}")

if __name__ == "__main__":
    main()
