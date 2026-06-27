import sys
import xml.etree.ElementTree as ET
from collections import Counter

def is_text_object(obj: ET.Element) -> bool:
    # Běžné varianty: objekt má typ "text" / "Text" nebo obsahuje textový subtag
    t = (obj.get("type") or "").strip().lower()
    if t == "text":
        return True
    for child in obj:
        if child.tag.lower() in {"text", "t"}:
            return True
    return False

def main(path: str) -> int:
    tree = ET.parse(path)
    root = tree.getroot()

    counts = Counter()

    for obj in root.iter("object"):
        if is_text_object(obj):
            continue
        sym = obj.get("symbol")
        if sym:
            counts[sym] += 1

    if not counts:
        print("Nenašel jsem žádné netextové <object> se symbolem.")
        return 0

    rows = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))

    sym_w = max(len("symbol"), max(len(s) for s, _ in rows))
    cnt_w = max(len("count"), max(len(str(c)) for _, c in rows))

    print(f"{'symbol'.ljust(sym_w)}  {'count'.rjust(cnt_w)}")
    print(f"{'-'*sym_w}  {'-'*cnt_w}")
    for sym, c in rows:
        print(f"{sym.ljust(sym_w)}  {str(c).rjust(cnt_w)}")

    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Použití: python vypis_symboly.py Homolka_Vojirov_20240917.omap")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))