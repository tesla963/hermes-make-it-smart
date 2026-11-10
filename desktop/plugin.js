/**
 * Hermes, make all my work Smart! — desktop plugin
 *
 * A full page that turns the session archive into a browsable catalogue:
 * facets on the left, sessions in the middle, the detail card on the right.
 *
 * Data comes from `plugin-data/<id>/index.json`, built by tools/build_index.py.
 * The plugin never reads state.db itself: the Python indexer did the work
 * (classification, subjects, counters, costs) and this window only paints.
 * That is the modular seam — another host can reuse the indexer, another
 * window can reuse this index.
 *
 * The file is loaded UNCOMPILED, so: no JSX syntax, and the only importable
 * specifiers are @hermes/plugin-sdk, react and react/jsx-runtime. `jsx` carries
 * its children inside props, so everything below goes through the tiny `h()`.
 *
 * Layout contract (docs/SPEC-UI.md):
 *   - the row is two lines: the name, then the data with the tag pills
 *   - the ordinal sits OUTSIDE the subject bracket
 *   - the version badge lives in the gutter under the filters, never in the KPIs
 *   - no visible text is hard-coded: everything passes through the dictionary
 */

import { host, ROUTES_AREA, SIDEBAR_NAV_AREA } from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'
import { useState, useEffect, useMemo } from 'react'

const ID = 'make-all-my-work-smart'
const NAME = 'Hermes, make all my work Smart!'
const VERSION = '0.23.0'
const ROUTE = '/smart'

/* ------------------------------------------------------------------ */
/* The nine tags. Two reach the name; the other seven are filters,    */
/* declared now so that growing the classifier costs no migration.    */
/* ------------------------------------------------------------------ */
const TAGS = [
  { key: 'tag1', color: '#f0d48a', label: { es: 'plataforma', en: 'platform' } },
  { key: 'tag2', color: '#d3e3f3', label: { es: 'familia', en: 'family' } },
  { key: 'tag3', color: '#c9a8f0', label: { es: 'pilar', en: 'pillar' } },
  { key: 'tag4', color: '#96e0b0', label: { es: 'país', en: 'country' } },
  { key: 'tag5', color: '#f2a8c4', label: { es: 'año', en: 'year' } },
  { key: 'tag6', color: '#f5b98f', label: { es: 'máquina', en: 'machine' } },
  { key: 'tag7', color: '#8fe6e0', label: { es: 'libre', en: 'free' } },
  { key: 'tag8', color: '#b8b8f5', label: { es: 'libre', en: 'free' } },
  { key: 'tag9', color: '#d8ec8f', label: { es: 'libre', en: 'free' } },
]

const C = {
  sujeto: '#8fd0f5',
  t1: '#f0d48a',
  t2: '#d3e3f3',
  n: '#c9a8f0',
}

/** jsx-runtime wants `children` inside props — this keeps call sites readable. */
function h(type, props, ...kids) {
  const p = { ...(props || {}) }
  if (kids.length === 1) return jsx(type, { ...p, children: kids[0] })
  if (kids.length > 1) return jsxs(type, { ...p, children: kids })
  return jsx(type, p)
}

const CSS = `
.mmws{display:grid;grid-template-columns:212px minmax(0,1fr) 330px;height:100%;
font:13px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text",Inter,sans-serif;color:#e8dde4;background:#0d0b0e}
.mmws *{box-sizing:border-box}

/* ---- filters ---- */
.mmws aside{border-right:1px solid #2a2330;display:flex;flex-direction:column;min-height:0}
.mmws .fscroll{overflow:auto;padding:10px;flex:1 1 auto;scrollbar-width:none}
.mmws .fscroll::-webkit-scrollbar{width:0}
.mmws aside h1{font-size:12.5px;margin:0 0 3px;font-weight:800;line-height:1.25;letter-spacing:-.1px}
.mmws aside .fmt{font-size:9px;color:#6f6579;font-family:ui-monospace,Menlo,monospace;
margin:0 0 9px;line-height:1.4;word-break:break-word}
.mmws input{width:100%;padding:5px 8px;border-radius:6px;border:1px solid #3a3040;
background:#17131a;color:inherit;font-size:12px;margin-bottom:4px}
.mmws input::placeholder{color:#6f6579}
.mmws .grp{margin:11px 0 0}
.mmws .grp h4{font-size:9.5px;text-transform:uppercase;letter-spacing:.07em;color:#8b8095;
margin:0 0 4px;display:flex;justify-content:space-between;align-items:baseline;font-weight:600}
.mmws .grp h4 em{font-style:normal;font-size:8.5px;color:#5f5568;letter-spacing:0;text-transform:none}
.mmws .opt{display:flex;justify-content:space-between;gap:8px;padding:2px 6px;border-radius:5px;
cursor:pointer;font-size:11.5px;line-height:1.5}
.mmws .opt:hover{background:#1d1822}
.mmws .opt.on{background:#2a1a24;color:#f4e6ee}
.mmws .opt span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mmws .opt i{font-style:normal;color:#6f6579;font-variant-numeric:tabular-nums;flex:0 0 auto;font-size:10.5px}

/* ---- the version badge: a gutter of its own, aligned with the KPIs ---- */
.mmws .vbadge{flex:0 0 auto;height:30px;display:flex;align-items:center;gap:6px;padding:0 10px;
border-top:1px solid #3a3040;background:#0f0c13;cursor:pointer;user-select:none}
.mmws .vbadge:hover{background:#171320}
.mmws .vbadge i{width:5px;height:5px;border-radius:50%;background:#8fd0f5;
box-shadow:0 0 6px #8fd0f5aa;font-style:normal;flex:0 0 auto}
.mmws .vbadge b{font:600 9.5px/1 ui-monospace,Menlo,monospace;letter-spacing:.11em;color:#c9a8f0}
.mmws .vbadge u{text-decoration:none;font:700 9.5px/1 ui-monospace,Menlo,monospace;color:#eee6f3}

/* ---- toolbar ---- */
.mmws main{overflow:auto;min-width:0;display:flex;flex-direction:column}
.mmws .bar{display:flex;gap:5px;align-items:center;padding:7px 9px;border-bottom:1px solid #2a2330;
position:sticky;top:0;background:#100d12;z-index:3;flex-wrap:wrap}
.mmws .bar .sep{width:1px;height:14px;background:#2a2330;margin:0 2px}
.mmws button{padding:2px 7px;font-size:11px;border-radius:5px;border:1px solid #3a3040;
background:#1d1822;color:#cfc4d4;cursor:pointer;white-space:nowrap;font-family:inherit}
.mmws button:hover{background:#241d2b;color:#e8dde4}
.mmws button.on{background:#3a2050;border-color:#6b4a9e;color:#e8dde4}
.mmws .note{font-size:10.5px;color:#96e0b0;margin-left:auto;white-space:nowrap}

/* ---- the two-line row ---- */
.mmws table{width:100%;border-collapse:collapse;table-layout:fixed}
.mmws col.c-n{width:42px}.mmws col.c-f{width:78px}.mmws col.c-s{width:150px}
.mmws col.c-c{width:52px}.mmws col.c-h{width:52px}.mmws col.c-t{width:62px}.mmws col.c-p{width:44px}
.mmws th{font-size:9px;text-transform:uppercase;letter-spacing:.07em;color:#8b8095;
text-align:left;padding:6px 6px 5px;position:sticky;top:37px;background:#100d12;z-index:2;
border-bottom:1px solid #2a2330;font-weight:600}
.mmws th.num{text-align:right}
.mmws tr.t td{padding:8px 6px 0;border-top:1px solid #1c1721}
.mmws tr.t td:first-child{padding-left:8px}
.mmws tr.t .tn{font:700 10.5px/1 ui-monospace,Menlo,monospace;color:#f4e6ee;
vertical-align:top;padding-top:10px}
.mmws tr.t .name{font:700 10.5px/1.45 ui-monospace,Menlo,monospace;color:#e8dde4;
overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mmws tr.t .name .desc{font-weight:700;color:#f4e6ee}
.mmws tr.r{cursor:pointer}
.mmws tr.r td{padding:1px 6px 7px;color:#a89bb3;font-size:10.5px;
border-bottom:1px solid #2a2330;font-variant-numeric:tabular-nums;
overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mmws tr.r td:first-child{padding-left:8px}
.mmws tr.r .fecha{text-align:left;color:#8b8095}
.mmws tr.r .num{text-align:right}
.mmws tr.r:hover td{background:#151119}
.mmws tr.r.sel td{background:#241521}
.mmws .subj{color:${C.sujeto};font-weight:600}
.mmws .ord{color:${C.n};font-weight:700;margin-left:3px}
.mmws .pill{display:inline-block;padding:0 5px;border-radius:20px;font-size:9.5px;
margin-left:4px;border:1px solid;line-height:1.5}
.mmws .empty{padding:36px;text-align:center;color:#8b8095;font-size:12px}

/* ---- KPIs ---- */
.mmws .kbar{position:sticky;bottom:0;display:flex;align-items:flex-end;gap:0;
padding:5px 10px 6px;background:#0f0c13;border-top:1px solid #3a3040;
font-size:10px;margin-top:auto}
.mmws .k{flex:1 1 0;display:flex;align-items:flex-end;gap:6px;padding:0 8px;position:relative}
.mmws .k:first-child{padding-left:0}
.mmws .k+.k::before{content:"";position:absolute;left:0;top:6px;bottom:6px;width:1px;
background:linear-gradient(#4a3d5e00,#4a3d5e,#4a3d5e00)}
.mmws .k b{font-size:16px;font-variant-numeric:tabular-nums;line-height:1;font-weight:700}
.mmws .k em{font-style:normal;font-size:8px;text-transform:uppercase;letter-spacing:.06em;
color:#8b8095;line-height:1.25;display:block}

/* ---- record ---- */
.mmws .panel{border-left:1px solid #2a2330;overflow:auto;padding:12px;min-width:0}
.mmws .panel h2{font-size:16px;margin:0 0 4px;line-height:1.3;font-weight:800;color:#f4e6ee}
.mmws .panel .sub2{font-size:10px;color:#6f6579;font-family:ui-monospace,Menlo,monospace;
margin:0 0 12px;word-break:break-word;line-height:1.5}
.mmws .kv{display:grid;grid-template-columns:auto 1fr;gap:3px 10px;font-size:11.5px;margin-bottom:12px}
.mmws .kv div:nth-child(odd){color:#8b8095}
.mmws .kv div:nth-child(even){color:#dcd2e2;overflow:hidden;text-overflow:ellipsis}
.mmws .panel h4{font-size:9px;text-transform:uppercase;letter-spacing:.07em;color:#8b8095;
margin:12px 0 5px;font-weight:600}
.mmws .key{margin:5px 0;padding-left:8px;border-left:2px solid #3a3040;color:#b9aec4;
font-size:11px;line-height:1.45}
.mmws .acts{display:flex;gap:5px;margin-top:12px}
.mmws .acts button{flex:0 0 auto}

/* ---- the plugin card ---- */
.mmws .veil{position:fixed;inset:0;background:#0a080dcc;display:flex;align-items:center;
justify-content:center;z-index:99;padding:24px}
.mmws .card{background:#141117;border:1px solid #3a3040;border-radius:12px;
max-width:520px;width:100%;padding:20px;max-height:82vh;overflow:auto;
box-shadow:0 24px 60px #000000aa}
.mmws .card .hd{display:flex;align-items:baseline;gap:9px;margin-bottom:10px;flex-wrap:wrap}
.mmws .card .hd h3{font-size:13px;margin:0;color:#f4e6ee}
.mmws .card .hd span{font:11px ui-monospace,Menlo,monospace;color:#c9a8f0}
.mmws .card p{font-size:11.5px;color:#b9aec4;margin:0 0 12px;line-height:1.55}
.mmws .card .sect{font:9.5px ui-monospace,Menlo,monospace;letter-spacing:.1em;
color:#6f6579;margin:12px 0 5px}
.mmws .card ul{font-size:11px;line-height:1.65;margin:0;padding-left:16px;color:#b9aec4}
.mmws .card li{margin:2px 0}
.mmws .card code{font-family:ui-monospace,Menlo,monospace;font-size:10.5px;color:#8fd0f5}
.mmws .card .ft{display:flex;justify-content:flex-end;margin-top:16px}
.mmws .card .ft button{background:#2a1a3d;border-color:#6b4a9e;color:#e8dde4}
`

/* ------------------------------------------------------------------ */
/* Language. The dictionary is the only source of visible text — the  */
/* switch must never find a string it cannot translate.               */
/* ------------------------------------------------------------------ */
const I18N = {
  es: {
    buscar: 'Buscar · 126,305 · 50-75',
    pilar: 'Pilar', t1: 'Tag 1 · Plataforma', t2: 'Tag 2 · Familia',
    motor: 'Motor de IA', maquina: 'Tag 6 · Máquina', autor: 'Autor',
    frente: 'frente de trabajo',
    limpiar: 'Limpiar', copiar: 'Copiar', exportar: 'Exportar',
    actualizar: 'Actualizar BD', showDel: 'Mostrar Borradas', hideDel: 'Ocultar Borradas',
    showCron: 'Mostrar Cron', hideCron: 'Ocultar Cron',
    ordenar: 'Ordenar:', byN: 'Nº', byCosto: 'Costo', byHoras: 'Horas', byFecha: 'Fecha',
    colN: 'Nº', colFecha: 'Fecha', colSujeto: 'Sujeto', colCosto: 'Costo',
    colHoras: 'Horas', colTokens: 'Tokens', colPosts: 'Posts',
    ver: 'ver', de: 'de',
    kSes1: 'sesiones', kSes2: 'visibles', kCos: 'costo', kHor: 'horas',
    kPost: 'posts', kTok: 'tokens',
    ficha: 'Elige una sesión para ver su ficha.',
    sujeto: 'Sujeto', tag1: 'Tag 1', tag2: 'Tag 2', tag3: 'Pilar', tag4: 'País',
    tag5: 'Año', tag6: 'Máquina', tag7: 'Tag 7', tag8: 'Tag 8', tag9: 'Tag 9',
    fecha: 'Fecha', costo: 'Costo', tokens: 'Tokens', motorL: 'Motor', perfil: 'Perfil',
    autores: 'Autor', msgs: 'Mensajes', claves: 'MENSAJES CLAVE DEL USUARIO',
    sinClaves: '(sin mensajes de usuario útiles en esta sesión)',
    copiarSesion: 'Copiar sesión', abrirSesion: 'Abrir sesión',
    copiadoTit: 'títulos copiados', copiadoFicha: 'ficha copiada', sinPermiso: 'sin permiso',
    exportado: 'exportado a', noEscribi: 'no pude escribir', cargando: 'Cargando índice…',
    faltaIdx: 'falta index.json — corre tools/build_index.py',
    noIdx: 'No pude leer el índice: ',
    cIntro: 'Catálogo navegable de tus sesiones: las indexa de las bases, les pone nombre canónico y las deja filtrar por plataforma, familia y pilar. Esta ventana solo pinta — el clasificador es Python puro y no sabe que existe Hermes.',
    cVer: 'ESTA VERSIÓN', cReg: 'REGLAS QUE APRENDIÓ', cerrar: 'Cerrar',
    c1: 'Cuatro filtros en el panel; el sujeto se busca, no se filtra',
    c2: 'Nueve tags declarados; tag1 y tag2 en el nombre, el resto filtros',
    c3: 'El ordinal <code>MMM</code> va fuera del corchete del sujeto',
    c4: 'Sin fecha en el título: la fecha es columna y filtro',
    c5: 'Buscador numérico: <code>126,305</code> y <code>50-75</code>',
    c6: 'Copiar títulos con su id, copiar la ficha, exportar CSV',
    c7: 'Mostrar u ocultar borradas y sesiones de cron',
    c8: 'Switch ES/EN — no cambia lo que el clasificador entiende',
    c9: 'Una serie se unifica: 50 sesiones, no 24 chips por dominio',
    r1: 'Un calificador estrecha, no nombra: el dominio va a la descripción',
    r2: 'La marca y el producto son dos cosas: USPS + Ground Advantage',
    r3: 'El sujeto es el paciente, no quien sostiene la ficha',
    r4: 'Una serie, un pilar: si hay 40 hermanos, el que no encaja está mal',
  },
  en: {
    buscar: 'Search · 126,305 · 50-75',
    pilar: 'Pillar', t1: 'Tag 1 · Platform', t2: 'Tag 2 · Family',
    motor: 'AI engine', maquina: 'Tag 6 · Machine', autor: 'Author',
    frente: 'workstream',
    limpiar: 'Clear', copiar: 'Copy', exportar: 'Export',
    actualizar: 'Refresh DB', showDel: 'Show Deleted', hideDel: 'Hide Deleted',
    showCron: 'Show Cron', hideCron: 'Hide Cron',
    ordenar: 'Sort:', byN: 'No.', byCosto: 'Cost', byHoras: 'Hours', byFecha: 'Date',
    colN: 'No.', colFecha: 'Date', colSujeto: 'Subject', colCosto: 'Cost',
    colHoras: 'Hours', colTokens: 'Tokens', colPosts: 'Posts',
    ver: 'of', de: 'of',
    kSes1: 'sessions', kSes2: 'visible', kCos: 'cost', kHor: 'hours',
    kPost: 'posts', kTok: 'tokens',
    ficha: 'Pick a session to see its record.',
    sujeto: 'Subject', tag1: 'Tag 1', tag2: 'Tag 2', tag3: 'Pillar', tag4: 'Country',
    tag5: 'Year', tag6: 'Machine', tag7: 'Tag 7', tag8: 'Tag 8', tag9: 'Tag 9',
    fecha: 'Date', costo: 'Cost', tokens: 'Tokens', motorL: 'Engine', perfil: 'Profile',
    autores: 'Author', msgs: 'Messages', claves: 'KEY USER MESSAGES',
    sinClaves: '(no useful user messages in this session)',
    copiarSesion: 'Copy session', abrirSesion: 'Open session',
    copiadoTit: 'titles copied', copiadoFicha: 'record copied', sinPermiso: 'no permission',
    exportado: 'exported to', noEscribi: 'could not write', cargando: 'Loading index…',
    faltaIdx: 'index.json is missing — run tools/build_index.py',
    noIdx: 'Could not read the index: ',
    cIntro: 'A browsable catalogue of your sessions: it indexes them from the databases, gives each a canonical name and lets you filter by platform, family and pillar. This window only paints — the classifier is pure Python and does not know Hermes exists.',
    cVer: 'THIS VERSION', cReg: 'RULES IT LEARNED', cerrar: 'Close',
    c1: 'Four filters in the panel; the subject is searched, not filtered',
    c2: 'Nine tags declared; tag1 and tag2 in the name, the rest are filters',
    c3: 'The <code>MMM</code> ordinal sits outside the subject bracket',
    c4: 'No date in the title: the date is a column and a filter',
    c5: 'Numeric search: <code>126,305</code> and <code>50-75</code>',
    c6: 'Copy titles with their id, copy the record, export CSV',
    c7: 'Show or hide deleted sessions and cron sessions',
    c8: 'ES/EN switch — it never changes what the classifier understands',
    c9: 'A series unifies: 50 sessions, not 24 chips per domain',
    r1: 'A qualifier narrows, it does not name: the domain goes in the description',
    r2: 'The brand and the product are two things: USPS + Ground Advantage',
    r3: 'The subject is the patient, not whoever holds the file',
    r4: 'One series, one pillar: with 40 siblings, the one that does not fit is wrong',
  },
}

const norm = (s) =>
  (s || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()

const fmtC = (v) =>
  (v || 0) >= 1 ? '$' + v.toFixed(2) : Math.round((v || 0) * 100) + '¢'
const fmtH = (m) =>
  (m || 0) >= 60
    ? Math.floor(m / 60) + 'h' + String(Math.round(m % 60)).padStart(2, '0')
    : Math.round(m || 0) + 'm'
const fmtN = (n) =>
  n >= 1e9
    ? (n / 1e9).toFixed(1) + 'B'
    : n >= 1e6
      ? (n / 1e6).toFixed(1) + 'M'
      : n >= 1e3
        ? (n / 1e3).toFixed(1) + 'k'
        : String(n || 0)

/** "126,305" or "50-75" selects by number; anything else is free text. */
function numSel(text) {
  const s = String(text || '').replace(/\s+/g, '')
  if (!s || !/^\d+(-\d+)?(,\d+(-\d+)?)*$/.test(s)) return null
  const out = new Set()
  for (const part of s.split(',')) {
    const m = part.match(/^(\d+)-(\d+)$/)
    if (m) {
      let a = +m[1]
      let b = +m[2]
      if (a > b) [a, b] = [b, a]
      for (let i = a; i <= b && out.size < 20000; i++) out.add(i)
    } else out.add(+part)
  }
  return out.size ? out : null
}

async function copyText(ctx, text) {
  try {
    if (ctx.os && ctx.os.writeClipboard && (await ctx.os.writeClipboard(text))) return true
  } catch (e) {
    /* fall through */
  }
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch (e) {
    return false
  }
}

/* ------------------------------------------------------------------ */

function App({ ctx }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [q, setQ] = useState('')
  const [f, setF] = useState({})
  const [sel, setSel] = useState(null)
  const [showCron, setShowCron] = useState(false)
  const [note, setNote] = useState('')
  const [card, setCard] = useState(false)
  const [lang, setLang] = useState(() => {
    try {
      return localStorage.getItem('mmws-lang') === 'en' ? 'en' : 'es'
    } catch (e) {
      return 'es'
    }
  })
  const [sort, setSort] = useState({ key: 'fecha', dir: -1 })

  const t = (k) => (I18N[lang] && I18N[lang][k]) || k

  const switchLang = (l) => {
    setLang(l)
    try {
      localStorage.setItem('mmws-lang', l)
    } catch (e) {
      /* private mode */
    }
  }

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const res = await ctx.files.readText('data', 'index.json')
        if (!alive) return
        if (!res || !res.ok || !res.text) throw new Error(t('faltaIdx'))
        setData(JSON.parse(res.text))
      } catch (e) {
        if (alive) setError(String((e && e.message) || e))
      }
    })()
    return () => {
      alive = false
    }
  }, [ctx])

  const sessions = data ? data.sessions : []
  const nums = useMemo(() => numSel(q), [q])

  const match = (s) => {
    if (!showCron && s.esCron) return false
    if (nums) {
      if (!nums.has(s.n)) return false
    } else if (q) {
      const hay = norm(s.raw + ' ' + s.id + ' ' + (s.desc || ''))
      if (!q.split(/\s+/).filter(Boolean).every((w) => hay.includes(norm(w)))) return false
    }
    for (const k of Object.keys(f)) if (f[k] && s[k] !== f[k]) return false
    return true
  }

  const visible = useMemo(() => sessions.filter(match), [sessions, q, f, showCron])

  const sorted = useMemo(() => {
    const out = visible.slice()
    const { key, dir } = sort
    out.sort((a, b) => {
      const va = a[key]
      const vb = b[key]
      if (typeof va === 'string' || typeof vb === 'string')
        return String(va || '').localeCompare(String(vb || '')) * dir
      return ((va || 0) - (vb || 0)) * dir
    })
    return out
  }, [visible, sort])

  const countBy = (key) => {
    const m = new Map()
    for (const s of sessions) {
      if (!showCron && s.esCron) continue
      if (s[key]) m.set(s[key], (m.get(s[key]) || 0) + 1)
    }
    return [...m.entries()].sort((a, b) => b[1] - a[1])
  }

  const totals = useMemo(
    () =>
      visible.reduce(
        (a, s) => ({
          costo: a.costo + (s.costo || 0),
          horas: a.horas + (s.horas || 0),
          tok: a.tok + (s.tok || 0),
          posts: a.posts + (s.posts || 0),
        }),
        { costo: 0, horas: 0, tok: 0, posts: 0 }
      ),
    [visible]
  )

  const flash = (msg) => {
    setNote(msg)
    setTimeout(() => setNote(''), 2600)
  }

  const copyTitles = async () => {
    const txt = sorted.map((s) => s.raw + '\t' + s.id).join('\n')
    flash((await copyText(ctx, txt)) ? '✔ ' + sorted.length + ' ' + t('copiadoTit') : '✗ ' + t('sinPermiso'))
  }

  const copyCard = async () => {
    if (!sel) return
    const s = sel
    const L = [
      s.raw,
      t('sujeto') + ': ' + s.sujeto,
      t('tag1') + ': ' + (s.tag1 || '—') + ' | ' + t('tag2') + ': ' + (s.tag2 || '—'),
      t('tag3') + ': ' + (s.pilar || '—') + ' | ' + t('tag6') + ': ' + (s.tag6 || '—'),
      t('sujeto') + ': ' + (s.desc || '—'),
      t('fecha') + ': ' + s.fecha + ' · ' + t('msgs') + ': ' + s.mc,
      t('costo') + ': ' + fmtC(s.costo) + ' · ' + fmtH(s.horas) + ' · ' + fmtN(s.tok) + ' ' + t('tokens'),
      t('motorL') + ': ' + (s.motor || '—') + ' · ' + t('perfil') + ': ' + s.prof,
    ]
    if (s.claves && s.claves.length) {
      L.push('--- ' + t('claves') + ' ---')
      s.claves.slice(0, 6).forEach((c) => L.push('> ' + c))
    }
    L.push('id: ' + s.id)
    flash((await copyText(ctx, L.join('\n'))) ? '✔ ' + t('copiadoFicha') : '✗ ' + t('sinPermiso'))
  }

  const exportCsv = async () => {
    const esc = (v) => '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"'
    const head = [
      'n', 'id', 'fecha', 'titulo_actual', 'sujeto', 'tag1', 'tag2', 'descripcion',
      'sujeto_nuevo', 'tag1_nuevo', 'tag2_nuevo', 'descripcion_nueva', 'observaciones',
    ]
    const rows = sorted.map((s) =>
      [s.n, s.id, s.fecha, s.raw, s.sujeto, s.tag1, s.tag2, s.desc, '', '', '', '', '']
        .map(esc)
        .join(',')
    )
    const res = await ctx.files.writeText(
      'data',
      'last-export.csv',
      '\ufeff' + head.join(',') + '\n' + rows.join('\n') + '\n'
    )
    flash(res && res.ok ? '✔ ' + t('exportado') + ' last-export.csv' : '✗ ' + t('noEscribi'))
  }

  const openSession = (s) => {
    try {
      host.openSession(s.id, { profile: s.prof, intent: 'tab' })
    } catch (e) {
      flash('✗ ' + ((e && e.message) || e))
    }
  }

  if (error)
    return h('div', { className: 'mmws' },
      h('style', null, CSS),
      h('div', { className: 'empty' }, t('noIdx') + error))
  if (!data)
    return h('div', { className: 'mmws' },
      h('style', null, CSS),
      h('div', { className: 'empty' }, t('cargando')))

  const opt = (key, value, n) =>
    h('div', {
      key: key + value,
      className: 'opt' + (f[key] === value ? ' on' : ''),
      onClick: () => setF((p) => ({ ...p, [key]: p[key] === value ? null : value })),
    }, h('span', null, value), h('i', null, n))

  const group = (title, key, hint) =>
    h('div', { className: 'grp', key },
      h('h4', null, h('span', null, title), hint ? h('em', null, hint) : null),
      countBy(key).map(([v, n]) => opt(key, v, n)))

  const kpi = (val, label, color) =>
    h('div', { className: 'k' }, h('b', { style: { color } }, val), h('em', null, label))

  const orderBtn = (key, label) =>
    h('button', {
      className: sort.key === key ? 'on' : '',
      onClick: () => setSort((p) => ({ key, dir: p.key === key ? -p.dir : -1 })),
    }, label)

  /* the two-line row */
  const rows = sorted.flatMap((s) => [
    h('tr', { className: 't', key: s.id + '-t' },
      h('td', { className: 'tn' }, String(s.n)),
      h('td', { className: 'name', colSpan: 6 },
        h('span', { style: { color: C.sujeto } }, '[' + s.sujeto + ']'),
        h('span', { className: 'ord' }, String(s.mmm || 0).padStart(3, '0')),
        s.tag1 ? h('span', { style: { color: C.t1 } }, ' [' + s.tag1 + ']') : null,
        s.tag2 ? h('span', { style: { color: C.t2 } }, ' [' + s.tag2 + ']') : null,
        s.desc ? h('span', { className: 'desc' }, ' ' + s.desc) : null)),
    h('tr', {
      className: 'r' + (sel && sel.id === s.id ? ' sel' : ''),
      key: s.id + '-r',
      onClick: () => setSel(s),
    },
      h('td', { className: 'fecha' }, s.fecha),
      h('td', null, s.sujeto),
      h('td', null,
        s.tag1 ? h('span', { className: 'pill', style: { color: C.t1, borderColor: C.t1 + '66' } }, s.tag1) : null,
        s.tag2 ? h('span', { className: 'pill', style: { color: C.t2, borderColor: C.t2 + '66' } }, s.tag2) : null),
      h('td', { className: 'num' }, fmtC(s.costo)),
      h('td', { className: 'num' }, fmtH(s.horas)),
      h('td', { className: 'num' }, fmtN(s.tok)),
      h('td', { className: 'num' }, s.posts))
  ])

  return h('div', { className: 'mmws' },
    h('style', null, CSS),

    /* ---------- filters ---------- */
    h('aside', null,
      h('div', { className: 'fscroll' },
        h('h1', null, NAME),
        h('p', { className: 'fmt' }, sessions.length + ' ' + t('kSes1') + ' · NNN [Sujeto] MMM [Tag1] [Tag2]'),
        h('input', {
          placeholder: t('buscar'),
          value: q,
          onChange: (e) => setQ(e.target.value),
        }),
        group(t('pilar'), 'pilar', String(countBy('pilar').length)),
        group(t('t1'), 'tag1'),
        group(t('t2'), 'tag2'),
        group(t('motor'), 'motor'),
        group(t('maquina'), 'tag6'),
        group(t('autor'), 'prof')),
      h('div', {
        className: 'vbadge',
        onClick: () => setCard(true),
        title: NAME,
      },
        h('i', null), h('b', null, 'V '), h('u', null, VERSION.split('.').slice(0, 2).join('.')))),

    /* ---------- sessions ---------- */
    h('main', null,
      h('div', { className: 'bar' },
        h('span', { style: { fontSize: '11px', color: '#8b8095' } },
          visible.length + ' ' + t('de') + ' ' + sessions.length),
        h('div', { className: 'sep' }),
        h('button', {
          onClick: () => {
            setF({})
            setQ('')
          },
        }, t('limpiar')),
        h('button', { onClick: copyTitles }, t('copiar') + ' · ' + visible.length),
        h('button', { onClick: exportCsv }, t('exportar') + ' · ' + visible.length),
        h('button', {
          className: showCron ? 'on' : '',
          onClick: () => setShowCron((v) => !v),
        }, (showCron ? t('hideCron') : t('showCron')) + ' · ' + sessions.filter((s) => s.esCron).length),
        h('div', { className: 'sep' }),
        h('span', { style: { fontSize: '10.5px', color: '#8b8095' } }, t('ordenar')),
        orderBtn('n', t('byN')),
        orderBtn('costo', t('byCosto')),
        orderBtn('horas', t('byHoras')),
        orderBtn('fecha', t('byFecha')),
        h('span', { className: 'note' }, note)),

      h('table', null,
        h('colgroup', null,
          h('col', { className: 'c-n' }), h('col', { className: 'c-f' }), h('col', { className: 'c-s' }),
          h('col', { className: 'c-c' }), h('col', { className: 'c-h' }), h('col', { className: 'c-t' }),
          h('col', { className: 'c-p' })),
        h('thead', null,
          h('tr', null,
            h('th', { className: 'num' }, t('colN')),
            h('th', null, t('colFecha')),
            h('th', null, t('colSujeto')),
            h('th', { className: 'num' }, t('colCosto')),
            h('th', { className: 'num' }, t('colHoras')),
            h('th', { className: 'num' }, t('colTokens')),
            h('th', { className: 'num' }, t('colPosts')))),
        h('tbody', null, rows)),

      h('div', { className: 'kbar' },
        kpi(visible.length, t('kSes1'), '#e88fb4'),
        kpi('$' + totals.costo.toFixed(2), t('kCos'), '#96e0b0'),
        kpi(Math.round(totals.horas / 60) + ' h', t('kHor'), '#f0d48a'),
        kpi(fmtN(totals.posts), t('kPost'), '#d3e3f3'),
        kpi(fmtN(totals.tok), t('kTok'), '#8fe6e0'))),

    /* ---------- record ---------- */
    h('div', { className: 'panel' },
      sel
        ? h('div', null,
            h('h2', null, sel.sujeto),
            h('p', { className: 'sub2' }, sel.raw),
            h('div', { className: 'kv' },
              h('div', null, t('tag1')), h('div', null, sel.tag1 || '—'),
              h('div', null, t('tag2')), h('div', null, sel.tag2 || '—'),
              h('div', null, t('tag3')), h('div', null, sel.pilar || '—'),
              h('div', null, t('tag6')), h('div', null, sel.tag6 || '—'),
              h('div', null, t('fecha')), h('div', null, sel.fecha),
              h('div', null, t('costo')), h('div', null, fmtC(sel.costo) + ' · ' + fmtH(sel.horas)),
              h('div', null, t('tokens')), h('div', null, fmtN(sel.tok) + ' · ' + sel.posts + ' ' + t('kPost')),
              h('div', null, t('motorL')), h('div', null, sel.motor || '—'),
              h('div', null, t('perfil')), h('div', null, sel.prof)),
            h('h4', null, t('claves')),
            (sel.claves || []).length
              ? (sel.claves || []).map((c, i) => h('div', { className: 'key', key: i }, c))
              : h('div', { className: 'key' }, t('sinClaves')),
            h('div', { className: 'acts' },
              h('button', { onClick: copyCard }, t('copiarSesion')),
              h('button', { onClick: () => openSession(sel) }, t('abrirSesion'))))
        : h('div', { className: 'empty' }, t('ficha'))),

    /* ---------- plugin card ---------- */
    card
      ? h('div', { className: 'veil', onClick: (e) => { if (e.target.className === 'veil') setCard(false) } },
          h('div', { className: 'card' },
            h('div', { className: 'hd' },
              h('h3', null, NAME),
              h('span', null, 'v' + VERSION.split('.').slice(0, 2).join('.'))),
            h('p', null, t('cIntro')),
            h('div', { className: 'sect' }, t('cVer')),
            h('ul', null, ['c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'c8', 'c9'].map((k) =>
              h('li', { key: k, dangerouslySetInnerHTML: { __html: t(k) } }))),
            h('div', { className: 'sect' }, t('cReg')),
            h('ul', null, ['r1', 'r2', 'r3', 'r4'].map((k) =>
              h('li', { key: k }, t(k)))),
            h('div', { className: 'ft' },
              h('button', { onClick: () => setCard(false) }, t('cerrar')),
              h('button', { onClick: () => switchLang(lang === 'es' ? 'en' : 'es') },
                lang === 'es' ? 'EN' : 'ES'))))
      : null)
}

// Named exports so the smoke test can exercise the pure helpers without React.
export { numSel, fmtC, fmtH, fmtN }

export default {
  id: ID,
  name: NAME,
  version: VERSION,

  register(ctx) {
    ctx.registerMany([
      { id: 'page', area: ROUTES_AREA, data: { path: ROUTE }, render: () => h(App, { ctx }) },
      {
        id: 'nav',
        area: SIDEBAR_NAV_AREA,
        data: { path: ROUTE, label: 'Make It Smart', codicon: 'archive' },
      },
    ])
  },
}
