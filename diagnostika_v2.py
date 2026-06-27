import xml.etree.ElementTree as ET
import sys
from collections import Counter

def main(path):
    print(f"Čtu soubor: {path}...")
    tree = ET.parse(path)
    root = tree.getroot()

    # 1. Zmapování symbolů. 
    # OMAP soubory často nenesou kód "406" přímo na objektu, ale mají tabulku: <symbol id="12" code="406.000">
    symbol_map = {}
    for elem in root.iter():
        # Hledáme tagy 'symbol' (ignorujeme případné namespaces)
        if 'symbol' in elem.tag.lower():
            s_id = elem.attrib.get('id')
            s_code = elem.attrib.get('code')
            if s_id and s_code:
                symbol_map[s_id] = s_code

    print(f"V mapě jsem našel slovník {len(symbol_map)} definic symbolů.")

    # 2. Počítání reálných objektů na mapě
    counts = Counter()
    found_objects = 0
    
    for elem in root.iter():
        if 'object' in elem.tag.lower():
            found_objects += 1
            # Objekt může mít ID symbolu
            sym_id = elem.attrib.get('symbol')
            if sym_id:
                # Přeložíme vnitřní ID na ISOM kód z tabulky výše
                isom_code = symbol_map.get(sym_id, f"Neznámé ID: {sym_id}")
                counts[isom_code] += 1

    print(f"Celkem nalezeno tagů <object>: {found_objects}\n")
    
    if not counts:
        print("Nenašel jsem v objektech žádný atribut 'symbol'.")
        print("Takhle vypadají atributy prvního nalezeného objektu, abychom viděli, kde je chyba:")
        for elem in root.iter():
            if 'object' in elem.tag.lower():
                print(elem.attrib)
                break
        return

    print("TOP 30 nejčastějších ISOM kódů v tvé mapě:")
    print("-" * 40)
    for sym, count in counts.most_common(30):
        print(f"ISOM Kód {sym.ljust(15)} : {count} objektů")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Spusť to takto: python diagnostika_v2.py Homolka_Vojirov_20240917.omap")
    else:
        main(sys.argv[1])