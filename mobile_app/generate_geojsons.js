const fs = require('fs');
const files = fs.readdirSync('assets/postupy').filter(f => f.endsWith('.geojson'));
let out = 'export const geojsons = {\n';
files.forEach(f => {
  out += `  '${f.replace('.geojson', '')}': require('./${f}'),\n`;
});
out += '};\n';
fs.writeFileSync('assets/postupy/geojsons.js', out);
console.log('done');
