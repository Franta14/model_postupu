import json

def main():
    with open("cache/Homolka_Vojirov_20240917/assigned_heights.json") as f:
        assigned = json.load(f)
        
    c500 = [k for k,v in assigned.items() if v == 500.0]
    
    print(f"Pocet 500.0 contours: {len(c500)}")
    
    # Is there a cycle?
    # We can reconstruct the parents from the algorithm
    with open("cache/Homolka_Vojirov_20240917/vrstevnice_groups.json") as f:
        gdata = json.load(f)['groups']
        
    print(f"Total groups: {len(gdata)}")
    
    # Well, we can't easily rebuild vote_graph without ray casting.
    # But wait! I can just modify 6_vyskova_mapa.py to print the cycles or just break them!
    
if __name__ == '__main__':
    main()
