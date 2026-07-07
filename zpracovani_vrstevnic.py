import xml.etree.ElementTree as ET
import numpy as np
from math import sqrt, atan2, pi
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

class ContourMerger:
    def __init__(self, root, symbol_map, max_dist=15.0): # Snížen max_dist pro větší bezpečnost
        self.root = root
        self.symbol_map = symbol_map
        self.max_dist = max_dist
        
        self.raw_fragments = []
        
    def _angle_diff(self, a1, a2):
        d = abs(a1 - a2)
        while d > pi:
            d = 2 * pi - d
        return d
        
    def process(self):
        print("   [ContourMerger] Extrahuji vrstevnice z OMAP (VČETNĚ všech bodů pro zachování tvaru)...")
        self._extract_fragments()
        
        if not self.raw_fragments:
            print("   [ContourMerger] Nebyly nalezeny žádné vrstevnice.")
            return []
            
        endpoints = self._identify_endpoints()
        print(f"   [ContourMerger] Nalezeno {len(endpoints)} volných konců.")
        
        mutual_matches = self._find_connections(endpoints)
        print(f"   [ContourMerger] Nalezeno {len(mutual_matches)} bezpečných spojení.")
        
        merged_contours = self._merge_fragments(mutual_matches)
        print(f"   [ContourMerger] Původně {len(self.raw_fragments)} fragmentů -> {len(merged_contours)} spojených celků.")
        
        return merged_contours
        
    def _extract_fragments(self):
        for obj in self.root.iter():
            if 'object' not in obj.tag.lower():
                continue
                
            isom_full = self.symbol_map.get(obj.attrib.get('symbol', ''), '')
            isom = isom_full.split('.')[0]
            
            if isom in ['101', '102']:
                pts = []
                for child in obj:
                    if 'coords' in child.tag.lower() and child.text:
                        for p in child.text.strip().split(';'):
                            parts = p.strip().split()
                            if len(parts) >= 2:
                                # ZRUŠENO: vynechávání Bezier bodů. 
                                # Tyto body definují tvar křivky. Pokud je vynecháme, vrstevnice se zkrátí a jde "lesem".
                                try:
                                    pts.append((float(parts[0])/1000, -float(parts[1])/1000))
                                except ValueError:
                                    pass
                        break
                        
                if len(pts) >= 2:
                    text_content = None
                    for child in obj:
                        if child.tag.lower() in ['t', 'text']:
                            text_content = (child.text or '').strip()
                            break
                            
                    elev_known = None
                    if text_content:
                        try:
                            elev_known = float(text_content)
                        except ValueError:
                            pass
                            
                    self.raw_fragments.append({
                        'pts': pts,
                        'is_index': (isom == '102'),
                        'elevation': elev_known
                    })

    def _get_stable_angle(self, pts, is_start):
        """
        Vypočítá stabilní směr konce vrstevnice.
        Protože poslední body mohou být velmi blízko sebe (např. Bezier control points),
        hledáme bod, který je alespoň 2 metry daleko od samotného konce, abychom získali skutečný směr.
        """
        LOOKAHEAD_DIST = 2.0
        if is_start:
            pt_end = pts[0]
            for i in range(1, len(pts)):
                d = sqrt((pts[i][0] - pt_end[0])**2 + (pts[i][1] - pt_end[1])**2)
                if d >= LOOKAHEAD_DIST or i == len(pts)-1:
                    # Směr OD pt_end DO lesa
                    # Takže směr ven z čáry je od pts[i] k pts[0]
                    return atan2(pt_end[1] - pts[i][1], pt_end[0] - pts[i][0])
        else:
            pt_end = pts[-1]
            for i in range(len(pts)-2, -1, -1):
                d = sqrt((pts[i][0] - pt_end[0])**2 + (pts[i][1] - pt_end[1])**2)
                if d >= LOOKAHEAD_DIST or i == 0:
                    # Směr ven z čáry je od pts[i] k pts[-1]
                    return atan2(pt_end[1] - pts[i][1], pt_end[0] - pts[i][0])
        return 0.0

    def _identify_endpoints(self):
        endpoints = []
        for i, frag in enumerate(self.raw_fragments):
            pts = frag['pts']
            if len(pts) < 2:
                continue
                
            d_loop = sqrt((pts[0][0] - pts[-1][0])**2 + (pts[0][1] - pts[-1][1])**2)
            if d_loop < 0.5:
                continue
                
            endpoints.append({
                'frag_idx': i,
                'is_start': True,
                'pt': pts[0],
                'angle': self._get_stable_angle(pts, True)
            })
            
            endpoints.append({
                'frag_idx': i,
                'is_start': False,
                'pt': pts[-1],
                'angle': self._get_stable_angle(pts, False)
            })
                
        return endpoints

    def _find_connections(self, endpoints):
        lines = [LineString(frag['pts']) for frag in self.raw_fragments]
        tree = STRtree(lines)
        
        def intersects_any(p1, p2, ignore_idx1, ignore_idx2):
            seg = LineString([p1, p2])
            candidates = tree.query(seg)
            for idx in candidates:
                if idx in (ignore_idx1, ignore_idx2):
                    continue
                if seg.intersects(lines[idx]):
                    return True
            return False

        matches = []
        for i, ep1 in enumerate(endpoints):
            best_cost = float('inf')
            best_j = -1
            
            for j, ep2 in enumerate(endpoints):
                if i == j:
                    continue
                if ep1['frag_idx'] == ep2['frag_idx']:
                    continue
                    
                p1 = ep1['pt']
                p2 = ep2['pt']
                dist = sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
                
                if dist > self.max_dist:
                    continue
                
                a1 = ep1['angle']
                a2 = ep2['angle']
                
                # U-turn prevence: Konce musí mířit zhruba proti sobě.
                # a2 by mělo být cca a1 + pi. 
                # Pokud je rozdíl větší než 75 stupňů (pi * 75 / 180), odmítneme spojení.
                dir_diff = self._angle_diff(a2, a1 + pi)
                if dir_diff > (75.0 * pi / 180.0):
                    continue
                
                # Výpočet úhlu propojovací čáry (od p1 k p2)
                angle_1_to_2 = atan2(p2[1] - p1[1], p2[0] - p1[0])
                
                # Jak moc p2 uhýbá ze směru, kterým míří p1? (Lateralita)
                dev1 = self._angle_diff(a1, angle_1_to_2)
                # Jak moc p1 uhýbá ze směru, kterým míří p2?
                dev2 = self._angle_diff(a2, angle_1_to_2 + pi)
                
                # Pokud některý úhel přesáhne 75 stupňů, je to příliš do boku
                if dev1 > (75.0 * pi / 180.0) or dev2 > (75.0 * pi / 180.0):
                    continue
                
                # Cena: vzdálenost + velká penalizace za boční odchylku (20m za radian)
                lateral_penalty = (dev1 + dev2) * 20.0
                cost = dist + lateral_penalty
                
                if cost < best_cost:
                    if not intersects_any(p1, p2, ep1['frag_idx'], ep2['frag_idx']):
                        best_cost = cost
                        best_j = j
                        
            if best_j != -1:
                matches.append((i, best_j, best_cost))
                
        # Zamezení protnutí nových spojů navzájem + mutual shoda
        matches.sort(key=lambda x: x[2])
        accepted_bridges = []
        bridge_lines = []
        used_endpoints = set()
        
        for i, j, cost in matches:
            if i in used_endpoints or j in used_endpoints:
                continue
                
            j_matches = [m for m in matches if m[0] == j]
            if not j_matches or j_matches[0][1] != i:
                continue
                
            p1 = endpoints[i]['pt']
            p2 = endpoints[j]['pt']
            seg = LineString([p1, p2])
            
            crosses = False
            for bline in bridge_lines:
                if seg.intersects(bline):
                    crosses = True
                    break
            
            if not crosses:
                accepted_bridges.append((endpoints[i]['frag_idx'], endpoints[j]['frag_idx'], endpoints[i]['is_start'], endpoints[j]['is_start']))
                bridge_lines.append(seg)
                used_endpoints.add(i)
                used_endpoints.add(j)
                    
        return accepted_bridges

    def _merge_fragments(self, mutual_matches):
        chains = {i: [(i, False)] for i in range(len(self.raw_fragments))}
        
        for f1, f2, is_start1, is_start2 in mutual_matches:
            chain1_idx = next(k for k, v in chains.items() if any(f == f1 for f, _ in v))
            chain2_idx = next(k for k, v in chains.items() if any(f == f2 for f, _ in v))
            
            if chain1_idx == chain2_idx:
                continue
                
            c1 = chains[chain1_idx]
            c2 = chains[chain2_idx]
            
            f1_pos = 0 if c1[0][0] == f1 else -1
            f2_pos = 0 if c2[0][0] == f2 else -1
            
            f1_rev = c1[f1_pos][1]
            f2_rev = c2[f2_pos][1]
            
            actual_start1 = not is_start1 if f1_rev else is_start1
            actual_start2 = not is_start2 if f2_rev else is_start2
            
            if actual_start1 and not actual_start2:
                new_chain = c2 + c1
            elif not actual_start1 and actual_start2:
                new_chain = c1 + c2
            elif not actual_start1 and not actual_start2:
                reversed_c2 = [(f, not r) for f, r in reversed(c2)]
                new_chain = c1 + reversed_c2
            elif actual_start1 and actual_start2:
                reversed_c1 = [(f, not r) for f, r in reversed(c1)]
                new_chain = reversed_c1 + c2
                
            chains[chain1_idx] = new_chain
            del chains[chain2_idx]
            
        merged_results = []
        for chain in chains.values():
            merged_pts = []
            is_idx = False
            elev = None
            
            for frag_idx, is_rev in chain:
                frag = self.raw_fragments[frag_idx]
                is_idx = is_idx or frag['is_index']
                if frag['elevation'] is not None:
                    elev = frag['elevation']
                    
                pts = frag['pts']
                if is_rev:
                    pts = list(reversed(pts))
                    
                if not merged_pts:
                    merged_pts.extend(pts)
                else:
                    merged_pts.extend(pts)
                    
            if len(merged_pts) >= 2:
                merged_results.append({
                    'geom': LineString(merged_pts),
                    'is_index': is_idx,
                    'elevation': elev
                })
                
        return merged_results
