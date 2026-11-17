// Arnés interactivo: monta el plugin real en jsdom y permite disparar clics de verdad.
// El render estático NO trae handlers; sólo este arnés prueba que un botón hace algo.
// Uso: node scripts/verify-clicks.mjs
import { readFileSync, writeFileSync, mkdirSync, symlinkSync, existsSync, readdirSync } from 'node:fs'
import { homedir, tmpdir } from 'node:os'
import { resolve, dirname, join } from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
// ojo: HERMES_HOME ya está definido en el entorno como ~/.hermes; no reutilizarlo.
const HERMES = process.env.PANEL_HERMES_ROOT || join(homedir(), '.hermes', 'hermes-agent')

function buscar(prefix) {
  for (const base of [join(HERMES, 'apps/desktop/node_modules'), join(HERMES, 'node_modules'), join(HERMES, 'node_modules/.pnpm')]) {
    if (!existsSync(base)) continue
    if (existsSync(join(base, prefix))) return join(base, prefix)
    const hit = readdirSync(base).find((d) => d.startsWith(prefix + '@') || d.startsWith(prefix + '-'))
    if (hit) return join(base, hit, 'node_modules', prefix)
  }
  return null
}

// node_modules propio del arnés por SYMLINK: Node resuelve desde el path real del store
// de pnpm, donde cada paquete tiene sus dependencias hermanas. Copiar el árbol las pierde.
// fuera del repo: el árbol de pruebas no debe ensuciar el checkout que se publica
const sandbox = join(tmpdir(), 'mms-panel-harness')
const nm = join(sandbox, 'node_modules')
mkdirSync(nm, { recursive: true })
for (const pkg of ['react', 'react-dom', 'scheduler', 'jsdom']) {
  const dst = join(nm, pkg)
  if (existsSync(dst)) continue
  const src = buscar(pkg)
  if (!src) throw new Error(`no encontré ${pkg} bajo ${HERMES}`)
  symlinkSync(src, dst)
}

const requireSandbox = createRequire(join(nm, 'puente.cjs'))
const { JSDOM } = requireSandbox('jsdom')

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'http://localhost/', pretendToBeVisual: true })
globalThis.window = dom.window
globalThis.document = dom.window.document
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
for (const k of ['HTMLElement', 'Element', 'Node', 'Event', 'MouseEvent', 'getComputedStyle']) globalThis[k] = dom.window[k]
globalThis.requestAnimationFrame = (cb) => setTimeout(cb, 0)
globalThis.cancelAnimationFrame = (id) => clearTimeout(id)
globalThis.IS_REACT_ACT_ENVIRONMENT = true

const tmp = join(sandbox, 'plugin-under-test.mjs')
writeFileSync(
  tmp,
  readFileSync(join(root, 'desktop/plugin.js'), 'utf8').replace(
    "from '@hermes/plugin-sdk'",
    `from '${join(root, 'tests/mocks/plugin-sdk.js')}'`
  )
)

const { createElement } = requireSandbox('react')
const { createRoot } = requireSandbox('react-dom/client')
const plugin = (await import(tmp + '?v=' + Date.now())).default

const base = { mmm: 1, iq2: '', iq3: '', iq3i: '', iq4: '', iq5: '2026', iq6: '', iq7: '', iq8: '', iq9: '', desc: '', verb: '', prof: 'default', costo: 0, horas: 0, tok: 0, posts: 1 }
const sesiones = [
  { ...base, n: 1, sujeto: 'Alfa', iq1: 'Apple', raw: '001 [Alfa] 001 Investigar', id: 's1', fecha: '2026-11-01', esCron: false, motor: 'DeepSeek Flash' },
  { ...base, n: 2, sujeto: 'Beta', iq1: 'Apple', raw: '002 [Beta] 001 Revisar', id: 'cron_abc', fecha: '2026-11-02', esCron: true, cron: 'job', cronJob: 'limpieza', motor: 'DeepSeek Flash' },
  { ...base, n: 3, sujeto: 'Gamma', iq1: 'Linux', tema: 'Borrada', raw: '003 [Gamma] 001 Borrar', id: 's3', fecha: '2026-11-03', esCron: false, motor: 'Claude' },
  { ...base, n: 4, sujeto: 'Delta', iq1: 'Apple', raw: '004 [Delta] 001 Bot', id: 's4', fecha: '2026-11-04', esCron: false, esBot: true, bot: 'bridge', motor: 'Claude' },
]
const catalogue = JSON.stringify({ schema: 1, generated: '2026-11-16T00:00:00', count: sesiones.length, subjects: [], facets: {}, sessions: sesiones })

const seen = []
plugin.register({
  registerMany: (i) => seen.push(...i),
  register: (i) => seen.push(i),
  files: { readText: async (a, n) => (n === 'index.json' ? { ok: true, text: catalogue } : { ok: false, text: '' }), writeText: async () => ({ ok: false }) },
  os: {},
  rpc: async () => ({ ok: false }),
})

createRoot(document.getElementById('root')).render(createElement(seen.find((x) => x.render).render))
const esperar = (ms) => new Promise((r) => setTimeout(r, ms))
await esperar(600)

const $ = (s) => document.querySelector(s)
const click = (el) => el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
const panel = () => ($('#panel') ? $('#panel').className : 'sin panel')
const filas = () => document.querySelectorAll('#tb tbody tr.r').length
const chips = () => [...document.querySelectorAll('#chipwrap .chip')].map((c) => c.textContent.replace('✕', '').trim())
const flechas = () => [...document.querySelectorAll('.railnav')].map((n) => n.disabled)
const radios = () => [...document.querySelectorAll('.estados input[name=estado]')]
const ok = (c) => (c ? 'ok  ' : 'FALLA')

let fallos = 0
const check = (nombre, cond, extra = '') => {
  if (!cond) fallos++
  console.log(ok(cond), nombre, extra)
}

check('la tabla pinta filas', filas() === 4, `(${filas()})`)
check('el panel arranca cerrado', panel() === 'panel', `(${panel()})`)

click($('.railtxt'))
await esperar(300)
check('el texto del rail ABRE la ficha', panel().includes('on'), `(${panel()})`)

const f = flechas()
check('con la ficha abierta la flecha arriba está apagada y la de abajo activa', f[0] === true && f[1] === false, JSON.stringify(f))

click($('.railtxt'))
await esperar(300)
check('segundo clic CIERRA la ficha', !panel().includes('on'), `(${panel()})`)

click($('#tabInfo'))
await esperar(300)
check('la zona vacía del rail también abre', panel().includes('on'), `(${panel()})`)

click(radios()[3])
await esperar(300)
check('Cron aísla su grupo', filas() === 1, `(${filas()} filas)`)
check('Cron aparece como chip', chips().some((c) => /Cron/.test(c)), JSON.stringify(chips()))

const inp = $('input[type=text], input[type=search]')
if (inp) {
  const set = Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, 'value').set
  set.call(inp, 'Gamma')
  inp.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await esperar(300)
  check('otro filtro se aplica DENTRO del estado (Gamma es borrada, no cron)', filas() === 0, `(${filas()} filas)`)
  set.call(inp, '')
  inp.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await esperar(300)
}

const x = $('#chipwrap .chip b')
if (x) {
  click(x)
  await esperar(300)
}
// sin ningún estado marcado se ven todas, especiales incluidas
const marcadoAhora = radios().find((r) => r.checked)
if (marcadoAhora) { click(marcadoAhora); await esperar(350) }
check('sin estado se ven todas las sesiones', filas() === 4, `(${filas()} filas)`)

// «All from State» es la unión de las categorías del módulo, no el archivo entero
click(radios()[3])
await esperar(300)
const conCron = filas()
click(radios()[0])
await esperar(400)
check('All from State muestra la unión (cron + borrada + bot)', filas() === 3, `(tras Cron ${conCron} → ahora ${filas()})`)
check('su chip lo dice', chips().some((c) => /All/i.test(c)), JSON.stringify(chips()))

// y desmarcarlo devuelve el archivo completo
click(radios()[0])
await esperar(400)
check('desmarcar All devuelve todas las sesiones', filas() === 4, `(${filas()} filas)`)
check('sin ningún estado marcado', radios().every((r) => !r.checked), `(${radios().map((r) => r.checked ? 'X' : '.').join('')})`)

console.log(fallos ? `\n${fallos} comprobaci${fallos === 1 ? 'ón' : 'ones'} fallida(s)` : '\ntodo en verde')
process.exit(fallos ? 1 : 0)
