// Compara las claves de I18N.es y I18N.en evaluando el objeto real del plugin.
const fs = require('fs')
const path = process.argv[2] || 'desktop/plugin.js'
const src = fs.readFileSync(path, 'utf8')

const i = src.indexOf('const I18N = {')
if (i < 0) { console.error('no encontré I18N'); process.exit(1) }
const ini = src.indexOf('{', i)
let prof = 0, fin = ini
for (let j = ini; j < src.length; j++) {
  const c = src[j]
  if (c === '{') prof++
  else if (c === '}') { prof--; if (prof === 0) { fin = j; break } }
}
const bloque = src.slice(ini, fin + 1)
let obj
try { obj = new Function('return ' + bloque)() }
catch (e) { console.error('no se pudo evaluar I18N:', e.message); process.exit(2) }

const es = Object.keys(obj.es || {}), en = Object.keys(obj.en || {})
const faltan = es.filter(k => !(k in (obj.en || {})))
const sobran = en.filter(k => !(k in (obj.es || {})))
console.log('es:', es.length, '· en:', en.length)
console.log('faltan en EN:', faltan.length, faltan.slice(0, 40).join(' '))
console.log('sobran en EN:', sobran.length)

// ¿queda algún valor EN idéntico al español y con pinta de español?
const ES = /\b(el|la|los|las|de|del|que|para|con|sin|una|por|tu|se|es|más|cuando|desde|hasta|esto|esta|todo|solo|sólo|podés|cargues|Falló|Guardar)\b/i
const enEspanol = en.filter(k => obj.es[k] === obj.en[k] && ES.test(obj.en[k]))
console.log('EN en español:', enEspanol.length, enEspanol.slice(0, 20).join(' '))
