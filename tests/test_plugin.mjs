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
const { tieneNumero, esMaquinaria, loadCatalogue } = mod
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
    { id: 'canon-1', n: 1, raw: '001 [Lisa] 001 Test', mc: 10, claves: ['test'] },
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
const { derivarCampos, canonicalTitle, esSujetoInvalido, esDescClonada, esPendiente } = mod
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

  // 2. Frases verbales típicas
  const dBrave = derivarCampos('Recuperar ventas y pestañas perdidas en Brave')
  ok(dBrave && dBrave.sujeto === 'Ventas y Pestañas', 'deriva sujeto nominal (Ventas y Pestañas)')
  ok(dBrave && dBrave.context === 'Brave', 'deriva contexto Brave')
  ok(dBrave && dBrave.verb === 'Recuperar', 'deriva verbo Recuperar')

  const dAnti = derivarCampos('Instalar y configurar Antigravity')
  ok(dAnti && dAnti.sujeto === 'Antigravity', 'deriva sujeto Antigravity')
  ok(dAnti && dAnti.verb === 'Instalar', 'deriva verbo Instalar para verbo compuesto')

  // 3. Guardia: si después de quitar el verbo no queda un sintagma nominal de 1-3 palabras, null
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
  ok(tBrave === '050 [Ventas y Pestañas] 001 [Brave] · Recuperar', `frase Brave genera: ${tBrave}`)

  // Caso Antigravity
  const tAnti = canonicalTitle({ n: 10, mmm: 1, raw: 'Instalar y configurar Antigravity' })
  ok(tAnti === '010 [Antigravity] 001 · Instalar', `caso Antigravity genera: ${tAnti}`)

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

console.log(failures ? `\n${failures} fallo(s)` : '\nTODO OK')
process.exit(failures ? 1 : 0)
