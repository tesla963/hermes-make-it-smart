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
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { dirname, join, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..')
const pluginPath = join(root, 'desktop', 'plugin.js')

const HERMES = join(process.env.HOME, '.hermes', 'hermes-agent', 'node_modules')
const asUrl = (p) => pathToFileURL(p).href

// Rewrite the three specifiers to files node can actually resolve here.
const src = readFileSync(pluginPath, 'utf8')
  .replace(/from '@hermes\/plugin-sdk'/g, `from '${asUrl(join(here, 'mocks', 'plugin-sdk.js'))}'`)
  .replace(/from 'react\/jsx-runtime'/g, `from '${asUrl(join(HERMES, 'react', 'jsx-runtime.js'))}'`)
  .replace(/from 'react'/g, `from '${asUrl(join(HERMES, 'react', 'index.js'))}'`)

const tmp = join(root, '.plugin-under-test.mjs')
writeFileSync(tmp, src)

let failures = 0
const ok = (cond, msg) => {
  console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${msg}`)
  if (!cond) failures++
}

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
ok(seen.length === 2, `declares 2 entries (got ${seen.length})`)
ok(seen.some((x) => x.render), 'one entry renders a component')
ok(seen.some((x) => x.data && x.data.path), 'one entry carries a route path')

console.log('\n§ primer render')
const { renderToStaticMarkup } = await import(asUrl(join(HERMES, 'react-dom', 'server.js')))
const { createElement } = await import(asUrl(join(HERMES, 'react', 'index.js')))
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

console.log('\n§ funciones puras')
const { numSel, fmtC, fmtH, fmtN } = mod
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
if (typeof fmtN === 'function') {
  ok(fmtN(15514624) === '15.5M', 'fmtN scales to millions')
  ok(fmtN(1500) === '1.5k', 'fmtN scales to thousands')
}

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

console.log(failures ? `\n${failures} fallo(s)` : '\nTODO OK')
process.exit(failures ? 1 : 0)
