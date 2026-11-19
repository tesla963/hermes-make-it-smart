#!/usr/bin/env node
/**
 * Plugin smoke test — runs the real desktop/plugin.js outside Hermes.
 *
 * The file is loaded UNCOMPILED by the host, so a syntax error or a bad import
 * is a white screen for the user. This catches both before install:
 *
 *   1. the module parses and exposes { id, name, version, register }
 *   2. register() declares exactly two areas: the page and the sidebar entry
 *   3. the component renders a first frame without throwing
 *   4. the pure formatters behave
 *
 *   node tests/test_plugin.mjs
 */
import { existsSync, mkdtempSync, readFileSync, rmSync, unlinkSync, writeFileSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..')
const pluginPath = join(root, 'desktop', 'plugin.js')

// React lives in different node_modules depending on how Hermes was built: the
// repo root in some installs, apps/desktop in others. Try every plausible one
// before falling back, so the test runs against the real React when it exists.
const HOME = process.env.HOME || ''
const REACT_CANDIDATES = [
  process.env.HERMES_REACT_DIR,
  join(HOME, '.hermes', 'hermes-agent', 'node_modules'),
  join(HOME, '.hermes', 'hermes-agent', 'apps', 'desktop', 'node_modules'),
  join(HOME, '.hermes', 'hermes-agent', 'apps', 'shared', 'node_modules'),
].filter(Boolean)

const asUrl = (p) => pathToFileURL(p).href

const HERMES = REACT_CANDIDATES.find(
  (dir) =>
    existsSync(join(dir, 'react', 'jsx-runtime.js')) &&
    existsSync(join(dir, 'react', 'index.js')) &&
    existsSync(join(dir, 'react-dom', 'server.js'))
)

const hasHermesReact = Boolean(HERMES)

// The fallback modules are written to disk: a data: URL keeps literal quotes and
// parentheses that break the import when the specifier is single-quoted.
const fallbackDir = hasHermesReact ? null : mkdtempSync(join(tmpdir(), 'mmws-react-'))
const writeFallback = (name, code) => {
  const file = join(fallbackDir, name)
  writeFileSync(file, code)
  return asUrl(file)
}

const REACT_JSX_FALLBACK = hasHermesReact
  ? null
  : writeFallback(
      'jsx-runtime.mjs',
      `
    export const jsx = (type, props, key) => ({ $$vnode: true, type, props: props || {}, key });
    export const jsxs = jsx;
    export const Fragment = Symbol.for('react.fragment');
  `
    )

const REACT_FALLBACK = hasHermesReact
  ? null
  : writeFallback(
      'react.mjs',
      `
    export const useState = (init) => [typeof init === 'function' ? init() : init, () => {}];
    export const useEffect = () => {};
    export const useMemo = (fn) => fn();
    export const useRef = (val) => ({ current: val });
    export const createElement = (type, props, ...children) => ({
      $$vnode: true,
      type,
      props: { ...(props || {}), children: children.length <= 1 ? children[0] : children },
    });
    export default { useState, useEffect, useMemo, useRef, createElement };
  `
    )


function renderFallbackVnode(node) {
  if (node === null || node === undefined || typeof node === 'boolean') return ''
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(renderFallbackVnode).join('')
  if (typeof node === 'object' && node.$$vnode) {
    if (typeof node.type === 'function') return renderFallbackVnode(node.type(node.props || {}))
    const tag = typeof node.type === 'string' ? node.type : 'div'
    const props = node.props || {}
    const cls = props.className ? ` class="${props.className}"` : ''
    const id = props.id ? ` id="${props.id}"` : ''
    const inner =
      props.dangerouslySetInnerHTML && props.dangerouslySetInnerHTML.__html
        ? String(props.dangerouslySetInnerHTML.__html)
        : renderFallbackVnode(props.children)
    return `<${tag}${id}${cls}>${inner}</${tag}>`
  }
  return ''
}

const jsxSpec = hasHermesReact ? asUrl(join(HERMES, 'react', 'jsx-runtime.js')) : REACT_JSX_FALLBACK
const reactSpec = hasHermesReact ? asUrl(join(HERMES, 'react', 'index.js')) : REACT_FALLBACK

// Rewrite the three specifiers to files node can actually resolve here.
const src = readFileSync(pluginPath, 'utf8')
  .replace(/from '@hermes\/plugin-sdk'/g, `from '${asUrl(join(here, 'mocks', 'plugin-sdk.js'))}'`)
  .replace(/from 'react\/jsx-runtime'/g, `from '${jsxSpec}'`)
  .replace(/from 'react'/g, `from '${reactSpec}'`)

const tmp = join(root, '.plugin-under-test.mjs')
writeFileSync(tmp, src)

let failures = 0
const ok = (cond, msg) => {
  console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${msg}`)
  if (!cond) failures++
}

try {
const mod = await import(asUrl(tmp) + '?v=' + Date.now())
const plugin = mod.default

console.log('\n§ forma del plugin')
ok(plugin && typeof plugin === 'object', 'exports a default object')
ok(plugin.id === 'make-it-smart', 'id is the storage key (make-it-smart)')
ok(/Smart!$/.test(plugin.name || ''), "name ends in 'Smart!'")
ok(/^\d+\.\d+\.\d+$/.test(plugin.version || ''), 'version is semver')
ok(typeof plugin.register === 'function', 'register() exists')

console.log('\n§ register()')
const seen = []
plugin.register({
  registerMany: (items) => seen.push(...items),
  register: (item) => seen.push(item),
  files: { readText: async () => ({ ok: false }), writeText: async () => ({ ok: false }) },
  os: {},
})
ok(seen.length === 4, `declares 4 entries (got ${seen.length})`)
ok(seen.some((x) => x.render), 'one entry renders a component')
ok(seen.some((x) => x.data && x.data.path), 'one entry carries a route path')

console.log('\n§ buscar en el plugin (paleta + atajo)')
const paletteRow = seen.find((x) => x.area === 'palette')
ok(Boolean(paletteRow), 'offers a palette row (⌘K)')
ok(paletteRow && /Smart/.test(paletteRow.data.label), 'the palette row names the plugin')
ok(paletteRow && typeof paletteRow.data.run === 'function', 'the palette row has a handler')

const atajo = seen.find((x) => x.area === 'keybinds')
ok(Boolean(atajo), 'offers a keybind')
ok(atajo && atajo.data.defaults && atajo.data.defaults.length === 1, 'the keybind ships a default combo')
ok(atajo && atajo.data.defaults[0] === 'mod+alt+s', 'the default combo is mod+alt+s')
ok(atajo && atajo.data.category === 'navigation', 'the keybind sits in the navigation section')

const sdkMock = await import(asUrl(join(here, 'mocks', 'plugin-sdk.js')))
if (paletteRow) {
  paletteRow.data.run()
  ok(sdkMock.host.__navigated === '/smart?focus=1', 'the palette row opens the page with the focus flag')
}
if (atajo) {
  sdkMock.host.__navigated = null
  atajo.data.run()
  ok(sdkMock.host.__navigated === '/smart?focus=1', 'the keybind without a selection only opens and focuses')
}

console.log('\n§ enlace profundo ?q=')
globalThis.window = {
  location: { hash: '#/smart?q=CyberPanel%20VPS' },
  addEventListener() {},
  removeEventListener() {},
  getSelection: () => '',
}
if (typeof mod.leerConsultaHash === 'function') {
  ok(mod.leerConsultaHash() === 'CyberPanel VPS', 'lee la consulta de la dirección')
  globalThis.window.location.hash = '#/smart?focus=1'
  ok(mod.leerConsultaHash() === '', 'focus=1 no trae consulta')
  globalThis.window.location.hash = '#/smart'
  ok(mod.leerConsultaHash() === '', 'sin consulta no hay búsqueda')
  globalThis.window.location.hash = '#/smart?q=%20%20'
  ok(mod.leerConsultaHash() === '', 'espacios en blanco no cuentan como consulta')
} else ok(false, 'leerConsultaHash se exporta')

if (typeof mod.textoSeleccionado === 'function') {
  globalThis.window.getSelection = () => '  Kiteworks  '
  ok(mod.textoSeleccionado() === 'Kiteworks', 'toma la selección de la página y la recorta')
  globalThis.window.getSelection = () => ''
  ok(mod.textoSeleccionado() === '', 'sin selección devuelve cadena vacía')
} else ok(false, 'textoSeleccionado se exporta')

delete globalThis.window
if (typeof mod.leerConsultaHash === 'function') {
  ok(mod.leerConsultaHash() === '', 'fuera del navegador devuelve vacío (no rompe los tests)')
}

// El atajo con selección real debe llevar el texto a la dirección.
globalThis.window = {
  location: { hash: '#/smart' },
  addEventListener() {},
  removeEventListener() {},
  getSelection: () => 'Avata 360',
}
if (atajo) {
  sdkMock.host.__navigated = null
  atajo.data.run()
  ok(
    sdkMock.host.__navigated === '/smart?q=Avata%20360',
    `el atajo codifica la selección (${sdkMock.host.__navigated})`
  )
}
delete globalThis.window

console.log('\n§ primer render')
let renderToStaticMarkup
let createElement
if (hasHermesReact) {
  ;({ renderToStaticMarkup } = await import(asUrl(join(HERMES, 'react-dom', 'server.js'))))
  ;({ createElement } = await import(asUrl(join(HERMES, 'react', 'index.js'))))
} else {
  renderToStaticMarkup = renderFallbackVnode
  ;({ createElement } = await import(REACT_FALLBACK))
}
let html = ''
let threw = null
try {
  const entry = seen.find((x) => x.render)
  html = renderToStaticMarkup(createElement(entry.render))
} catch (e) {
  threw = e
}
ok(!threw, threw ? 'renders: ' + threw.message : 'renders a first frame')
ok(html.includes('mmws'), 'emits the plugin root class')
ok(html.length > 200, `frame has substance (${html.length} chars)`)
ok(/ÚLTIMO USO|LAST USED/.test(html) && html.includes('Up to 8 Hours') && html.includes('Yesterday'),
  'el panel izquierdo pinta el bloque Last Used con sus opciones')

console.log('\n§ funciones puras')
const { numSel, fmtC, fmtH, fmtHoras, fmtN } = mod
if (typeof numSel === 'function') {
  ok(numSel('126,305').has(305), 'numSel reads a comma list')
  ok(numSel('50-53').size === 4, 'numSel expands a range')
  ok(numSel('hola') === null, 'numSel ignores free text')
  ok(numSel('') === null, 'numSel ignores an empty string')
} else ok(false, 'numSel is exported')
if (typeof fmtC === 'function') {
  ok(fmtC(1.5) === '$1.50', 'fmtC gives dollars above 1')
  ok(fmtC(0.07) === '7¢', 'fmtC gives cents below 1')
}
if (typeof fmtH === 'function') {
  ok(fmtH(90) === '1h30', 'fmtH splits hours and minutes')
  ok(fmtH(45) === '45m', 'fmtH keeps minutes under an hour')
}
if (typeof fmtHoras === 'function') {
  ok(fmtHoras(45) === '45m', 'fmtHoras: minutes below an hour')
  ok(fmtHoras(200) === '3h20', 'fmtHoras: hours below a day')
  ok(fmtHoras(3000) === '2d 2h', 'fmtHoras: days below a week')
  ok(fmtHoras(15840) === '1w 4d', 'fmtHoras: weeks below a month')
  ok(fmtHoras(525600) === '1.0y', 'fmtHoras: years from a month up')
  ok(fmtHoras(0) === '—', 'fmtHoras: zero is a dash')
} else ok(false, 'fmtHoras is exported')
if (typeof fmtN === 'function') {
  ok(fmtN(15514624) === '15.5M', 'fmtN scales to millions')
  ok(fmtN(1500) === '1.5k', 'fmtN scales to thousands')
}

console.log('\n§ filtro Last Used')
const { matchLastUsed, getTimestampMs, LAST_USED_OPTS } = mod
if (typeof matchLastUsed === 'function') {
  // Mediodía local fijo: así «hoy» y «ayer» no dependen de la hora a la que corre el test.
  const NOW = new Date(2026, 10, 18, 12, 0, 0).getTime()
  const H = 3600000
  const z = (n) => String(n).padStart(2, '0')
  const ymd = (ms) => {
    const d = new Date(ms)
    return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`
  }
  // Sesión sintética usada hace `h` horas (marca en ms, como la deja el merge).
  const hace = (h) => ({ last_used_ms: NOW - h * H, fecha: ymd(NOW - h * H) })
  const en = (h, k) => matchLastUsed(hace(h), k, NOW)
  const KEYS = ['up_to_8h', '8_16h', '16_24h', '24h', '24_48h', 'today', 'yesterday']

  ok(Array.isArray(LAST_USED_OPTS) && LAST_USED_OPTS.map(([k]) => k).join() === KEYS.join(),
    'Last Used ofrece las 7 opciones en orden')

  // 1. Up to 8 Hours: 0 <= h <= 8 (deriva negativa se clava a 0 con Math.max(0, edad))
  ok(en(0, 'up_to_8h') && en(3, 'up_to_8h') && en(8, 'up_to_8h'), 'up_to_8h incluye 0, 3 y 8 h')
  ok(!en(8.01, 'up_to_8h') && en(-0.05, 'up_to_8h'), 'up_to_8h excluye >8 h y tolera deriva negativa con Math.max(0, edad)')
  // 2. 8 - 16 Hours: 8 < h <= 16
  ok(!en(8, '8_16h') && en(8.01, '8_16h') && en(16, '8_16h'), '8_16h: (8, 16]')
  ok(!en(16.01, '8_16h'), '8_16h excluye >16 h')
  // 3. 16 - 24 Hours: 16 < h <= 24
  ok(!en(16, '16_24h') && en(20, '16_24h') && en(24, '16_24h'), '16_24h: (16, 24]')
  ok(!en(24.01, '16_24h'), '16_24h excluye >24 h')
  // 4. 24 Hours: 0 <= h <= 24, exactamente la suma de los tres tramos anteriores
  ok(en(0, '24h') && en(12, '24h') && en(24, '24h'), '24h incluye 0, 12 y 24 h')
  ok(!en(24.01, '24h') && en(-0.05, '24h'), '24h excluye >24 h y tolera deriva negativa')
  const muestras = [-1, 0, 1, 7.99, 8, 8.5, 15, 16, 16.2, 23, 24, 24.5, 30, 47, 48, 49, 72]
  const sumaOk = muestras.every((h) => {
    const tramos = ['up_to_8h', '8_16h', '16_24h'].filter((k) => en(h, k)).length
    return tramos === (en(h, '24h') ? 1 : 0)
  })
  ok(sumaOk, '24h = 0-8h + 8-16h + 16-24h, sin solapes ni huecos')
  // 5. 24 - 48 Hours: 24 < h <= 48
  ok(!en(24, '24_48h') && en(24.01, '24_48h') && en(48, '24_48h'), '24_48h: (24, 48]')
  ok(!en(48.01, '24_48h'), '24_48h excluye >48 h')
  // 6. Today: fecha === hoy (local)
  ok(matchLastUsed({ fecha: '2026-11-18' }, 'today', NOW), 'today: fecha de hoy')
  ok(!matchLastUsed({ fecha: '2026-11-17' }, 'today', NOW), 'today excluye ayer')
  // 7. Yesterday: fecha === ayer (local)
  ok(matchLastUsed({ fecha: '2026-11-17' }, 'yesterday', NOW), 'yesterday: fecha de ayer')
  ok(!matchLastUsed({ fecha: '2026-11-18' }, 'yesterday', NOW) &&
    !matchLastUsed({ fecha: '2026-11-16' }, 'yesterday', NOW), 'yesterday excluye hoy y anteayer')
  // Cambio de mes: ayer del 1 de diciembre es el 30 de noviembre.
  const DIC1 = new Date(2026, 11, 1, 9, 0, 0).getTime()
  ok(matchLastUsed({ fecha: '2026-11-30' }, 'yesterday', DIC1), 'yesterday cruza el cambio de mes')

  // Derivación de la marca: segundos epoch (gateway), ISO, o sólo fecha.
  const segs = Math.floor((NOW - 5 * H) / 1000)
  ok(matchLastUsed({ started_at: segs }, 'up_to_8h', NOW), 'started_at en segundos epoch se convierte a ms')
  ok(matchLastUsed({ started_at: new Date(NOW - 30 * H).toISOString() }, '24_48h', NOW), 'started_at ISO se interpreta')
  ok(matchLastUsed({ fecha: '2026-11-18' }, 'up_to_8h', NOW) === false &&
    matchLastUsed({ fecha: '2026-11-18' }, '8_16h', NOW) === false &&
    matchLastUsed({ fecha: '2026-11-18' }, 'today', NOW) === true,
    'sólo fecha: nunca inventa medianoche sintética en tramos horarios, pero sí entra en Today')
  ok(!matchLastUsed({}, 'up_to_8h', NOW) && !matchLastUsed({}, 'today', NOW), 'sin marca ni fecha no entra en ningún tramo')
  ok(!matchLastUsed(hace(1), 'desconocida', NOW), 'una clave desconocida no filtra a favor')
  if (typeof getTimestampMs === 'function') {
    ok(getTimestampMs(1700000000, '') === 1700000000000, 'getTimestampMs: segundos → ms')
    ok(getTimestampMs(1700000000000, '') === 1700000000000, 'getTimestampMs: ms se respetan')
    ok(getTimestampMs(null, '') === null, 'getTimestampMs: nada → null')
    ok(getTimestampMs('2026-11-18') === null, 'getTimestampMs: fecha YYYY-MM-DD no se parsea como UTC')
  }

  // Marca real de último uso (SPEC LAST USED FIX): last_used_at manda sobre started_at.
  const fila3h = {
    last_used_at: Math.floor((NOW - 3 * H) / 1000), // epoch segundos, como sale del índice
    started_at: Math.floor((NOW - 30 * H) / 1000),
    fecha: ymd(NOW - 30 * H),
  }
  ok(matchLastUsed(fila3h, 'up_to_8h', NOW), 'last_used_at de hace 3 h entra en up_to_8h')
  ok(!matchLastUsed(fila3h, '24_48h', NOW), 'started_at de hace 30 h no la manda a 24_48h')

  // Today / Yesterday por fecha del último uso: iniciada ayer 23:00, usada hoy 01:00.
  const ayer23 = new Date(2026, 10, 17, 23, 0, 0).getTime()
  const hoy01 = new Date(2026, 10, 18, 1, 0, 0).getTime()
  const filaNoche = { last_used_at: hoy01 / 1000, started_at: ayer23 / 1000, fecha: '2026-11-17' }
  ok(matchLastUsed(filaNoche, 'today', NOW), 'iniciada ayer 23:00 y usada hoy 01:00 cuenta como Today')
  ok(!matchLastUsed(filaNoche, 'yesterday', NOW), '… y no como Yesterday')
  // Igual con la marca ya en ms, como la deja el merge (last_used_ms).
  ok(matchLastUsed({ last_used_ms: hoy01, fecha: '2026-11-17' }, 'today', NOW),
    'last_used_ms real decide Today aunque fecha sea ayer')
  // Sin marca utilizable, respaldo a d.fecha.
  ok(matchLastUsed({ last_used_at: null, fecha: '2026-11-17' }, 'yesterday', NOW),
    'sin marca: Yesterday se decide por fecha')

  // Regresión: sesión vieja reusada hoy con sidecar de ayer (Math.max sobre allCandidates)
  const tsAyer10h = Math.floor((NOW - 10 * H) / 1000)
  const tsHoy1h = Math.floor((NOW - 1 * H) / 1000)
  const candsReuso = [tsAyer10h, tsHoy1h].map((v) => getTimestampMs(v)).filter((ms) => ms != null)
  const maxMsReuso = Math.max(...candsReuso)
  ok(matchLastUsed({ last_used_ms: maxMsReuso }, 'up_to_8h', NOW),
    'regresión: sesión vieja con cache de 10h y live_activity de 1h entra a up_to_8h')
  ok(!matchLastUsed({ last_used_ms: maxMsReuso }, '8_16h', NOW),
    'regresión: sesión vieja reusada no queda atrapada en 8_16h')

  // Regresión: sesión nueva sin index ni cache, solo live.started_at
  const tsNueva30m = Math.floor((NOW - 0.5 * H) / 1000)
  const candsNueva = [null, undefined, tsNueva30m].map((v) => getTimestampMs(v)).filter((ms) => ms != null)
  const maxMsNueva = Math.max(...candsNueva)
  ok(matchLastUsed({ last_used_ms: maxMsNueva }, 'up_to_8h', NOW),
    'regresión: sesión nueva sin cache entra inmediatamente a up_to_8h')

  // Posición: LAST USED es el primer hijo del ascroll, en las dos pestañas.
  const srcLU = readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), '../desktop/plugin.js'), 'utf8')
  ok(/\{ className: 'ascroll' \},\s*bloqueLastUsed,\s*pendMap/.test(srcLU),
    'bloqueLastUsed es el primer bloque del ascroll, antes de Pending')
  ok(!/panelFiltros \? (bloqueLastUsed|null) : (null|bloqueLastUsed)/.test(srcLU),
    'bloqueLastUsed ya no depende de panelFiltros')
} else ok(false, 'matchLastUsed se exporta')

console.log('\n§ sub-sesiones')
const { jerarquia, isChildRow } = mod
if (typeof jerarquia === 'function') {
  // La madre no está entre las filas (oculta, filtrada o desaparecida): la hija es raíz.
  const huerfana = jerarquia([{ id: 'a' }, { id: 'b', parent: 'no-existe', esBot: true }])
  ok(!huerfana.sub.has('b'), 'una fila cuyo padre no está se dibuja como raíz')
  ok(huerfana.rows.length === 2, 'no se añade ni se pierde ninguna fila (los KPI cuentan una vez)')

  // Control: con la madre visible, la hija cuelga justo debajo de ella.
  const arbol = jerarquia([
    { id: 'b', parent: 'a', esBot: true },
    { id: 'x' },
    { id: 'a' },
  ])
  ok(arbol.sub.has('b') && arbol.rows.map((d) => d.id).join() === 'x,a,b', 'la hija cuelga debajo de la madre visible')

  // Una continuación no es jerarquía: el host también pone parent_session_id ahí.
  const continuacion = jerarquia([{ id: 'a' }, { id: 'b', parent: 'a' }])
  ok(!continuacion.sub.has('b'), 'una continuación (sin esBot) no se indenta')

  // Una fila que se apunta a sí misma es raíz.
  const suelta = jerarquia([{ id: 'a', parent: 'a', esBot: true }])
  ok(!suelta.sub.has('a'), 'una sesión que se apunta a sí misma es raíz')

  // Ciclo a→b→a: no entra en bucle y no duplica filas.
  const ciclo = jerarquia([
    { id: 'a', parent: 'b', esBot: true },
    { id: 'b', parent: 'a', esBot: true },
  ])
  ok(ciclo.rows.length === 2, 'un ciclo de padres no duplica ni pierde filas')

  // El orden se conserva para las filas sin jerarquía.
  const plano = jerarquia([{ id: 'a' }, { id: 'b' }, { id: 'c' }])
  ok(plano.rows.map((d) => d.id).join() === 'a,b,c', 'sin jerarquía el orden no cambia')
} else ok(false, 'jerarquia se exporta')

if (typeof isChildRow === 'function') {
  const vis = new Set(['madre'])
  ok(isChildRow({ id: 'h', parent: 'madre', esBot: true }, vis), 'subagente con madre en pantalla: sí')
  ok(!isChildRow({ id: 'h', parent: 'madre' }, vis), 'sin esBot: no')
  ok(!isChildRow({ id: 'h', parent: 'h', esBot: true }, vis), 'auto-padre: no')
  ok(!isChildRow({ id: 'h', parent: 'madre', esBot: true }, null), 'sin conjunto visible: no adivina')
} else ok(false, 'isChildRow se exporta')

console.log('\n§ esquema de ejes (migración)')
const { esEsquemaViejo, migrarEjes, contarEjes } = mod
if (typeof esEsquemaViejo === 'function') {
  // Quien viene de < 0.27.0 trae tagN y ningún sello.
  ok(esEsquemaViejo({ sessions: [{ id: 'a', tag1: 'Apple' }] }), 'tagN sin sello es esquema viejo')
  ok(esEsquemaViejo({ facets: { tag3: { v: 1 } } }), 'también en objetos anidados')
  // Quien ya está en 0.27.0+ no debe ver nunca el aviso.
  ok(!esEsquemaViejo({ schema: 2, sessions: [{ id: 'a', iq1: 'Apple' }] }), 'sello 2 con iqN no es viejo')
  ok(!esEsquemaViejo({ schema: 2, sessions: [] }), 'sello 2 vacío no es viejo')
  ok(!esEsquemaViejo({ sessions: [{ id: 'a', iq1: 'Apple' }] }), 'iqN sin sello tampoco')
  ok(!esEsquemaViejo(null) && !esEsquemaViejo({}), 'sin datos no hay nada que migrar')

  const viejo = { generated: 'x', sessions: [{ id: 'a', tag0: 'Sujeto', tag1: 'Apple', sujeto: 'Mac mini' }], facets: { tag3: { n: 1 } } }
  const { data, renamed } = migrarEjes(viejo)
  ok(renamed === 3, `renombra las 3 claves (${renamed})`)
  ok(data.schema === 2, 'sella schema 2')
  ok(data.sessions[0].iq1 === 'Apple' && data.sessions[0].sujeto === 'Mac mini', 'conserva los valores')
  ok(!JSON.stringify(data).includes('"tag'), 'no queda ninguna clave tag')
  ok(contarEjes(data) === 3, 'cuenta las claves de eje del resultado')

  // Idempotente: migrar lo ya migrado no cambia nada.
  const segunda = migrarEjes(data)
  ok(segunda.renamed === 0 && JSON.stringify(segunda.data) === JSON.stringify(data), 'la segunda pasada no cambia nada')
} else ok(false, 'esEsquemaViejo se exporta')

console.log('\n§ sesiones vírgenes y maquinaria (bug #975)')
const { tieneNumero, esMaquinaria, loadCatalogue, esPendiente, esSujetoInvalido } = mod
if (typeof tieneNumero === 'function' && typeof esMaquinaria === 'function') {
  ok(tieneNumero('973 [Layout teclado] 001 [Steren]'), 'tieneNumero reconoce prefijo canónico NNN')
  ok(tieneNumero('024 [DeepSeek] 001'), 'tieneNumero reconoce prefijo con ceros')
  ok(!tieneNumero('Compare Xfce vs LXQt on Fedora'), 'tieneNumero rechaza título virgen')
  ok(!tieneNumero('Bot Chat'), 'tieneNumero rechaza Bot Chat')
  ok(!tieneNumero('Subagent: Traducir al inglés'), 'tieneNumero rechaza Subagent')

  ok(esMaquinaria({ raw: 'Bot Chat' }), 'esMaquinaria reconoce Bot Chat')
  ok(esMaquinaria({ raw: 'Subagent: Traducir al inglés' }), 'esMaquinaria reconoce Subagent')
  ok(esMaquinaria({ raw: 'Cron: Backup diario', esCron: true }), 'esMaquinaria reconoce Cron')
  ok(esMaquinaria({ raw: '[Sesión Borrada]', sujeto: 'Sesión Borrada' }), 'esMaquinaria reconoce Sesión Borrada')
  ok(!esMaquinaria({ raw: 'Compare Xfce vs LXQt on Fedora' }), 'esMaquinaria rechaza sesión virgen de usuario')

  // Simulación de carga de catálogo con sesión virgen #975 (sin mc, sin claves, con nueva: true)
  const mockSessions = [
    { id: 'canon-1', n: 1, raw: '001 [Assistant] 001 Test', mc: 10, claves: ['test'] },
    { id: 'bot-1', n: 958, raw: 'Bot Chat', mc: 0, claves: [] },
    { id: 'sub-1', n: 962, raw: 'Subagent: Traducir al inglés', mc: 0, claves: [] },
    {
      id: 'local-83588de9b025bf2536d66532d116e5203ca8f8a5a33f57d976da54576304bf02',
      n: 975, mmm: 1, prof: 'default',
      raw: 'Compare Xfce vs LXQt on Fedora',
      date: '', sujeto: '', iq0: '', iq1: '', iq2: '', iq3: '', desc: '', verb: '',
      nueva: true,
    },
  ]
  const mockCtx = {
    files: {
      readText: async (dir, file) => {
        if (file === 'index.json') return { ok: true, text: JSON.stringify({ sessions: mockSessions }) }
        return { ok: false }
      },
    },
    host: {
      listPersistedSessions: async () => [],
      profiles: { list: async () => [{ name: 'default' }] },
    },
  }
  const cat = await loadCatalogue(mockCtx)
  const rows = cat.sessions || []
  const s975 = rows.find((r) => r.n === 975)
  ok(Boolean(s975), 'sesión 975 está presente en el catálogo cargado')
  ok(s975 && s975.vacia === false, 'sesión 975 no se marca vacia (vacia === false)')

  const pending = rows.filter((d) => !esMaquinaria(d) && !tieneNumero(d.raw))
  const machinery = rows.filter((d) => esMaquinaria(d) && d.raw && !tieneNumero(d.raw))
  ok(pending.length === 1 && pending[0].n === 975, 'pendingRows contiene exactamente la sesión 975')
  ok(machinery.length === 2, 'machineryPending contiene exactamente los bots/subagents (2)')

  // Verificación adicional: una sesión sin campos (sujeto/ejes vacíos) NO es vacía si tiene título real
  const mockSinCampos = [
    {
      id: 'local-no-fields',
      n: 976, mmm: 1, prof: 'default',
      raw: 'Instalar servidor Nginx en Debian',
      date: '', sujeto: '', iq0: '', iq1: '', iq2: '', iq3: '', desc: '', verb: '',
    },
  ]
  const mockCtx2 = {
    files: {
      readText: async (dir, file) => {
        if (file === 'index.json') return { ok: true, text: JSON.stringify({ sessions: mockSinCampos }) }
        return { ok: false }
      },
    },
    host: {
      listPersistedSessions: async () => [],
      profiles: { list: async () => [{ name: 'default' }] },
    },
  }
  const cat2 = await loadCatalogue(mockCtx2)
  const s976 = (cat2.sessions || [])[0]
  ok(s976 && s976.vacia === false, 'sesión con campos en blanco pero título real no es vacia (vacia === false)')

  // Verificación de sesión virgen real (caso local-068a24... 'Verificar saldo de $5 en API de Claude')
  const mockVirginClaude = [
    {
      id: 'local-068a241393b79d89c93c72bc27389db0089e6e616dc90c64d753e8725b367960',
      n: 1003, mmm: 1, prof: 'default',
      raw: 'Verificar saldo de $5 en API de Claude',
      date: '', sujeto: '', iq0: '', iq1: '', iq2: '', iq3: '', desc: '', verb: '',
      nueva: true,
    },
    {
      id: '20261007_123848_a5c355',
      n: 657, mmm: 1, prof: 'default',
      raw: '657 [Monitor Portátil Doble] 001 VisionOwl $332 vs MagicRaven: nits, HDMI, DisplayLink, consumo',
      sujeto: 'Monitor Portátil Doble',
      date: '2026-10-07', iq1: '', iq2: '', iq3: 'Compare', desc: 'VisionOwl $332 vs MagicRaven: nits, HDMI, DisplayLink, consumo',
      verb: '',
    },
  ]
  const mockCtxVirgin = {
    files: {
      readText: async (dir, file) => {
        if (file === 'index.json') return { ok: true, text: JSON.stringify({ sessions: mockVirginClaude }) }
        return { ok: false }
      },
    },
    host: {
      listPersistedSessions: async () => [
        {
          id: 'local-068a241393b79d89c93c72bc27389db0089e6e616dc90c64d753e8725b367960',
          title: 'Verificar saldo de $5 en API de Claude',
          source: 'oneshot',
          parent_session_id: null,
          profile_name: 'default',
          message_count: 16,
        },
      ],
      profiles: { list: async () => [{ name: 'default' }] },
    },
  }
  const catVirgin = await loadCatalogue(mockCtxVirgin)
  const rowsVirgin = catVirgin.sessions || []
  const sClaude = rowsVirgin.find((r) => r.id === 'local-068a241393b79d89c93c72bc27389db0089e6e616dc90c64d753e8725b367960')
  const sMonitor = rowsVirgin.find((r) => r.n === 657)

  ok(Boolean(sClaude), 'sesión virgen local-068a24... presente en el catálogo')
  ok(sClaude && sClaude.vacia === false, 'sesión virgen con 16 mensajes no está vacía')
  ok(sClaude && esPendiente(sClaude), 'sesión virgen entra a pendingRows (esPendiente === true)')
  ok(sMonitor && !esPendiente(sMonitor), 'sesión 657 [Monitor Portátil Doble] NO entra a pendingRows (no es verbo de acción)')
  ok(sMonitor && !esSujetoInvalido(sMonitor.raw), 'sujeto [Monitor Portátil Doble] es sustantivo válido (no verbo)')
} else ok(false, 'tieneNumero y esMaquinaria se exportan')

console.log('\n§ ramas del diálogo de confirmación (bug del botón Process)')
const dlgMatch = src.match(/id:\s*['"]dlgOk['"][\s\S]*?onClick:\s*async\s*\(\)\s*=>\s*\{([\s\S]*?)\n\s*\},/)
ok(Boolean(dlgMatch), 'el botón dlgOk y su manejador existen en el código')
if (dlgMatch) {
  const handlerBody = dlgMatch[1]

  // Todos los `kind` emitidos por botones del panel vía setDialogo({ kind: '...' })
  const emittedKinds = [
    ...new Set([...src.matchAll(/setDialogo\(\{\s*kind:\s*['"]([^'"]+)['"]/g)].map((m) => m[1])),
  ]
  ok(emittedKinds.length >= 3, `se detectan los kinds emitidos por el panel (${emittedKinds.join(', ')})`)

  // Todos los `kind` con rama explícita en el manejador de confirmación
  const handledKinds = new Set(
    [...handlerBody.matchAll(/d\.kind\s*===\s*['"]([^'"]+)['"]/g)].map((m) => m[1])
  )

  // Cada kind emitido por la UI DEBE tener su rama correspondiente
  const missing = emittedKinds.filter((k) => !handledKinds.has(k))
  ok(missing.length === 0, missing.length ? `faltan ramas para: ${missing.join(', ')}` : 'todos los kinds emitidos tienen rama')

  // Kinds canónicos esperados
  for (const k of ['process', 'processall', 'restore', 'applynewrules']) {
    ok(handledKinds.has(k), `el manejador tiene rama explícita para '${k}'`)
  }

  // Verificación de comportamiento en runtime con mocks
  const testHandler = new Function('dialogo', 'calls', `
    let setDialogoCalled = false;
    const setDialogo = (v) => { setDialogoCalled = true; };
    const restaurarOriginales = async () => { calls.push('restaurarOriginales'); };
    const procesarTodo = async () => { calls.push('procesarTodo'); };
    const aplicarPropuesta = async () => { calls.push('aplicarPropuesta'); };
    const handleCommit = async () => { calls.push('handleCommit'); };
    return (async () => {
      ${handlerBody}
      return { setDialogoCalled, calls };
    })();
  `)

  // 'process' DEBE llamar a procesarTodo y NUNCA a handleCommit
  const callsProcess = []
  await testHandler({ kind: 'process', n: 5 }, callsProcess)
  ok(callsProcess.includes('procesarTodo'), "dialogo 'process' ejecuta procesarTodo")
  ok(!callsProcess.includes('handleCommit'), "dialogo 'process' NO cae en handleCommit")

  // 'processall' llama a procesarTodo
  const callsProcessAll = []
  await testHandler({ kind: 'processall', n: 5 }, callsProcessAll)
  ok(callsProcessAll.includes('procesarTodo'), "dialogo 'processall' ejecuta procesarTodo")

  // 'restore' llama a restaurarOriginales
  const callsRestore = []
  await testHandler({ kind: 'restore', n: 5 }, callsRestore)
  ok(callsRestore.includes('restaurarOriginales'), "dialogo 'restore' ejecuta restaurarOriginales")

  // 'applynewrules' llama a aplicarPropuesta
  const callsApply = []
  await testHandler({ kind: 'applynewrules', n: 5 }, callsApply)
  ok(callsApply.includes('aplicarPropuesta'), "dialogo 'applynewrules' ejecuta aplicarPropuesta")
}

console.log('\n§ derivación de campos y títulos canónicos (bug títulos kilométricos #975)')
const { derivarCampos, canonicalTitle, esDescClonada } = mod
if (
  typeof derivarCampos === 'function' &&
  typeof canonicalTitle === 'function' &&
  typeof esSujetoInvalido === 'function' &&
  typeof esDescClonada === 'function' &&
  typeof esPendiente === 'function'
) {
  // 1. Derivación del caso exacto #975
  const d975 = derivarCampos('Compare Xfce vs LXQt on Fedora')
  ok(d975 && d975.sujeto === 'Xfce vs LXQt', 'deriva sujeto nominal limpio (Xfce vs LXQt)')
  ok(d975 && d975.context === 'Fedora', 'deriva contexto iq2 (Fedora)')
  ok(d975 && d975.verb === 'Compare', 'deriva intención/verbo iq3 (Compare)')
  ok(d975 && d975.desc === '', 'deja descripción vacía')

  // Derivación desde el título canónico malformado que quedó grabado
  const d975Bad = derivarCampos('975 [Compare Xfce vs LXQt on Fedora] 001 Compare Xfce vs LXQt on Fedora')
  ok(d975Bad && d975Bad.sujeto === 'Xfce vs LXQt', 'deriva sujeto limpio desde título malo grabado en state.db')
  ok(d975Bad && d975Bad.context === 'Fedora', 'deriva contexto Fedora desde título malo')
  ok(d975Bad && d975Bad.verb === 'Compare', 'deriva verbo Compare desde título malo')

  // 2. Frases verbales típicas y guarda nominal
  const dBrave = derivarCampos('Recuperar ventas y pestañas perdidas en Brave')
  ok(dBrave && dBrave.sujeto === 'Ventas y pestañas', 'deriva sujeto nominal (Ventas y pestañas)')
  ok(dBrave && dBrave.context === 'Brave', 'deriva contexto Brave')
  ok(dBrave && dBrave.verb === 'Recuperar', 'deriva verbo Recuperar')

  // Caso 3 solicitado por el dueño: "Instalar y configurar Antigravity"
  // Al quitar el verbo "Instalar", el remanente "y configurar Antigravity" contiene otro verbo
  // y conector colgante: NO es sintagma nominal limpio -> guardia activa, NO emite título.
  const dAnti = derivarCampos('Instalar y configurar Antigravity')
  ok(dAnti === null, 'guardia rechaza "Instalar y configurar Antigravity" al no quedar sintagma nominal limpio')

  // 3. Guardia en frases largas o cláusulas verbales
  const dMonster = derivarCampos('Investigar por qué el servidor de producción se cayó tres veces anoche')
  ok(dMonster === null, 'guardia rechaza frase verbal larga que no es sintagma nominal limpio')

  // 4. canonicalTitle con las reglas del dueño
  // Caso #975 virgen
  const t975Virgin = canonicalTitle({ n: 975, mmm: 1, raw: 'Compare Xfce vs LXQt on Fedora' })
  ok(t975Virgin === '975 [Xfce vs LXQt] 001 [Fedora] · Compare', `título virgen #975 genera: ${t975Virgin}`)

  // Caso #975 ya grabado con título malo (debe repararlo a la forma esperada)
  const t975Bad = canonicalTitle({
    n: 975, mmm: 1,
    raw: '975 [Compare Xfce vs LXQt on Fedora] 001 Compare Xfce vs LXQt on Fedora',
    sujeto: 'Compare Xfce vs LXQt on Fedora',
    desc: 'Compare Xfce vs LXQt on Fedora',
  })
  ok(t975Bad === '975 [Xfce vs LXQt] 001 [Fedora] · Compare', `título malo grabado #975 genera: ${t975Bad}`)

  // Caso Brave
  const tBrave = canonicalTitle({ n: 50, mmm: 1, raw: 'Recuperar ventas y pestañas perdidas en Brave' })
  ok(tBrave === '050 [Ventas y pestañas] 001 [Brave] · Recuperar', `frase Brave genera: ${tBrave}`)

  // Caso Antigravity: guardia en canonicalTitle devuelve d.raw sin emitir título canónico
  const tAnti = canonicalTitle({ n: 10, mmm: 1, raw: 'Instalar y configurar Antigravity' })
  ok(tAnti === 'Instalar y configurar Antigravity', `caso Antigravity NO emite título canónico y devuelve raw: ${tAnti}`)

  // Guardia en canonicalTitle: devuelve d.raw si no se puede derivar sujeto limpio
  const tMonster = canonicalTitle({ n: 99, mmm: 1, raw: 'Investigar por qué el servidor de producción se cayó tres veces anoche' })
  ok(tMonster === 'Investigar por qué el servidor de producción se cayó tres veces anoche', 'guardia en canonicalTitle devuelve d.raw sin crear monstruo')

  // 5. Regla de descripción: mejor vacía que clonada
  ok(esDescClonada('Xfce vs LXQt', 'Xfce vs LXQt', 'raw'), 'desc idéntica al sujeto es clonada')
  ok(
    esDescClonada('Compare Xfce vs LXQt on Fedora', 'Xfce vs LXQt', 'Compare Xfce vs LXQt on Fedora', 'Fedora', 'Compare'),
    'desc que repite raw/ejes es clonada'
  )
  ok(
    !esDescClonada('Consumo de RAM y respuesta', 'Xfce vs LXQt', 'raw', 'Fedora', 'Compare'),
    'desc con información amplificadora real se conserva'
  )

  // 6. Validación de sujeto inválido
  ok(esSujetoInvalido('Compare Xfce vs LXQt on Fedora'), 'sujeto con verbo y 6 palabras es inválido')
  ok(esSujetoInvalido('975 [Compare Xfce vs LXQt on Fedora] 001'), 'sujeto entre corchetes con verbo es inválido')
  ok(!esSujetoInvalido('Xfce vs LXQt'), 'sujeto nominal de 3 palabras es válido')

  // 7. Capacidad de reprocesar en Process (esPendiente)
  ok(
    esPendiente({
      raw: '975 [Compare Xfce vs LXQt on Fedora] 001 Compare Xfce vs LXQt on Fedora',
      canonTitle: '975 [Xfce vs LXQt] 001 [Fedora] · Compare',
    }),
    'esPendiente incluye la sesión #975 con título canónico malformado para poder corregirla'
  )
  ok(
    !esPendiente({
      raw: '975 [Xfce vs LXQt] 001 [Fedora] · Compare',
      canonTitle: '975 [Xfce vs LXQt] 001 [Fedora] · Compare',
    }),
    'esPendiente excluye sesión #975 una vez corregida'
  )
  ok(
    esPendiente({ raw: 'Compare Xfce vs LXQt on Fedora' }),
    'esPendiente incluye sesión virgen'
  )
  ok(
    !esPendiente({ raw: 'Subagent: Traducir al inglés' }),
    'esPendiente excluye maquinaria'
  )
} else ok(false, 'derivarCampos, canonicalTitle, esSujetoInvalido, esDescClonada y esPendiente se exportan')
} finally {
  try {
    unlinkSync(tmp)
  } catch (_) {}
  if (fallbackDir) {
    try {
      rmSync(fallbackDir, { recursive: true, force: true })
    } catch (_) {}
  }
}

console.log(failures ? `\n${failures} fallo(s)` : '\nTODO OK')
process.exit(failures ? 1 : 0)
