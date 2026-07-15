with open('export/app.js', 'r', encoding='utf-8') as f:
    text = f.read()

import re

# 1. Remove old SVG spojnice logic
text = re.sub(
    r'if \(startCoords && endCoords\) \{\s*let dx = endCoords\[0\] - startCoords\[0\];\s*let dy = endCoords\[1\] - startCoords\[1\];\s*let dist = Math\.sqrt\(dx\*dx \+ dy\*dy\);\s*if \(dist > 0\) \{\s*let ux = dx / dist;\s*let uy = dy / dist;\s*let rStart = 0\.75;\s*let rEnd = 0\.55;\s*let lineStart = \[startCoords\[0\] \+ ux \* rStart \* 1\.5, startCoords\[1\] \+ uy \* rStart \* 1\.5\];\s*let lineEnd = \[endCoords\[0\] - ux \* rEnd \* 1\.2, endCoords\[1\] - uy \* rEnd \* 1\.2\];\s*geojson\.features\.push\(\{\s*"type": "Feature",\s*"geometry": \{\s*"type": "LineString",\s*"coordinates": \[lineStart, lineEnd\]\s*\},.*?\}\);\s*\}\s*\}',
    '',
    text,
    flags=re.DOTALL
)

# 2. Update filter
text = re.sub(
    r'filter: function\(feature\) \{\s*if \(feature\.properties && feature\.properties\.type === \'variant\' && !showVariants\) \{\s*return false;\s*\}\s*return true;\s*\},',
    '''filter: function(feature) {
            if (feature.properties && feature.properties.type === 'variant' && !showVariants) return false;
            if (feature.properties && ['start', 'end', 'spojnice'].includes(feature.properties.type)) return false;
            return true;
        },''',
    text
)

# 3. Replace pointToLayer and old drawing with new native circles
new_native = '''}
    });
    
    if (startCoords && endCoords) {
        let dx = endCoords[0] - startCoords[0];
        let dy = endCoords[1] - startCoords[1];
        let dist = Math.sqrt(dx*dx + dy*dy);
        if (dist > 0) {
            let R = 0.55; 
            let gap = 0.05;
            let ux = dx / dist;
            let uy = dy / dist;
            let lineWeight = Math.max(2.5, Math.min(3.5, 2.5 + dist / 100));
            let lineStart = [startCoords[0] + ux * (R + gap), startCoords[1] + uy * (R + gap)];
            let lineEnd = [endCoords[0] - ux * (R + gap), endCoords[1] - uy * (R + gap)];
            if (dist > R*2 + gap*2) {
                let polyline = L.polyline([
                    [lineStart[1], lineStart[0]],
                    [lineEnd[1], lineEnd[0]]
                ], {color: iofPurple, weight: lineWeight, pane: 'markerPane', interactive: false});
                layer.addLayer(polyline);
            }
            [startCoords, endCoords].forEach((coords, idx) => {
                let circle = L.circle([coords[1], coords[0]], {
                    radius: R, color: iofPurple, weight: lineWeight, fill: false, pane: 'markerPane', interactive: false
                });
                layer.addLayer(circle);
                let nx = -uy, ny = ux;
                let num = idx === 0 ? "1" : "2";
                let svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
                svg.setAttribute('xmlns', "http://www.w3.org/2000/svg");
                svg.setAttribute('viewBox', "0 0 100 100");
                svg.innerHTML = <text x='50' y='80' font-family='Arial, sans-serif' font-size='75' font-weight='bold' fill='' text-anchor='middle'></text>;
                let textDist = R + 0.40; 
                let cx = coords[0] + nx * textDist, cy = coords[1] + ny * textDist;
                let halfSize = 0.45;
                let bounds = [[cy - halfSize, cx - halfSize], [cy + halfSize, cx + halfSize]];
                layer.addLayer(L.svgOverlay(svg, bounds, {interactive: false}));
            });
        }
    }'''

text = re.sub(
    r'style: function \(feature\) \{.*?pointToLayer: function \(feature, latlng\) \{.*?return L\.featureGroup\(\[outer, inner\]\);\s*\}\s*\}\s*\}\);',
    '''style: function (feature) {
            if (feature.properties && feature.properties.type === 'variant') {
                return { color: feature.properties.color, weight: 6, opacity: 0.8, lineCap: 'round', lineJoin: 'round' };
            }
        ''' + new_native,
    text,
    flags=re.DOTALL
)

# 4. Calibration logic
text = text.replace("map.fitBounds(bounds);", "map.fitBounds(bounds);\n    map.on('zoomend', updateCalibrationShift);")

calib_logic = '''
let calibMode = false;
let calibX = 400;
let calibY = -300;
document.addEventListener('keydown', (e) => {
    if (e.key.toLowerCase() === 'k') {
        calibMode = !calibMode;
        let ui = document.getElementById('calibration-ui');
        if(ui) ui.style.display = calibMode ? 'block' : 'none';
        if (calibMode) updateCalibrationShift();
        return;
    }
    if (!calibMode) return;
    if (e.key === 'ArrowLeft') calibX -= 1;
    else if (e.key === 'ArrowRight') calibX += 1;
    else if (e.key === 'ArrowUp') calibY -= 1;
    else if (e.key === 'ArrowDown') calibY += 1;
    else return;
    e.preventDefault();
    let xspan = document.getElementById('calib-x');
    let yspan = document.getElementById('calib-y');
    if (xspan) xspan.innerText = calibX;
    if (yspan) yspan.innerText = calibY;
    updateCalibrationShift();
});

function updateCalibrationShift() {
    if (typeof activeIndex === 'undefined') return;
    let map = mapInstances[activeIndex];
    if (!map) return;
    let pane = map.getPane('markerPane');
    let shiftXConfig = calibX - 400;
    let shiftYConfig = calibY - (-300);
    let scale = Math.pow(2, map.getZoom()) / 64;
    pane.style.marginLeft = (shiftXConfig * scale) + 'px';
    pane.style.marginTop = (shiftYConfig * scale) + 'px';
}
'''
text += calib_logic

with open('export/app.js', 'w', encoding='utf-8') as f:
    f.write(text)
