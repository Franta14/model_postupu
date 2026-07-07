import matplotlib.pyplot as plt
import numpy as np
import xml.etree.ElementTree as ET
from zpracovani_vrstevnic import ContourMerger

tree = ET.parse('Homolka_Vojirov_20240917.omap')
root = tree.getroot()

symbol_map = {}
for elem in root.iter():
    if 'symbol' in elem.tag.lower():
        sid = elem.attrib.get('id')
        code = elem.attrib.get('code')
        if sid and code:
            symbol_map[sid] = code

merger = ContourMerger(root, symbol_map)
contours = merger.process()

plt.figure(figsize=(12, 12))
cmap = plt.get_cmap('tab20')

for i, c in enumerate(contours):
    pts = np.array(c['geom'].coords)
    color = cmap(i % 20)
    plt.plot(pts[:, 0], pts[:, 1], color=color, linewidth=1.5)

plt.axis('equal')
plt.title("Merged Contours")
plt.savefig('cache/merged_contours.png', dpi=300)
print("Saved cache/merged_contours.png")
