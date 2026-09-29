const fs = require('fs');
const path = require('path');
const dir = path.join(__dirname, 'assets', 'postupy');

const files = fs.readdirSync(dir).filter(f => f.endsWith('.geojson'));
files.forEach(f => {
  fs.renameSync(path.join(dir, f), path.join(dir, f.replace('.geojson', '.json')));
});

const newFiles = fs.readdirSync(dir).filter(f => f.endsWith('.json') && f !== 'postupy_index.json');
let out = 'export const geojsons = {\n';
newFiles.forEach(f => {
  out += `  '${f.replace('.json', '')}': require('./${f}'),\n`;
});
out += '};\n';
fs.writeFileSync(path.join(dir, 'geojsons.js'), out);
console.log('done');
