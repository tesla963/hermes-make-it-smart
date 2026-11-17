// Reproduce el bug reportado con el índice REAL de Jorge: marcar un estado y volver a All.
// Uso: node scripts/verify-state-real.mjs
import { readFileSync, writeFileSync, mkdirSync, symlinkSync, existsSync, readdirSync } from 'node:fs'
import { homedir, tmpdir } from 'node:os'
import { resolve, dirname, join } from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const HERMES = process.env.PANEL_HERMES_ROOT || join(homedir(), '.hermes', 'hermes-agent')
const INDICE = join(homedir(), '.hermes/plugin-data/make-it-smart/index.json')

function buscar(prefix) {
  for (const base of [join(HERMES, 'apps/desktop/node_modules'), join(HERMES, 'node_modules'), join(HERMES, 'node_modules/.pnpm')]) {
    if (!existsSync(base)) continue
    if (existsSync(join(base, prefix))) return join(base, prefix)
    const hit = readdirSync(base).find((d) => d.startsWith(prefix + '@') || d.startsWith(prefix + '-'))
    if (hit) return join(base, hit, 'node_modules', prefix)
  }
  return null
}

const sandbox = join(tmpdir(), 'mms-panel-harness')
const nm = join(sandbox, 'node_modules')
mkdirSync(nm, { recursive: true })
for (const pkg of ['react', 'react-dom', 'scheduler', 'jsdom']) {
  const dst = join(nm, pkg)
  if (existsSync(dst)) continue
  symlinkSync(buscar(pkg), dst)
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

const tmp = join(sandbox, 'plugin-real.mjs')
writeFileSync(tmp, readFileSync(join(root, 'desktop/plugin.js'), 'utf8').replace(
  "from '@hermes/plugin-sdk'", `from '${join(root, 'tests/mocks/plugin-sdk.js')}'`))

const { createElement } = requireSandbox('react')
const { createRoot } = requireSandbox('react-dom/client')
const plugin = (await import(tmp + '?v=' + Date.now())).default

const catalogue = readFileSync(INDICE, 'utf8')
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
await esperar(1200)

const $ = (s) => document.querySelector(s)
const click = (el) => el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
const radios = () => [...document.querySelectorAll('.estados input[name=estado]')]
const etiquetas = () => [...document.querySelectorAll('.estados label')].map((l) => l.textContent.trim())
const marcado = () => radios().findIndex((r) => r.checked)
const contador = () => $('.counter').textContent.replace(/\s+/g, ' ').trim()
const filas = () => document.querySelectorAll('#tb tbody tr.r').length

const marca = async (i) => {
  click(radios()[i])
  await esperar(400)
}

console.log('radios:', etiquetas().join(' | '))
console.log('INICIAL → marcado:', marcado(), '(debe ser -1: ninguno) | filas:', filas(), '| chips:', document.querySelectorAll('#chipwrap .chip').length)
let fallos = 0
const check = (nombre, cond, extra = '') => {
  if (!cond) fallos++
  console.log(cond ? 'ok  ' : 'FALLA', nombre, extra)
}

const limpio = async () => {
  // deja el módulo sin ningún estado marcado
  for (let i = 0; i < radios().length; i++) {
    if (radios()[i].checked) { click(radios()[i]); await esperar(250) }
  }
}

console.log('INICIAL → marcado:', marcado(), '(debe ser -1) | filas:', filas(), '| chips:', document.querySelectorAll('#chipwrap .chip').length)

// 1) «All» es un interruptor: primer clic lo enciende, segundo lo apaga
await marca(0)
const onAll = { marcado: marcado(), chips: document.querySelectorAll('#chipwrap .chip').length, filas: filas() }
await marca(0)
const offAll = { marcado: marcado(), chips: document.querySelectorAll('#chipwrap .chip').length, filas: filas() }
check('All se enciende con un clic (chip incluido)', onAll.marcado === 0 && onAll.chips === 1, JSON.stringify(onAll))
check('All muestra la unión de las categorías, no el archivo entero', onAll.filas === 130, `(${onAll.filas} filas)`)
check('All se apaga con otro clic (sin chip y con las 903)', offAll.marcado === -1 && offAll.chips === 0 && offAll.filas === 903, JSON.stringify(offAll))

// 2) cada estado aísla su grupo y All vuelve al total
for (let i = 1; i < radios().length; i++) {
  await limpio()
  const nombre = etiquetas()[i]
  const esperado = { 1: 3, 2: 0, 3: 105, 4: 12, 5: 10 }[i]
  await marca(i)
  const n = filas()
  const chips = [...document.querySelectorAll('#chipwrap .chip')].map((c) => c.textContent.replace('✕', '').trim())
  check(`${nombre} deja ${esperado} filas`, n === esperado, `(${n} filas · chip ${JSON.stringify(chips)})`)
  // el chip se puede quitar con su ✕
  const x = document.querySelector('#chipwrap .chip b')
  if (x) { click(x); await esperar(350) }
  check(`la ✕ del chip quita ${nombre}`, filas() === 903 && marcado() === -1, `(${filas()} filas)`)
}


