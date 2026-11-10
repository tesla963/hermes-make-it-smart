/**
 * Hermes, Make All My Work Smart! — desktop plugin (v0.1)
 *
 * A full page that turns the session archive into a browsable catalog:
 * facets on the left, sessions in the middle, the detail card on the right.
 *
 * Data comes from `plugin-data/<id>/index.json`, built by tools/build_index.py.
 * The plugin never reads state.db itself: the Python indexer already did the
 * work (classification, subjects, counters, costs), and the window only paints.
 *
 * What it can do today:
 *   - filter by pillar, tag1, tag2 and free text (with synonyms)
 *   - select sessions by number: "126,305" or "50-75"
 *   - copy the visible titles, or one full card, to the clipboard
 *   - export the visible rows to CSV with a running [CCCC] counter
 *   - open a stored session in the app, in place or in a tab
 *
 * Everything here is read-only against the host. The one write — renaming —
 * goes through host.request('session.title'), never a raw database call.
 */

import { host, ROUTES_AREA, SIDEBAR_NAV_AREA } from '@hermes/plugin-sdk'
// The disk file is loaded uncompiled: jsx lives in react/jsx-runtime, and the
// only importable specifiers are @hermes/plugin-sdk, react and react/jsx-runtime.
import { jsx, jsxs } from 'react/jsx-runtime'
import { useState, useEffect, useMemo } from 'react'

const ID = 'make-all-my-work-smart'
const NAME = 'Hermes, make all my work Smart!'
const VERSION = '0.1.0'
const ROUTE = '/smart'

const CSS = `
.mmws{display:grid;grid-template-columns:220px 1fr 340px;height:100%;font-size:13px;color:#e8dde4;background:#0d0b0e}
.mmws aside{border-right:1px solid #2a2330;overflow:auto;padding:10px}
.mmws main{overflow:auto}
.mmws .panel{border-left:1px solid #2a2330;overflow:auto;padding:12px}
.mmws h1{font-size:15px;margin:0 0 8px}
.mmws input{width:100%;padding:6px 8px;border-radius:6px;border:1px solid #3a3040;background:#17131a;color:inherit}
.mmws .grp{margin:12px 0}
.mmws .grp h4{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:#8b8095;margin:0 0 5px}
.mmws .opt{display:flex;justify-content:space-between;padding:3px 6px;border-radius:5px;cursor:pointer}
.mmws .opt:hover{background:#1d1822}
.mmws .opt.on{background:#2a1a24;color:#f0dbe4}
.mmws .opt i{font-style:normal;color:#8b8095}
.mmws .bar{display:flex;gap:6px;align-items:center;padding:8px 10px;border-bottom:1px solid #2a2330;position:sticky;top:0;background:#100d12;z-index:2}
.mmws button{padding:3px 8px;font-size:12px;border-radius:6px;border:1px solid #3a3040;background:#1d1822;color:#cfc4d4;cursor:pointer}
.mmws button.on{background:#5a2040;border-color:#7a2a56;color:#fff}
.mmws table{width:100%;border-collapse:collapse}
.mmws th{font-size:9.5px;text-transform:uppercase;letter-spacing:.06em;color:#8b8095;text-align:left;padding:6px 8px;position:sticky;top:41px;background:#100d12}
.mmws td{padding:3px 8px;vertical-align:top}
.mmws tr.t td{padding-top:9px;font-family:ui-monospace,Menlo,monospace;font-size:11px;font-weight:700;color:#f4e6ee}
.mmws tr.t span.f{color:#f4e6ee}
.mmws tr.r{cursor:pointer}
.mmws tr.r td{border-bottom:2px solid #3d3346;color:#cfc4d4}
.mmws tr.r.sel{background:#251521}
.mmws .num{text-align:center;font-variant-numeric:tabular-nums}
.mmws .pill{display:inline-block;padding:1px 6px;border-radius:20px;background:#241d2b;font-size:10.5px;margin-right:4px}
.mmws .empty{padding:30px;text-align:center;color:#8b8095}
.mmws .kbar{position:sticky;bottom:0;display:flex;gap:14px;padding:6px 10px;background:#100d12;border-top:1px solid #2a2330;font-size:11px}
.mmws .kbar b{font-size:15px;margin-right:4px}
.mmws .kbar i{font-style:normal;font-size:8px;text-transform:uppercase;color:#8b8095}
.mmws .card h2{font-size:13px;margin:0 0 8px;font-family:ui-monospace,Menlo,monospace;line-height:1.4}
.mmws .kv{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;font-size:11.5px}
.mmws .kv div:nth-child(odd){color:#8b8095}
.mmws .key{margin:6px 0;padding-left:8px;border-left:2px solid #3a3040;color:#cfc4d4;font-size:11.5px}
`

const norm = (s) =>
  (s || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()

const fmtC = (v) => (v >= 1 ? '$' + v.toFixed(2) : Math.round(v * 100) + '¢')
const fmtH = (m) => (m >= 60 ? Math.floor(m / 60) + 'h' + String(Math.round(m % 60)).padStart(2, '0') : Math.round(m) + 'm')
const fmtN = (n) =>
  n >= 1e9 ? (n / 1e9).toFixed(1) + 'B' : n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? (n / 1e3).toFixed(1) + 'k' : String(n || 0)

/** "126,305" or "50-75" selects by number; anything else is text. */
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
    const ok = await ctx.os.writeClipboard(text)
    if (ok) return true
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

function App({ ctx }) {

  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [q, setQ] = useState('')
  const [f, setF] = useState({ pilar: null, tag1: null, tag2: null })
  const [sel, setSel] = useState(null)
  const [showCron, setShowCron] = useState(false)
  const [note, setNote] = useState('')

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const res = await ctx.files.readText('data', 'index.json')
        if (!alive) return
        if (!res || !res.ok || !res.text) throw new Error('no index.json — run tools/build_index.py first')
        setData(JSON.parse(res.text))
      } catch (e) {
        if (alive) setError(String(e && e.message ? e.message : e))
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
      const hay = norm(s.raw + ' ' + s.id)
      if (!q.split(/\s+/).filter(Boolean).every((w) => hay.includes(norm(w)))) return false
    }
    if (f.pilar && s.pilar !== f.pilar) return false
    if (f.tag1 && s.tag1 !== f.tag1) return false
    if (f.tag2 && s.tag2 !== f.tag2) return false
    return true
  }

  const visible = useMemo(() => sessions.filter(match), [sessions, q, f, showCron])

  const countBy = (key) => {
    const m = new Map()
    for (const s of visible) if (s[key]) m.set(s[key], (m.get(s[key]) || 0) + 1)
    return [...m.entries()].sort((a, b) => b[1] - a[1])
  }

  const totals = useMemo(
    () =>
      visible.reduce(
        (a, s) => ({ costo: a.costo + (s.costo || 0), horas: a.horas + (s.horas || 0), tok: a.tok + (s.tok || 0), posts: a.posts + (s.posts || 0) }),
        { costo: 0, horas: 0, tok: 0, posts: 0 }
      ),
    [visible]
  )

  if (error)
    return jsx('div', { className: 'mmws' }, jsx('div', { className: 'empty' }, 'No pude leer el índice: ' + error))
  if (!data) return jsx('div', { className: 'mmws' }, jsx('div', { className: 'empty' }, 'Cargando índice…'))

  const optRow = (key, value, n) =>
    jsx(
      'div',
      {
        key: key + value,
        className: 'opt' + (f[key] === value ? ' on' : ''),
        onClick: () => setF((p) => ({ ...p, [key]: p[key] === value ? null : value })),
      },
      jsx('span', null, value),
      jsx('i', null, n)
    )

  const group = (title, key) =>
    jsx(
      'div',
      { className: 'grp' },
      jsx('h4', null, title),
      countBy(key).slice(0, 40).map(([v, n]) => optRow(key, v, n))
    )

  const copyTitles = async () => {
    const txt = visible
      .slice()
      .sort((a, b) => a.n - b.n)
      .map((s) => s.raw + '\t' + s.id)
      .join('\n')
    setNote((await copyText(ctx, txt)) ? '✔ ' + visible.length + ' títulos copiados' : '✗ sin permiso')
    setTimeout(() => setNote(''), 2500)
  }

  const copyCard = async () => {
    if (!sel) return
    const s = sel
    const L = [
      s.raw,
      'sujeto: ' + s.sujeto + ' · ordinal ' + String(s.mmm).padStart(3, '0'),
      'tag1: ' + (s.tag1 || '—') + ' | tag2: ' + (s.tag2 || '—'),
      'pilar: ' + (s.pilar || '—') + ' | máquina: ' + (s.tag6 || '—'),
      'descripción: ' + (s.desc || '—'),
      'fecha: ' + s.fecha + ' · mensajes: ' + s.mc + ' · posts: ' + s.posts,
      'costo: ' + fmtC(s.costo) + ' · horas: ' + fmtH(s.horas) + ' · tokens: ' + fmtN(s.tok),
      'motor: ' + (s.motor || '—') + ' · perfil: ' + s.prof,
    ]
    if (s.claves && s.claves.length) {
      L.push('--- mensajes clave del usuario ---')
      s.claves.slice(0, 6).forEach((c) => L.push('> ' + c))
    }
    L.push('id: ' + s.id)
    setNote((await copyText(ctx, L.join('\n'))) ? '✔ ficha copiada' : '✗ sin permiso')
    setTimeout(() => setNote(''), 2500)
  }

  const exportCsv = async () => {
    const esc = (v) => '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"'
    const head = ['n', 'id', 'fecha', 'titulo_actual', 'sujeto', 'tag1', 'tag2', 'descripcion', 'sujeto_nuevo', 'tag1_nuevo', 'tag2_nuevo', 'descripcion_nueva', 'observaciones']
    const rows = visible
      .slice()
      .sort((a, b) => a.n - b.n)
      .map((s) => [s.n, s.id, s.fecha, s.raw, s.sujeto, s.tag1, s.tag2, s.desc, '', '', '', '', ''].map(esc).join(','))
    const ok = await ctx.files.writeText('data', 'last-export.csv', '\ufeff' + head.join(',') + '\n' + rows.join('\n') + '\n')
    setNote(ok ? '✔ exportado a plugin-data/data/last-export.csv' : '✗ no pude escribir')
    setTimeout(() => setNote(''), 3000)
  }

  const openSession = (s) => {
    try {
      host.openSession(s.id, { profile: s.prof, intent: 'tab' })
    } catch (e) {
      setNote('✗ ' + (e.message || e))
    }
  }

  return jsx(
    'div',
    { className: 'mmws' },
    jsx('style', null, CSS),
    jsx(
      'aside',
      null,
      jsx('h1', null, NAME),
      jsx('input', { placeholder: 'Buscar o 126,305 · 50-75', value: q, onChange: (e) => setQ(e.target.value) }),
      jsx('div', { className: 'grp' }, jsx('h4', null, 'Pilar'), countBy('pilar').map(([v, n]) => optRow('pilar', v, n))),
      group('Tag 1 · plataforma', 'tag1'),
      group('Tag 2 · familia', 'tag2')
    ),
    jsx(
      'main',
      null,
      jsx(
        'div',
        { className: 'bar' },
        jsx('strong', null, visible.length + ' de ' + sessions.length),
        jsx('button', { onClick: () => { setF({ pilar: null, tag1: null, tag2: null }); setQ('') } }, 'Limpiar'),
        jsx('button', { onClick: copyTitles }, 'Copiar · ' + visible.length),
        jsx('button', { onClick: exportCsv }, 'Exportar · ' + visible.length),
        jsx('button', { className: showCron ? 'on' : '', onClick: () => setShowCron((v) => !v) }, (showCron ? 'Hide' : 'Show') + ' Cron · ' + sessions.filter((s) => s.esCron).length),
        jsx('span', { style: { marginLeft: 'auto', color: '#8b8095', fontSize: '11px' } }, note)
      ),
      jsx(
        'table',
        null,
        jsx('thead', null, jsx('tr', null, ['Nº', 'Fecha', 'Sesión', 'Tags', 'Costo', 'Horas', 'Tokens', 'Posts'].map((h) => jsx('th', { key: h }, h)))),
        jsx(
          'tbody',
          null,
          visible.flatMap((s) => [
            jsx(
              'tr',
              { className: 't', key: s.id + '-t' },
                jsx('td', { className: 'num' }, s.n),
                jsx(
                  'td',
                  { colSpan: 7 },
                  jsx('span', { className: 'f' }, '[' + s.sujeto + '] ' + String(s.mmm).padStart(3, '0') + (s.tag1 ? ' [' + s.tag1 + ']' : '') + (s.tag2 ? ' [' + s.tag2 + ']' : '')),
                  ' ',
                  jsx('span', { className: 'd' }, s.desc)
                )
              ),
              jsx(
                'tr',
                { className: 'r' + (sel && sel.id === s.id ? ' sel' : ''), key: s.id + '-r', onClick: () => setSel(s) },
                jsx('td', { className: 'num' }, ''),
                jsx('td', null, s.fecha),
                jsx('td', null, s.sujeto),
                jsx('td', null, jsx('span', { className: 'pill' }, s.tag1 || '—'), jsx('span', { className: 'pill' }, s.tag2 || '—')),
                jsx('td', { className: 'num' }, fmtC(s.costo)),
                jsx('td', { className: 'num' }, fmtH(s.horas)),
                jsx('td', { className: 'num' }, fmtN(s.tok)),
                jsx('td', { className: 'num' }, s.posts)
              )
            ),
          ])
        )
      ),
      jsx(
        'div',
        { className: 'kbar' },
        jsx('span', null, jsx('b', null, visible.length), jsx('i', null, 'sesiones')),
        jsx('span', null, jsx('b', null, '$' + totals.costo.toFixed(2)), jsx('i', null, 'costo')),
        jsx('span', null, jsx('b', null, Math.round(totals.horas / 60) + ' h'), jsx('i', null, 'horas')),
        jsx('span', null, jsx('b', null, fmtN(totals.posts)), jsx('i', null, 'posts')),
        jsx('span', null, jsx('b', null, fmtN(totals.tok)), jsx('i', null, 'tokens'))
      )
    ),
    jsx(
      'div',
      { className: 'panel card' },
      sel
        ? jsx(
            React.Fragment,
            null,
            jsx('h2', null, sel.raw),
            jsx(
              'div',
              { className: 'kv' },
              jsx('div', null, 'Sujeto'),
              jsx('div', null, sel.sujeto + ' · ' + String(sel.mmm).padStart(3, '0')),
              jsx('div', null, 'Tag 1'),
              jsx('div', null, sel.tag1 || '—'),
              jsx('div', null, 'Tag 2'),
              jsx('div', null, sel.tag2 || '—'),
              jsx('div', null, 'Pilar'),
              jsx('div', null, sel.pilar || '—'),
              jsx('div', null, 'Máquina'),
              jsx('div', null, sel.tag6 || '—'),
              jsx('div', null, 'Fecha'),
              jsx('div', null, sel.fecha),
              jsx('div', null, 'Costo'),
              jsx('div', null, fmtC(sel.costo) + ' · ' + fmtH(sel.horas)),
              jsx('div', null, 'Tokens'),
              jsx('div', null, fmtN(sel.tok) + ' · ' + sel.posts + ' posts'),
              jsx('div', null, 'Motor'),
              jsx('div', null, sel.motor || '—'),
              jsx('div', null, 'Perfil'),
              jsx('div', null, sel.prof)
            ),
            jsx('h4', { style: { fontSize: '10px', color: '#8b8095', margin: '14px 0 4px' } }, 'MENSAJES CLAVE DEL USUARIO'),
            (sel.claves || []).length
              ? sel.claves.map((c, i) => jsx('div', { className: 'key', key: i }, c))
              : jsx('div', { className: 'key' }, '(sin mensajes de usuario útiles en esta sesión)'),
            jsx(
              'div',
              { style: { display: 'flex', gap: '6px', marginTop: '12px' } },
              jsx('button', { onClick: copyCard }, 'Copiar sesión'),
              jsx('button', { onClick: () => openSession(sel) }, 'Abrir sesión')
            ),
            jsx('div', { style: { marginTop: '10px', fontSize: '10px', color: '#8b8095', fontFamily: 'monospace', wordBreak: 'break-all' } }, 'id ' + sel.id)
          )
        : jsx('div', { className: 'empty' }, 'Elige una sesión para ver su ficha.')
    )
  )
}

export default {
  id: ID,
  name: NAME,
  version: VERSION,

  register(ctx) {
    ctx.registerMany([
      { id: 'page', area: ROUTES_AREA, data: { path: ROUTE }, render: () => jsx(App, { ctx }) },
      { id: 'nav', area: SIDEBAR_NAV_AREA, data: { path: ROUTE, label: 'Make It Smart', codicon: 'archive' } },
    ])
  },
}
