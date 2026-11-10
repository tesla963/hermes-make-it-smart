/**
 * Hermes, make all my work Smart! — desktop plugin (v0.1)
 *
 * A full page that turns the session archive into a browsable catalog:
 * facets on the left, sessions in the middle, the detail card on the right.
 *
 * Data comes from `plugin-data/<id>/index.json`, built by tools/build_index.py.
 * The plugin never reads state.db itself: the Python indexer already did the
 * work (classification, subjects, counters, costs) and the window only paints.
 * That is the modular seam — another host can reuse the indexer, another window
 * can reuse this index.
 *
 * The disk file is loaded UNCOMPILED, so: no JSX syntax, and the only
 * importable specifiers are @hermes/plugin-sdk, react and react/jsx-runtime.
 * `jsx(type, props)` carries its children inside props, so everything below
 * goes through the tiny `h()` helper instead of raw runtime calls.
 */

import { host, ROUTES_AREA, SIDEBAR_NAV_AREA } from '@hermes/plugin-sdk'
import { jsx, jsxs, Fragment } from 'react/jsx-runtime'
import { useState, useEffect, useMemo } from 'react'

const ID = 'make-my-work-smart'
const NAME = 'Hermes, make all my work Smart!'
const VERSION = '0.1.0'
const ROUTE = '/smart'

/**
 * jsx-runtime wants `children` inside props:
 *   jsx('div', { props })   /   jsxs('div', { props, children: [...] })
 * This keeps the call sites readable — h(tag, props, ...children).
 */
function h(type, props, ...kids) {
  const p = { ...(props || {}) }
  if (kids.length === 1) return jsx(type, { ...p, children: kids[0] })
  if (kids.length > 1) return jsxs(type, { ...p, children: kids })
  return jsx(type, p)
}

const CSS = `
.mmws{display:grid;grid-template-columns:220px 1fr 340px;height:100%;font-size:13px;color:#e8dde4;background:#0d0b0e}
.mmws aside{border-right:1px solid #2a2330;overflow:auto;padding:10px}
.mmws main{overflow:auto;min-width:0}
.mmws .panel{border-left:1px solid #2a2330;overflow:auto;padding:12px}
.mmws h1{font-size:14px;margin:0 0 8px;font-weight:800;letter-spacing:.01em;line-height:1.3}
.mmws input{width:100%;padding:6px 8px;border-radius:6px;border:1px solid #3a3040;background:#17131a;color:inherit}
.mmws .grp{margin:12px 0}
.mmws .grp h4{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:#8b8095;margin:0 0 5px}
.mmws .opt{display:flex;justify-content:space-between;gap:8px;padding:3px 6px;border-radius:5px;cursor:pointer}
.mmws .opt:hover{background:#1d1822}
.mmws .opt.on{background:#2a1a24;color:#f0dbe4}
.mmws .opt i{font-style:normal;color:#8b8095}
.mmws .bar{display:flex;gap:6px;align-items:center;padding:8px 10px;border-bottom:1px solid #2a2330;position:sticky;top:0;background:#100d12;z-index:2;flex-wrap:wrap}
.mmws button{padding:3px 8px;font-size:12px;border-radius:6px;border:1px solid #3a3040;background:#1d1822;color:#cfc4d4;cursor:pointer;white-space:nowrap}
.mmws button.on{background:#5a2040;border-color:#7a2a56;color:#fff}
.mmws table{width:100%;border-collapse:collapse}
.mmws th{font-size:9.5px;text-transform:uppercase;letter-spacing:.06em;color:#8b8095;text-align:left;padding:6px 8px;position:sticky;top:41px;background:#100d12;z-index:1}
.mmws td{padding:3px 8px;vertical-align:top}
.mmws tr.t td{padding-top:9px;font-family:ui-monospace,Menlo,monospace;font-size:11px;font-weight:700;color:#f4e6ee;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:0}
.mmws tr.r{cursor:pointer}
.mmws tr.r td{border-bottom:2px solid #3d3346;color:#cfc4d4}
.mmws tr.r:hover td{background:#171320}
.mmws tr.r.sel td{background:#251521}
.mmws .num{text-align:center;font-variant-numeric:tabular-nums}
.mmws .pill{display:inline-block;padding:1px 6px;border-radius:20px;background:#241d2b;font-size:10.5px;margin-right:4px}
.mmws .empty{padding:30px;text-align:center;color:#8b8095}
.mmws .kbar{position:sticky;bottom:0;display:flex;gap:16px;padding:6px 10px;background:#100d12;border-top:1px solid #2a2330;font-size:11px;align-items:baseline}
.mmws .kbar b{font-size:15px;margin-right:4px;font-variant-numeric:tabular-nums}
.mmws .kbar i{font-style:normal;font-size:8px;text-transform:uppercase;color:#8b8095}
.mmws .card h2{font-size:12.5px;margin:0 0 8px;font-family:ui-monospace,Menlo,monospace;line-height:1.45}
.mmws .kv{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;font-size:11.5px}
.mmws .kv div:nth-child(odd){color:#8b8095}
.mmws .key{margin:6px 0;padding-left:8px;border-left:2px solid #3a3040;color:#cfc4d4;font-size:11.5px;line-height:1.4}
.mmws .hint{color:#8b8095;font-size:11px;margin-left:auto}
`

const norm = (s) =>
  (s || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()

const fmtC = (v) => (v >= 1 ? '$' + v.toFixed(2) : Math.round(v * 100) + '¢')
const fmtH = (m) =>
  m >= 60 ? Math.floor(m / 60) + 'h' + String(Math.round(m % 60)).padStart(2, '0') : Math.round(m) + 'm'
const fmtN = (n) =>
  n >= 1e9
    ? (n / 1e9).toFixed(1) + 'B'
    : n >= 1e6
      ? (n / 1e6).toFixed(1) + 'M'
      : n >= 1e3
        ? (n / 1e3).toFixed(1) + 'k'
        : String(n || 0)

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
    if (await ctx.os.writeClipboard(text)) return true
  } catch (e) {
    /* fall through to the browser API */
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
        if (!res || !res.ok || !res.text) throw new Error('falta index.json — corre tools/build_index.py')
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
      const hay = norm(s.raw + ' ' + s.id + ' ' + s.desc)
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

  if (error)
    return h('div', { className: 'mmws' }, h('div', { className: 'empty' }, 'No pude leer el índice: ' + error))
  if (!data) return h('div', { className: 'mmws' }, h('div', { className: 'empty' }, 'Cargando índice…'))

  const optRow = (key, value, n) =>
    h(
      'div',
      {
        key: key + value,
        className: 'opt' + (f[key] === value ? ' on' : ''),
        onClick: () => setF((p) => ({ ...p, [key]: p[key] === value ? null : value })),
      },
      h('span', null, value),
      h('i', null, n)
    )

  const group = (title, key) =>
    h(
      'div',
      { className: 'grp', key },
      h('h4', null, title),
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
    const head = [
      'n', 'id', 'fecha', 'titulo_actual', 'sujeto', 'tag1', 'tag2', 'descripcion',
      'sujeto_nuevo', 'tag1_nuevo', 'tag2_nuevo', 'descripcion_nueva', 'observaciones',
    ]
    const rows = visible
      .slice()
      .sort((a, b) => a.n - b.n)
      .map((s) =>
        [s.n, s.id, s.fecha, s.raw, s.sujeto, s.tag1, s.tag2, s.desc, '', '', '', '', ''].map(esc).join(',')
      )
    const res = await ctx.files.writeText(
      'data',
      'last-export.csv',
      '\ufeff' + head.join(',') + '\n' + rows.join('\n') + '\n'
    )
    setNote(res && res.ok ? '✔ exportado a plugin-data/data/last-export.csv' : '✗ no pude escribir')
    setTimeout(() => setNote(''), 3000)
  }

  const openSession = (s) => {
    try {
      host.openSession(s.id, { profile: s.prof, intent: 'tab' })
    } catch (e) {
      setNote('✗ ' + ((e && e.message) || e))
      setTimeout(() => setNote(''), 3000)
    }
  }

  return h(
    'div',
    { className: 'mmws' },
    h('style', null, CSS),

    h(
      'aside',
      null,
      h('h1', null, NAME),
      h('input', { placeholder: 'Buscar · 126,305 · 50-75', value: q, onChange: (e) => setQ(e.target.value) }),
      h('div', { className: 'grp' }, h('h4', null, 'Pilar'), countBy('pilar').map(([v, n]) => optRow('pilar', v, n))),
      group('Tag 1 · plataforma', 'tag1'),
      group('Tag 2 · familia', 'tag2')
    ),

    h(
      'main',
      null,
      h(
        'div',
        { className: 'bar' },
        h('strong', null, visible.length + ' de ' + sessions.length),
        h('button', { onClick: () => { setF({ pilar: null, tag1: null, tag2: null }); setQ('') } }, 'Limpiar'),
        h('button', { onClick: copyTitles }, 'Copiar · ' + visible.length),
        h('button', { onClick: exportCsv }, 'Exportar · ' + visible.length),
        h(
          'button',
          { className: showCron ? 'on' : '', onClick: () => setShowCron((v) => !v) },
          (showCron ? 'Hide' : 'Show') + ' Cron · ' + sessions.filter((s) => s.esCron).length
        ),
        h('span', { className: 'hint' }, note)
      ),

      h(
        'table',
        null,
        h(
          'thead',
          null,
          h(
            'tr',
            null,
            ['Nº', 'Fecha', 'Sesión', 'Tags', 'Costo', 'Horas', 'Tokens', 'Posts'].map((x) => h('th', { key: x }, x))
          )
        ),
        h(
          'tbody',
          null,
          visible.flatMap((s) => [
            h(
              'tr',
              { className: 't', key: s.id + '-t' },
              h('td', { className: 'num' }, s.n),
              h(
                'td',
                { colSpan: 7 },
                '[' + s.sujeto + '] ' + String(s.mmm).padStart(3, '0') +
                  (s.tag1 ? ' [' + s.tag1 + ']' : '') +
                  (s.tag2 ? ' [' + s.tag2 + ']' : '') +
                  (s.desc ? ' ' + s.desc : '')
              )
            ),
            h(
              'tr',
              { className: 'r' + (sel && sel.id === s.id ? ' sel' : ''), key: s.id + '-r', onClick: () => setSel(s) },
              h('td', { className: 'num' }, ''),
              h('td', null, s.fecha),
              h('td', null, s.sujeto),
              h('td', null, h('span', { className: 'pill' }, s.tag1 || '—'), h('span', { className: 'pill' }, s.tag2 || '—')),
              h('td', { className: 'num' }, fmtC(s.costo)),
              h('td', { className: 'num' }, fmtH(s.horas)),
              h('td', { className: 'num' }, fmtN(s.tok)),
              h('td', { className: 'num' }, s.posts)
            ),
          ])
        )
      ),

      h(
        'div',
        { className: 'kbar' },
        h('span', null, h('b', null, visible.length), h('i', null, 'sesiones')),
        h('span', null, h('b', null, '$' + totals.costo.toFixed(2)), h('i', null, 'costo')),
        h('span', null, h('b', null, Math.round(totals.horas / 60) + ' h'), h('i', null, 'horas')),
        h('span', null, h('b', null, fmtN(totals.posts)), h('i', null, 'posts')),
        h('span', null, h('b', null, fmtN(totals.tok)), h('i', null, 'tokens'))
      )
    ),

    h(
      'div',
      { className: 'panel card' },
      sel
        ? h(
            Fragment,
            null,
            h('h2', null, sel.raw),
            h(
              'div',
              { className: 'kv' },
              h('div', null, 'Sujeto'), h('div', null, sel.sujeto + ' · ' + String(sel.mmm).padStart(3, '0')),
              h('div', null, 'Tag 1'), h('div', null, sel.tag1 || '—'),
              h('div', null, 'Tag 2'), h('div', null, sel.tag2 || '—'),
              h('div', null, 'Pilar'), h('div', null, sel.pilar || '—'),
              h('div', null, 'Máquina'), h('div', null, sel.tag6 || '—'),
              h('div', null, 'Fecha'), h('div', null, sel.fecha),
              h('div', null, 'Costo'), h('div', null, fmtC(sel.costo) + ' · ' + fmtH(sel.horas)),
              h('div', null, 'Tokens'), h('div', null, fmtN(sel.tok) + ' · ' + sel.posts + ' posts'),
              h('div', null, 'Motor'), h('div', null, sel.motor || '—'),
              h('div', null, 'Perfil'), h('div', null, sel.prof)
            ),
            h('h4', { style: { fontSize: '10px', color: '#8b8095', margin: '14px 0 4px' } }, 'MENSAJES CLAVE DEL USUARIO'),
            (sel.claves || []).length
              ? (sel.claves || []).map((c, i) => h('div', { className: 'key', key: i }, c))
              : h('div', { className: 'key' }, '(sin mensajes de usuario útiles en esta sesión)'),
            h(
              'div',
              { style: { display: 'flex', gap: '6px', marginTop: '12px' } },
              h('button', { onClick: copyCard }, 'Copiar sesión'),
              h('button', { onClick: () => openSession(sel) }, 'Abrir sesión')
            ),
            h(
              'div',
              {
                style: {
                  marginTop: '10px',
                  fontSize: '10px',
                  color: '#8b8095',
                  fontFamily: 'monospace',
                  wordBreak: 'break-all',
                },
              },
              'id ' + sel.id
            )
          )
        : h('div', { className: 'empty' }, 'Elige una sesión para ver su ficha.')
    )
  )
}

export default {
  id: ID,
  name: NAME,
  version: VERSION,

  register(ctx) {
    ctx.registerMany([
      { id: 'page', area: ROUTES_AREA, data: { path: ROUTE }, render: () => h(App, { ctx }) },
      { id: 'nav', area: SIDEBAR_NAV_AREA, data: { path: ROUTE, label: 'Make It Smart', codicon: 'archive' } },
    ])
  },
}
