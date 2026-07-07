import xml.etree.ElementTree as ET
import sys

file_path = "Homolka_Vojirov_20240917.omap"
print(f"Reading {file_path}...")

try:
    tree = ET.parse(file_path)
    root = tree.getroot()
    ns = {'ns': 'http://openorienteering.org/apps/mapper/xml/v2'}
    
    count = 0
    objects = root.findall('.//ns:object', ns)
    if not objects:
        objects = root.findall('.//object')
        ns = {}
        
    for obj in objects:
        sym = obj.attrib.get('symbol')
        if sym in ['101', '102']:
            print(f"Found object with symbol {sym}")
            coords_elem = obj.find('coords' if not ns else 'ns:coords', ns)
            if coords_elem is not None:
                print("Text length:", len(coords_elem.text) if coords_elem.text else 0)
                print("Text snippet:", coords_elem.text[:200] if coords_elem.text else "None")
                for c in list(coords_elem)[:5]:
                    print("Child:", c.tag, c.attrib)
            count += 1
            if count >= 2:
                break
except Exception as e:
    print(e)
