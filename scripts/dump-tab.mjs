// Vuelca la pestaña Process (o la que se pida) a un HTML con su CSS, para medirla/capturarla.
// Uso: node scripts/dump-tab.mjs "Process" /tmp/process.html
import { readFileSync, writeFileSync, mkdirSync, symlinkSync, existsSync, readdirSync } from 'node:fs'
import { homedir, tmpdir } from 'node:os'
import { resolve, dirname, join } from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const HERMES = process.env.PANEL_HERMES_ROOT || join(homedir(), '.hermes', 'hermes-agent')
const etiqueta = process.argv[2] || 'Process'
const salida = process.argv[3] || '/tmp/process.html'

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

const tmp = join(sandbox, 'plugin-dump.mjs')
writeFileSync(tmp, readFileSync(join(root, 'desktop/plugin.js'), 'utf8').replace(
  "from '@hermes/plugin-sdk'", `from '${join(root, 'tests/mocks/plugin-sdk.js')}'`))

const { createElement } = requireSandbox('react')
const { createRoot } = requireSandbox('react-dom/client')
const plugin = (await import(tmp + '?v=' + Date.now())).default

const base = { mmm: 1, iq2: '', iq3: '', iq3i: '', iq4: '', iq5: '2026', iq6: '', iq7: '', iq8: '', iq9: '', desc: '', verb: '', prof: 'default', costo: 0.004, horas: 0.5, tok: 12000, posts: 3 }
// Pendiente = raw SIN número. Así Process y Session DB tienen universos distintos.
const sesiones = [
  { ...base, n: 1, sujeto: 'Alfa', iq0: 'Alfa', iq1: 'Apple', raw: 'revisar el chat viejo', id: 'p1', fecha: '2026-11-01', esCron: false, motor: 'DeepSeek Flash', pendTot: 2 },
  { ...base, n: 2, sujeto: 'Alfa', iq0: 'Alfa', iq1: 'Apple', raw: 'ordenar notas sueltas', id: 'p2', fecha: '2026-11-02', esCron: false, motor: 'DeepSeek Flash', pendTot: 1 },
  { ...base, n: 3, sujeto: 'Beta', iq0: 'Beta', iq1: 'Apple', raw: 'revisar el disco externo', id: 'p3', fecha: '2026-11-03', esCron: false, motor: 'Claude', pendTot: 1 },
  { ...base, n: 4, sujeto: 'Bot', iq0: 'Bot', iq1: 'Apple', raw: 'Bot Chat', id: 'bot1', fecha: '2026-11-04', esCron: false, motor: 'DeepSeek Flash', pendTot: 0 },
  { ...base, n: 5, sujeto: 'Sub', iq0: 'Sub', iq1: 'Apple', raw: 'Subagent: traducir el manual', id: 'sub1', fecha: '2026-11-05', esCron: false, motor: 'DeepSeek Flash', pendTot: 0 },
  { ...base, n: 11, sujeto: 'Gamma', iq0: 'Gamma', iq1: 'Linux', raw: '011 [Gamma] 001 Investigar tema', id: 'g1', fecha: '2026-11-04', esCron: false, motor: 'Claude', pendTot: 0 },
  { ...base, n: 12, sujeto: 'Gamma', iq0: 'Gamma', iq1: 'Linux', raw: '012 [Gamma] 002 Revisar disco', id: 'g2', fecha: '2026-11-05', esCron: false, motor: 'Claude', pendTot: 0 },
]
// con el 5º argumento «real» se usa el índice real en lugar del mock
const usarReal = (process.argv[5] || '').toLowerCase() === 'real'
const catalogue = usarReal
  ? readFileSync(join(homedir(), '.hermes/plugin-data/make-it-smart/index.json'), 'utf8')
  : JSON.stringify({ schema: 1, generated: '2026-11-16T00:00:00', count: sesiones.length, subjects: [], facets: {}, sessions: sesiones })

const seen = []
plugin.register({
  registerMany: (i) => seen.push(...i),
  register: (i) => seen.push(i),
  files: {
    readText: async (a, n) => {
      if (n === 'index.json') return { ok: true, text: catalogue }
      // 6º argumento «pend»: simula el mapa de pendientes para ver la columna PENDING
      if (n === 'pending_index.json' && (process.argv[6] || '').toLowerCase() === 'pend') {
        const by_session = Object.fromEntries(sesiones.map((x) => [x.id, { mem: ['m'], skl: ['s'] }]))
        return { ok: true, text: JSON.stringify({ by_session, attribution: {} }) }
      }
      return { ok: false, text: '' }
    },
    writeText: async () => ({ ok: false }),
  },
  os: {},
  rpc: async () => ({ ok: false }),
})

createRoot(document.getElementById('root')).render(createElement(seen.find((x) => x.render).render))
const esperar = (ms) => new Promise((r) => setTimeout(r, ms))
await esperar(700)

// clic en la pestaña pedida
const tabs = [...document.querySelectorAll('button, [role=tab], .tab')]
const tab = tabs.find((b) => new RegExp(etiqueta, 'i').test(b.textContent || ''))
if (tab) {
  tab.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
  await esperar(500)
} else {
  console.log('no encontré la pestaña', etiqueta, '| candidatas:', tabs.map((b) => (b.textContent || '').trim()).filter(Boolean).slice(0, 10).join(' / '))
}

// opcional: marcar un filtro de estado antes de volcar (p. ej. "Bots")
const estadoPedido = process.argv[4]
if (estadoPedido) {
  const radio = [...document.querySelectorAll('.estados label')].find((l) => new RegExp(estadoPedido, 'i').test(l.textContent))
  if (radio) {
    // un solo clic en el control: con checkbox, dos clics lo dejarían como estaba
    const inp = radio.querySelector('input')
    inp.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }))
    await esperar(400)
  } else {
    console.log('no encontré el estado', estadoPedido)
  }
}

const estilos = [...document.querySelectorAll('style')].map((s) => s.textContent).join('\n')
const html = document.getElementById('root').innerHTML
writeFileSync(salida, `<!doctype html><meta charset="utf-8">\n<style>html,body{margin:0;background:#0d0b0e;height:100%}.mmws{height:840px}</style>\n<style>${estilos}</style>\n${html}`)
console.log('pestaña:', etiqueta, '| chars:', html.length, '| css:', estilos.length, '| →', salida)
