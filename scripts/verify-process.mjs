// Verifica que Process tenga su propio universo y sus propios filtros:
// 1) las facetas sólo cuentan pendientes; 2) filtrar en Process no toca Session DB.
// Uso: node scripts/verify-process.mjs
import { readFileSync, writeFileSync, mkdirSync, symlinkSync, existsSync, readdirSync } from 'node:fs'
import { homedir, tmpdir } from 'node:os'
import { resolve, dirname, join } from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
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

const tmp = join(sandbox, 'plugin-process.mjs')
writeFileSync(tmp, readFileSync(join(root, 'desktop/plugin.js'), 'utf8').replace(
  "from '@hermes/plugin-sdk'", `from '${join(root, 'tests/mocks/plugin-sdk.js')}'`))

const { createElement } = requireSandbox('react')
const { createRoot } = requireSandbox('react-dom/client')
const plugin = (await import(tmp + '?v=' + Date.now())).default

// Pendiente = raw SIN número. Los que llevan número ya están procesados.
const base = { mmm: 1, iq1: 'Apple', iq2: '', iq3: '', iq3i: '', iq4: '', iq5: '2026', iq6: '', iq7: '', iq8: '', iq9: '', desc: '', verb: '', prof: 'default', costo: 0, horas: 0, tok: 0, posts: 1, motor: 'DeepSeek Flash' }
const sesiones = [
  // 3 pendientes: Alfa x2, Beta x1
  { ...base, n: 1, sujeto: 'Alfa', iq0: 'Alfa', raw: 'revisar el chat viejo', id: 'p1', fecha: '2026-11-01', esCron: false },
  { ...base, n: 2, sujeto: 'Alfa', iq0: 'Alfa', raw: 'ordenar notas sueltas', id: 'p2', fecha: '2026-11-02', esCron: false },
  { ...base, n: 3, sujeto: 'Beta', iq0: 'Beta', raw: 'revisar el disco externo', id: 'p3', fecha: '2026-11-03', esCron: false },
  // 1 Bot Chat y 1 subagente: maquinaria, nunca se renombran
  { ...base, n: 4, sujeto: 'Bot', iq0: 'Bot', raw: 'Bot Chat', id: 'bot1', fecha: '2026-11-04', esCron: false },
  { ...base, n: 5, sujeto: 'Sub', iq0: 'Sub', raw: 'Subagent: traducir el manual', id: 'sub1', fecha: '2026-11-05', esCron: false },
  // 5 ya procesadas, sujeto Gamma
  ...Array.from({ length: 5 }, (_, i) => ({
    ...base, n: 10 + i, sujeto: 'Gamma', iq0: 'Gamma',
    raw: `0${10 + i} [Gamma] 00${i + 1} Investigar tema`, id: 'g' + i, fecha: '2026-11-0' + (i + 1), esCron: false,
  })),
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
await esperar(700)

const $ = (s) => document.querySelector(s)
const click = (el) => el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
const filas = () => document.querySelectorAll('#tb tbody tr.r').length
const chips = () => [...document.querySelectorAll('#chipwrap .chip')].map((c) => c.textContent.replace('✕', '').trim())
const facetasSujeto = () => [...document.querySelectorAll('.ascroll label.opt')].map((l) => l.textContent.trim())
const irA = async (nombre) => {
  const tab = [...document.querySelectorAll('button')].find((b) => new RegExp(nombre, 'i').test(b.textContent || ''))
  if (tab) { click(tab); await esperar(500) }
}

let fallos = 0
const check = (nombre, cond, extra = '') => {
  if (!cond) fallos++
  console.log(cond ? 'ok  ' : 'FALLA', nombre, extra)
}

check('Session DB ve las 10 sesiones', filas() === 10, `(${filas()})`)

await irA('Process')
check('Process ve sólo las 3 pendientes', filas() === 3, `(${filas()})`)

const facetas = facetasSujeto()
const texto = facetas.join(' ')
check('la faceta de sujeto no lista el sujeto de las ya procesadas', !/Gamma/.test(texto), `→ ${texto.slice(0, 60) || '(vacío)'}`)
check('la faceta de sujeto lista Alfa (2) y Beta (1)', /Alfa/.test(texto) && /Beta/.test(texto), `→ ${texto.slice(0, 60) || '(vacío)'}`)

// 1) el estado Bots sustituye al universo dentro de Process
const radiosB = [...document.querySelectorAll('.estados input[name=estado]')]
const marca = async (i) => {
  if (!radiosB[i]) return false
  click(radiosB[i])
  radiosB[i].dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await esperar(400)
  return true
}

check('el panel tiene un radio propio para Subagentes', radiosB.length === 6, `(${radiosB.length} radios)`)

if (await marca(4)) {
  check('el filtro Bots deja sólo el Bot Chat', filas() === 1, `(${filas()} filas)`)
  check('Bots no incluye al subagente', !/Subagent/.test(document.querySelector('#tb tbody').textContent), '(sin subagente)')
  const aviso = $('#avisoMaquinaria')
  check('se avisa que son sesiones de máquina y no se renombran', !!aviso && /máquina|machine/i.test(aviso.textContent), aviso ? aviso.textContent.trim().slice(0, 60) : '(sin aviso)')
  check('el contador usa el universo de bots', /1\s*(of|de)\s*1/i.test($('.counter').textContent), `(${$('.counter').textContent.trim()})`)
} else {
  check('encontrar el radio Bots', false, `(radios: ${radiosB.length})`)
}

if (await marca(5)) {
  check('el filtro Subagentes deja sólo su sesión', filas() === 1, `(${filas()} filas)`)
  check('Subagentes no incluye al Bot Chat', !/Bot Chat/.test(document.querySelector('#tb tbody').textContent), '(sin bot chat)')
} else {
  check('encontrar el radio Subagentes', false, '(no existe)')
}

// 2) volver a All: otra vez las pendientes
if (radiosB[0]) {
  click(radiosB[0])
  radiosB[0].dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await esperar(400)
}
check('al volver a All reaparecen las pendientes', filas() === 3, `(${filas()} filas)`)
check('el aviso desaparece fuera de Bots', !$('#avisoMaquinaria'), '')

// 3) filtrar por Alfa dentro de Process
const etiquetaAlfa = [...document.querySelectorAll('.ascroll label.opt')].find((l) => /^Alfa/.test(l.textContent.trim()))
if (etiquetaAlfa) {
  const radio = etiquetaAlfa.querySelector('input')
  click(etiquetaAlfa)
  click(radio)
  radio.dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  radio.dispatchEvent(new dom.window.Event('input', { bubbles: true }))
  await esperar(400)
  check('filtrar Alfa en Process deja 2 filas', filas() === 2, `(${filas()})`)
  check('el filtro aparece como chip', chips().length > 0, JSON.stringify(chips()))
} else {
  check('encontrar la faceta Alfa', false, '(no encontrada)')
}

// 4) autonomía: Session DB no hereda nada
await irA('Session Datab')
check('Session DB no hereda el filtro de Process', filas() === 10, `(${filas()})`)
check('Session DB no muestra el chip de Process', chips().length === 0, JSON.stringify(chips()))

// 5) y Process conserva su filtro al volver
await irA('Process')
check('Process conserva su propio filtro al volver', filas() === 2, `(${filas()})`)

// New Rules es una tercera ventana con su propio panel
await irA('New Rules')
check('New Rules ve su propio universo (todas)', filas() === 10, `(${filas()})`)
check('New Rules no hereda el filtro de Process', chips().length === 0, JSON.stringify(chips()))
const rnr = [...document.querySelectorAll('.estados input[name=estado]')]
if (rnr[4]) {
  click(rnr[4])
  rnr[4].dispatchEvent(new dom.window.Event('change', { bubbles: true }))
  await esperar(400)
  check('en New Rules el estado Bots filtra', filas() === 1, `(${filas()} filas)`)
  check('y lo dice en su chip', chips().some((c) => /Bots/.test(c)), JSON.stringify(chips()))
}

await irA('Process')
check('Process conserva su filtro tras pasar por New Rules', filas() === 2, `(${filas()})`)
check('Process no hereda el Bots de New Rules', !chips().some((c) => /^Bots/.test(c)), JSON.stringify(chips()))

await irA('New Rules')
check('New Rules conserva su Bots al volver', chips().some((c) => /Bots/.test(c)) && filas() === 1, `(${filas()} · ${JSON.stringify(chips())})`)

console.log(fallos ? `\n${fallos} comprobación(es) fallida(s)` : '\ntodo en verde')
process.exit(fallos ? 1 : 0)
