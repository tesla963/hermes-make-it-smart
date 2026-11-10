/**
 * Hermes, Make All my Work Smart! — desktop plugin (v0.23)
 *
 * Full-page session catalogue mounted at `/smart` ("Make It Smart").
 * Queries REAL sessions from Hermes Desktop via `host.request('profiles.list')`
 * and `host.request('session.list', { limit, profile })` (plus remote routes
 * via `host.profileRoutes()` / `host.requestProfile()`), enriched with
 * `plugin-data/<id>/index.json` and `facets.json` when available, and lazy
 * transcript/title RPCs (`session.resume`, `session.title`).
 *
 * Visual & behavioral twin of `tools/simulator_template.html` (docs/SPEC-UI.md).
 * Loaded uncompiled by Hermes Desktop: only `@hermes/plugin-sdk`, `react`, and
 * `react/jsx-runtime` are imported.
 */

import { host, ROUTES_AREA, SIDEBAR_NAV_AREA } from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'
import { useState, useEffect, useMemo, useRef } from 'react'

const ID = 'make-all-my-work-smart'
const NAME = 'Hermes, Make All my Work Smart!'
const VERSION = '0.23.0'
const ROUTE = '/smart'

/** jsx-runtime helper: keeps uncompiled React code compact and readable. */
function h(type, props, ...kids) {
  const { key, ...p } = props || {}
  const flat = kids.flat().filter((x) => x !== null && x !== undefined && x !== false)
  if (flat.length === 1) return jsx(type, { ...p, children: flat[0] }, key)
  if (flat.length > 1) return jsxs(type, { ...p, children: flat }, key)
  return jsx(type, p, key)
}

/* ------------------------------------------------------------------ */
/* Pure formatting & parsing helpers (exported for test_plugin.mjs)   */
/* ------------------------------------------------------------------ */

const norm = (s) =>
  String(s || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()

const fmtC = (v) =>
  (v || 0) >= 1 ? '$' + Number(v).toFixed(2) : Math.round((v || 0) * 100) + '¢'

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

const fmtT = (n) =>
  n >= 1e9
    ? (n / 1e9).toFixed(1) + 'B'
    : n >= 1e8
      ? Math.round(n / 1e6) + 'M'
      : n >= 1e6
        ? (n / 1e6).toFixed(1) + 'M'
        : n >= 1e3
          ? Math.round(n / 1e3) + 'k'
          : String(n || 0)

const fmtP = (n) => (n >= 1000 ? (n / 1000).toFixed(1) + 'k' : String(n || 0))

/** "126,305" or "50-75" selects sessions by number; anything else is free text. */
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

const esRuido = (x) =>
  !x ||
  /^\s*\[/.test(x) ||
  /^##\s*(script output|run context)/i.test(x) ||
  /you are running as a scheduled cron job/i.test(x) ||
  /^\s*<system/i.test(x) ||
  /^-{3}\s*\n?\s*name:/.test(x) ||
  /^\s*-{3}\s*name:/i.test(x) ||
  /description:\s*"Use when/i.test(String(x).slice(0, 160))

const esCron = (d) =>
  Boolean(d && (d.esCron || /^cron[_-]/i.test(d.id || '') || /^cron[_-]/i.test(d.prof || '')))

const esBorrada = (d) =>
  Boolean(
    d &&
      (/^\s*borrada/i.test(d.tema || '') ||
        /^\s*sesi[oó]n borrada/i.test(d.sujeto || '') ||
        /^\s*sesi[oó]n( de cron)? eliminad/i.test(d.desc || '') ||
        /^\s*\[?sesi[oó]n borrada/i.test(d.raw || ''))
  )

/* Bilingual synonym table from simulator_template.html */
const SIN = {
  'inteligencia artificial': 'ia',
  'artificial intelligence': 'ia',
  'machine learning': 'ia',
  ai: 'ia',
  ia: 'ia',
  respaldo: 'backup',
  respaldos: 'backup',
  backups: 'backup',
  'copias de seguridad': 'backup',
  backup: 'backup',
  correo: 'email',
  correos: 'email',
  mail: 'email',
  buzon: 'email',
  email: 'email',
  disco: 'disk',
  discos: 'disk',
  disck: 'disk',
  unidad: 'disk',
  disk: 'disk',
  contrasena: 'password',
  contraseña: 'password',
  passwords: 'password',
  clave: 'password',
  password: 'password',
  red: 'network',
  redes: 'network',
  networking: 'network',
  trafico: 'network',
  network: 'network',
  seguridad: 'security',
  proteccion: 'security',
  blindaje: 'security',
  security: 'security',
  recuperar: 'recovery',
  recuperacion: 'recovery',
  recuperación: 'recovery',
  rescate: 'recovery',
  recovery: 'recovery',
  permiso: 'permission',
  permisos: 'permission',
  autorizacion: 'permission',
  permission: 'permission',
  servidor: 'vps',
  servidores: 'vps',
  hosting: 'vps',
  vps: 'vps',
  nube: 'cloud',
  cloud: 'cloud',
  programa: 'software',
  programas: 'software',
  aplicacion: 'software',
  app: 'software',
  software: 'software',
  video: 'multimedia',
  videos: 'multimedia',
  audio: 'multimedia',
  foto: 'multimedia',
  fotos: 'multimedia',
  multimedia: 'multimedia',
  traducir: 'traduccion',
  traduccion: 'traduccion',
  translation: 'traduccion',
  resumen: 'resumen',
  resumir: 'resumen',
  summary: 'resumen',
  monitorear: 'monitor',
  vigilar: 'monitor',
  monitoring: 'monitor',
  monitorizar: 'monitor',
  monitor: 'monitor',
  research: 'investigar',
  investigacion: 'investigar',
  investigar: 'investigar',
  buscar: 'buscar',
  busqueda: 'buscar',
  install: 'instalar',
  instalacion: 'instalar',
  instalar: 'instalar',
  config: 'configurar',
  setup: 'configurar',
  configurar: 'configurar',
  database: 'database',
  'base de datos': 'database',
  basededatos: 'database',
  repositorio: 'repository',
  repos: 'repository',
  repo: 'repository',
  repository: 'repository',
  mantenimiento: 'soporte',
  soporte: 'soporte',
  troubleshooting: 'troubleshooting',
  arreglar: 'reparar',
  reparacion: 'reparar',
  roto: 'reparar',
  dano: 'reparar',
  reparar: 'reparar',
}
const SINP = {}
const SINW = {}
Object.keys(SIN).forEach((k) => ((k.indexOf(' ') > 0 ? SINP : SINW)[k] = SIN[k]))
const SINP_KEYS = Object.keys(SINP).sort((a, b) => b.length - a.length)

function sin(t) {
  let x = norm(t || '')
  SINP_KEYS.forEach((k) => {
    x = x.replace(new RegExp('\\b' + k.replace(/ /g, '\\s+') + '\\b', 'g'), ' ~' + SINP[k] + '~ ')
  })
  return x
    .split(/[^a-z0-9áéíóúñü~]+/i)
    .map((w) => {
      if (!w) return ''
      if (w.length > 1 && w[0] === '~' && w[w.length - 1] === '~') return w
      const k = norm(w)
      return SINW[k] ? '~' + SINW[k] + '~' : w
    })
    .filter(Boolean)
    .join(' ')
}

/* Title parser matching tools/build_index.py */
const TITLE_RE =
  /^(?<nnn>\d{3,4})\s+\[(?<subject>.+?)\]\s+(?<mmm>\d{3,4})\s*(?:\[(?<tag1>[^\]]*)\])?\s*(?:\[(?<tag2>[^\]]*)\])?\s*(?<desc>.*?)(?:\s*·\s*(?<verb>[^·]+))?\s*$/
const TITLE_RE_LEGACY =
  /^(?<nnn>\d{3,4})\s+\[(?<subject>.+?)\s+(?<mmm>\d{3,4})\]\s*(?:\[(?<tag1>[^\]]*)\])?\s*(?:\[(?<tag2>[^\]]*)\])?\s*(?<desc>.*?)(?:\s*·\s*(?<verb>[^·]+))?\s*$/

function parseTitle(title) {
  const s = String(title || '').trim()
  const m = s.match(TITLE_RE) || s.match(TITLE_RE_LEGACY)
  return m && m.groups ? m.groups : null
}

function toFecha(startedAt, fallback) {
  if (typeof startedAt === 'number' && startedAt > 0) {
    try {
      const ms = startedAt > 1e12 ? startedAt : startedAt * 1000
      return new Date(ms).toISOString().slice(0, 10)
    } catch (_) {
      /* ignore */
    }
  }
  if (typeof startedAt === 'string' && startedAt.length >= 10) {
    return startedAt.slice(0, 10)
  }
  if (fallback && String(fallback).length >= 10) return String(fallback).slice(0, 10)
  return ''
}

function isoWeek(fecha) {
  if (!fecha || fecha.length < 10) return ''
  const d = new Date(fecha.slice(0, 10) + 'T00:00:00Z')
  if (isNaN(d.getTime())) return ''
  const day = d.getUTCDay() || 7
  d.setUTCDate(d.getUTCDate() + 4 - day)
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1))
  const weekNo = Math.ceil(((d - yearStart) / 86400000 + 1) / 7)
  return d.getUTCFullYear() + '-W' + String(weekNo).padStart(2, '0')
}

const MESNOM = {
  es: ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'],
  en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
}

function nombreMes(m, lang) {
  if (!m || !m.includes('-')) return m || ''
  const [y, mm] = m.split('-')
  const arr = MESNOM[lang] || MESNOM.es
  return (arr[parseInt(mm, 10) - 1] || mm) + ' ' + y
}

/* ------------------------------------------------------------------ */
/* I18N dictionary (1:1 with simulator_template.html)                 */
/* ------------------------------------------------------------------ */

const I18N = {
  es: {
    ordenar: 'Ordenar:',
    limpiar: 'Limpiar',
    copiar: 'Copiar',
    exportar: 'Exportar',
    actualizar: 'Actualizar BD',
    showDel: 'Mostrar Borradas',
    hideDel: 'Ocultar Borradas',
    showCron: 'Mostrar Cron',
    hideCron: 'Ocultar Cron',
    buscar: 'Buscar sujeto, tema, tag…',
    pilar: 'Pilar',
    frente: 'frente de trabajo',
    tag1: 'Marca',
    tag2: 'Contexto',
    tag3: 'Intención',
    tema: 'Tema',
    itTema: 'IT · tema',
    fecha: 'Fecha',
    todoAnio: 'Todo',
    semAbbr: 'sem',
    diaExacto: 'Día exacto',
    rango: 'Rango',
    motor: 'Motor de IA',
    autor: 'Autor',
    maquina: 'Tag 6 · Máquina',
    colN: 'Nº',
    colFecha: 'Fecha',
    colSujeto: 'Sujeto · #',
    colTags: 'Tags',
    colCosto: 'Costo',
    colHoras: 'Horas',
    colTokens: 'Tokens',
    colPosts: 'Posts',
    mostrando: 'Mostrando',
    de: 'de',
    angosto: '⚠ angosto',
    copiarSesion: 'Copiar sesión',
    abrirSesion: 'Abrir sesión',
    mensajes: 'MENSAJES CLAVE DEL USUARIO',
    sinMensajes: '(sin mensajes de usuario útiles en esta sesión)',
    elegir: 'Elige una sesión para ver su ficha.',
    sujeto: 'Sujeto',
    costo: 'Costo',
    horas: 'Horas',
    tokens: 'Tokens',
    perfil: 'Perfil',
    pais: 'País',
    anio: 'Año',
    motores: 'motores',
    autores: 'autores',
    de1: '1 de ',
    kSes1: 'Sesiones',
    kSes2: 'visibles',
    kCos1: 'Costo',
    kCos2: 'acumulado',
    lblPlataforma: 'plataforma',
    lblFamilia: 'familia',
    lblPilar: 'pilar',
    lblPais: 'país',
    lblAnio: 'año',
    lblMaquina: 'máquina',
    lblLibre: 'libre',
    kHor1: 'Horas',
    kHor2: 'trabajo',
    kPost1: 'Total',
    kPost2: 'posts',
    kTok1: 'Total',
    kTok2: 'tokens',
    sinMsgs: '(sin mensajes de usuario en esta sesión)',
    hintUnica: 'Selección única. El sujeto no es faceta: usa el buscador.',
    editarBtn: '✎ Editar nombre y reentrenar el algoritmo',
    editarTit: 'Editar título de la sesión',
    editarHint: 'Al guardar, el plugin escribe el título con autoridad de usuario en state.db vía session.title.',
    cancelar: 'Cancelar',
    guardar: 'Guardar y aprender',
    ocultasFiltro: 'ocultas por filtros',
    ver: 'ver',
    Mas: 'más',
    Menos: '− menos',
    cargando: 'Cargando sesiones de Hermes Desktop…',
    vIntro:
      'Catálogo navegable de tus sesiones: las consulta en vivo desde las bases de Hermes Desktop vía JSON-RPC, les pone nombre canónico y las deja filtrar por marca, contexto, intención y tema.',
    vSub: 'v0.23 · plugin nativo',
    vVer: 'ESTA VERSIÓN',
    vReg: 'REGLAS QUE APRENDIÓ',
    vCerrar: 'Cerrar',
    v1: 'Catálogo de sesiones · NNN [Sujeto] MMM [Tag1] [Tag2] Descripción · Verbo',
    v2: 'Nueve tags declarados; tag1 y tag2 en el nombre, el resto filtros',
    v3: 'El ordinal <b>MMM</b> fuera del corchete del sujeto',
    v4: 'Sin fecha en el título; la fecha es columna y filtro',
    v5: 'Buscador numérico: <span class="mono">126,305</span> y <span class="mono">50-75</span>',
    v6: 'Copiar títulos con su id, copiar ficha, exportar CSV con contador <span class="mono">[CCCC]</span>',
    v7: 'Mostrar/ocultar borradas y sesiones de cron',
    v8: 'Switch ES/EN — no cambia lo que el clasificador entiende',
    v9: 'La serie se unifica: <span class="mono">DNS + Correo</span> son 50 sesiones, no 24 chips',
    r1: 'Un calificador estrecha, no nombra — el dominio va a la descripción',
    r2: 'La marca y el producto son dos cosas: USPS + Ground Advantage',
    r3: 'El sujeto es el paciente, no quien sostiene la ficha',
    r4: 'Una serie, un pilar: si hay 40 hermanos, el que no encaja está mal',
  },
  en: {
    ordenar: 'Sort:',
    limpiar: 'Clear',
    copiar: 'Copy',
    exportar: 'Export',
    actualizar: 'Refresh DB',
    showDel: 'Show Deleted',
    hideDel: 'Hide Deleted',
    showCron: 'Show Cron',
    hideCron: 'Hide Cron',
    buscar: 'Search subject, topic, tag…',
    pilar: 'Pillar',
    frente: 'work front',
    tag1: 'Maker',
    tag2: 'Context',
    tag3: 'Intention',
    tema: 'Theme',
    itTema: 'IT · topic',
    fecha: 'Date',
    todoAnio: 'All',
    semAbbr: 'wk',
    diaExacto: 'Exact day',
    rango: 'Range',
    motor: 'AI engine',
    autor: 'Author',
    maquina: 'Tag 6 · Machine',
    colN: 'No.',
    colFecha: 'Date',
    colSujeto: 'Subject · #',
    colTags: 'Tags',
    colCosto: 'Cost',
    colHoras: 'Hours',
    colTokens: 'Tokens',
    colPosts: 'Posts',
    mostrando: 'Showing',
    de: 'of',
    angosto: '⚠ narrow',
    copiarSesion: 'Copy session',
    abrirSesion: 'Open session',
    mensajes: 'KEY USER MESSAGES',
    sinMensajes: '(no useful user messages in this session)',
    elegir: 'Pick a session to see its card.',
    sujeto: 'Subject',
    costo: 'Cost',
    horas: 'Hours',
    tokens: 'Tokens',
    perfil: 'Profile',
    pais: 'Country',
    anio: 'Year',
    motores: 'engines',
    autores: 'authors',
    de1: '1 of ',
    kSes1: 'Visible',
    kSes2: 'sessions',
    kCos1: 'Total',
    kCos2: 'cost',
    lblPlataforma: 'platform',
    lblFamilia: 'family',
    lblPilar: 'pillar',
    lblPais: 'country',
    lblAnio: 'year',
    lblMaquina: 'machine',
    lblLibre: 'free',
    kHor1: 'Work',
    kHor2: 'hours',
    kPost1: 'Total',
    kPost2: 'posts',
    kTok1: 'Total',
    kTok2: 'tokens',
    sinMsgs: '(no user messages in this session)',
    hintUnica: 'Single selection. Subject is not a facet: use the search bar.',
    editarBtn: '✎ Edit title and retrain the algorithm',
    editarTit: 'Edit session title',
    editarHint: 'Saving writes the title with user authority into state.db via session.title.',
    cancelar: 'Cancel',
    guardar: 'Save & learn',
    ocultasFiltro: 'hidden by filters',
    ver: 'show',
    Mas: 'more',
    Menos: '− less',
    cargando: 'Loading Hermes Desktop sessions…',
    vIntro:
      'A browsable catalogue of your sessions: queries them live from Hermes Desktop databases over JSON-RPC, gives each a canonical name and lets you filter by maker, context, intention and theme.',
    vSub: 'v0.23 · native plugin',
    vVer: 'THIS VERSION',
    vReg: 'RULES IT LEARNED',
    vCerrar: 'Close',
    v1: 'Session catalogue · NNN [Subject] MMM [Tag1] [Tag2] Description · Verb',
    v2: 'Nine tags declared; tag1 and tag2 in the name, the rest are filters',
    v3: 'The <b>MMM</b> ordinal sits outside the subject bracket',
    v4: 'No date in the title; the date is a column and a filter',
    v5: 'Numeric search: <span class="mono">126,305</span> and <span class="mono">50-75</span>',
    v6: 'Copy titles with their id, copy the record, export CSV with a <span class="mono">[CCCC]</span> counter',
    v7: 'Show/hide deleted sessions and cron sessions',
    v8: 'ES/EN switch — it never changes what the classifier understands',
    v9: 'The series unifies: <span class="mono">DNS + Correo</span> is 50 sessions, not 24 chips',
    r1: 'A qualifier narrows, it does not name — the domain goes in the description',
    r2: 'The brand and the product are two things: USPS + Ground Advantage',
    r3: 'The subject is the patient, not whoever holds the file',
    r4: 'One series, one pillar: with 40 siblings, the one that does not fit is wrong',
  },
}

/* ------------------------------------------------------------------ */
/* Scoped CSS (1:1 from tools/simulator_template.html & SPEC-UI.md)   */
/* ------------------------------------------------------------------ */

const CSS = `
.mmws{--kbar-h:33px;--aside-ef:264px;--bg:#0d0b0e;--bg2:#141117;--card:#17131a;--line:#2a2330;--line2:#3a3040;--tx:#eae4ee;--tx2:#b9aec4;--tx3:#857a92;--wine:#a3234a;--wine2:#d94f78;--gold:#c9a227;--ok:#3f9e6a;
position:relative;display:flex;flex-direction:column;width:100%;height:100%;min-height:0;overflow:hidden;background:var(--bg);color:var(--tx);font:14px/1.55 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",sans-serif}
.mmws *{box-sizing:border-box}
.mmws h1{font-size:12.5px;margin:0;letter-spacing:.01em;font-weight:800;color:var(--tx)}
.mmws h4{margin:13px 0 5px;font-size:9.5px;text-transform:uppercase;letter-spacing:.08em;color:var(--tx3);display:flex;justify-content:space-between;align-items:center;gap:4px;flex-wrap:wrap}
.mmws h4 span{font-weight:400;text-transform:none;letter-spacing:0;color:var(--tx3);font-size:9.5px}
.mmws .sub{color:var(--tx2);font-size:12.5px}
.mmws .mono{font-family:ui-monospace,Menlo,monospace;font-size:12px}
.mmws header.top{flex:0 0 auto;z-index:40;background:linear-gradient(180deg,#100d12,#0d0b0e);border-bottom:1px solid var(--line);padding:10px 18px}
.mmws .brandrow{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.mmws .bodywrap{flex:1 1 auto;min-height:0;display:flex;align-items:stretch;position:relative;overflow:hidden}
.mmws aside{width:var(--aside-ef);flex:0 0 var(--aside-ef);height:100%;overflow-y:auto;overflow-x:hidden;scrollbar-width:none;-ms-overflow-style:none;overscroll-behavior:contain;border-right:1px solid var(--line);background:var(--bg2);padding:9px 10px 14px}
.mmws aside::-webkit-scrollbar{display:none;width:0;height:0}
.mmws.sinFiltros aside{display:none}
.mmws main{flex:1 1 auto;min-width:0;height:100%;overflow-y:auto;overflow-x:hidden;padding:0 0 40px}
.mmws .toolbar{position:sticky;top:0;z-index:30;background:rgba(13,11,14,.98);backdrop-filter:blur(6px);border-bottom:1px solid var(--line);padding:8px 16px 7px;display:flex;gap:8px; row-gap:6px;align-items:center;flex-wrap:wrap}
.mmws .counter{font-size:12.5px;color:var(--tx2);flex:0 0 auto;white-space:nowrap}
.mmws .counter b{color:#fff}
.mmws .trow{display:flex;flex-wrap:nowrap;align-items:center;gap:6px;width:100%;min-width:0;overflow:hidden}
.mmws .trow>button{flex:0 0 auto;white-space:nowrap}
.mmws button{font:inherit;font-size:12px;cursor:pointer;border-radius:6px;border:1px solid var(--line2);background:#1d1822;color:var(--tx2);padding:3px 8px;white-space:nowrap}
.mmws button:hover{border-color:var(--wine);color:#fff}
.mmws button.on{background:var(--wine);border-color:var(--wine);color:#fff}
.mmws .chips{display:flex;gap:6px;flex-wrap:wrap;align-items:center;flex:1 0 100%;width:100%;margin-top:2px;min-height:28px;justify-content:flex-start}
.mmws .chipwrap{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-left:auto}
.mmws .chips>button.clrbtn{margin-left:0;flex:0 0 auto}
.mmws .chip{flex:0 0 auto;background:#251521;border:1px solid #4a2033;color:#f6dbe4;border-radius:999px;padding:2px 4px 2px 9px;font-size:11.5px;display:inline-flex;align-items:center;gap:6px}
.mmws .chip b{cursor:pointer;color:var(--wine2);font-weight:700}
.mmws button.primary{background:var(--wine);border-color:var(--wine);color:#fff}
.mmws button.primary.ghost,.mmws button.primary:disabled{background:transparent;border-color:var(--line2);color:var(--tx3);cursor:default;box-shadow:none}
.mmws button.primary.ghost:hover,.mmws button.primary:disabled:hover{border-color:var(--line2);color:var(--tx3)}
.mmws .opt{display:flex;align-items:center;gap:4px;padding:2.5px 5px;border-radius:5px;cursor:pointer;font-size:12px;white-space:nowrap;overflow:hidden}
.mmws .opt>span:first-of-type{overflow:hidden;text-overflow:ellipsis;flex:1 1 auto}
.mmws .opt:hover{background:#1e1923}
.mmws .opt input{accent-color:var(--wine2);margin:0;cursor:pointer}
.mmws .opt .n{margin-left:5px;flex:0 0 auto;font-size:11px;color:var(--tx3);font-variant-numeric:tabular-nums}
.mmws .opt .n::before,.mmws .node>.hd .n::before{content:"("}
.mmws .opt .n::after,.mmws .node>.hd .n::after{content:")"}
.mmws .opt.sel{background:#251521;color:#fff}
.mmws .opt.empty{display:block;opacity:.45;font-style:italic}
.mmws .more{padding:3px 6px;font-size:10.5px;color:#8fd0f5;cursor:pointer;user-select:none}
.mmws .more:hover{color:#b9e6ff;background:#1d1822;border-radius:5px}
.mmws aside h4.fold{cursor:pointer;user-select:none;justify-content:flex-start;gap:5px}
.mmws aside h4.fold .caret{font-size:9px;color:#6f6579;flex:0 0 auto}
.mmws aside h4.fold.off{color:#6f6579}
.mmws .qhint{color:#f0b529;cursor:help}
.mmws .qshow{font-size:10.5px;padding:1px 7px;border-radius:5px;background:#2a2110;border:1px solid #4a3a12;color:#f0b529;cursor:pointer;margin-left:4px}
.mmws .qshow:hover{background:#3a2c14;color:#ffd166}
.mmws .node{border:1px solid var(--line);border-radius:6px;margin-bottom:4px;overflow:hidden}
.mmws .node>.hd{display:flex;align-items:center;gap:4px;padding:4px 7px;background:#1a1520;cursor:pointer;font-size:12.5px;font-weight:600;user-select:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mmws .node>.hd .n{margin-left:auto;flex:0 0 auto;color:var(--tx3);font-weight:400;font-size:11px}
.mmws .ynode>.hd{font-weight:700;color:var(--tx);font-size:12.5px;background:#221a2b}
.mmws .ynode.sel>.hd{background:#2a1f38;color:#f4e6ee}
.mmws .ynode.sel>.hd .n{color:#c9a8f0}
.mmws .ynode>.hd .n{font-weight:700;color:var(--tx2)}
.mmws .ynode>.bd{border-left:2px solid #453063;margin-left:7px;padding-left:4px}
.mmws .mnode>.hd{font-size:11.5px;font-weight:600}
.mmws .node>.hd .caret{color:var(--tx3);font-size:9px;width:9px;text-align:center}
.mmws .node>.bd{display:none;padding:2px 5px 5px}
.mmws .node.open>.bd{display:block}
.mmws .node.sel>.hd{background:#2a1220;color:#fff}
.mmws table{width:100%;border-collapse:collapse;font-size:12.5px;table-layout:fixed}
.mmws th,.mmws td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top;overflow-wrap:anywhere}
.mmws th{position:sticky;top:0;background:#1a151f;color:var(--tx3);font-size:10px;text-transform:uppercase;letter-spacing:.05em;cursor:pointer;white-space:nowrap;z-index:20;text-align:center}
.mmws th:hover{color:#fff}
.mmws th.tight,.mmws td.tight{white-space:nowrap}
.mmws td.cen{text-align:center !important}
.mmws td.num{text-align:right;font-variant-numeric:tabular-nums;color:var(--tx2);white-space:nowrap}
.mmws #tb th:nth-child(1){width:48px;text-align:center}
.mmws #tb th:nth-child(2){width:84px;padding-left:8px !important;text-align:left !important}
.mmws #tb th:nth-child(3){width:auto;text-align:left}
.mmws #tb th:nth-child(4){width:56px}
.mmws #tb th:nth-child(5){width:54px}
.mmws #tb th:nth-child(6){width:64px}
.mmws #tb th:nth-child(7){width:50px}
.mmws #tb th:nth-child(1),.mmws #tb td.ncol{padding:6px 0;text-align:center;white-space:nowrap;width:48px}
.mmws td.fecha{padding-left:8px !important;text-align:left !important;color:var(--tx3)}
.mmws #tb td.ttitle{padding:6px 8px 2px 0;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:10.5px;line-height:1.45;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;border-bottom:none !important;color:#f4e6ee;font-weight:700}
.mmws tr.t{cursor:pointer}
.mmws tr.t td.ncol.t{font-family:ui-monospace,Menlo,monospace;font-size:10.5px;line-height:1.45;font-weight:700;color:#f4e6ee;border-bottom:none !important;vertical-align:baseline}
.mmws tr.t .ttitle .tfac{color:#f4e6ee;font-weight:700}
.mmws tr.t .ttitle .tdesc{color:#f4e6ee;font-weight:700;letter-spacing:.005em}
.mmws tr.t:hover .ttitle .tfac{color:var(--tx2)}
.mmws tr.t .ttitle.borrada .tdesc{text-decoration:line-through;text-decoration-color:rgba(217,79,120,.65);text-decoration-thickness:1px}
.mmws tr.r{cursor:pointer}
.mmws tr.r:hover{background:#1b1620}
.mmws tr.r.sele{background:#251521}
.mmws tr.r>td{border-bottom:2px solid #3d3346;padding-top:4px}
.mmws #tb td:nth-child(3){padding-left:8px;overflow:hidden;text-overflow:ellipsis}
.mmws .pill{display:inline-block;font-size:10.5px;padding:1px 6px;border-radius:999px;border:1px solid var(--line2);color:var(--tx2);background:#1c1721;white-space:nowrap}
.mmws .pill.pick{cursor:pointer;transition:filter .12s,outline-color .12s}
.mmws .pill.pick:hover{filter:brightness(1.35);outline:1px solid var(--wine2);outline-offset:1px}
.mmws .pill.s{color:#8fd0f5;background:#0f2431;border-color:#1f4a63;max-width:140px;overflow:hidden;text-overflow:ellipsis;vertical-align:bottom}
.mmws .pill.s.del{opacity:.6;border-style:dashed}
.mmws .pill.tag1{color:#f0d48a;background:#2a2210;border-color:#55461f}
.mmws .pill.tag2{color:#d3e3f3;background:#121d28;border-color:#24404f}
.mmws .pill.tag3{color:#c9a8f0;background:#221634;border-color:#453063}
.mmws .pill.tag4{color:#96e0b0;background:#0f2618;border-color:#1f4a30}
.mmws .pill.tag5{color:#f2a8c4;background:#2b1220;border-color:#55233d}
.mmws .pill.tag6{color:#f5b98f;background:#2b1a0f;border-color:#553620}
.mmws .pill.tag7{color:#8fe6e0;background:#0d2725;border-color:#1f4a46}
.mmws .pill.tag8{color:#b8b8f5;background:#1a1a33;border-color:#33335f}
.mmws .pill.tag9{color:#d8ec8f;background:#222b0f;border-color:#44551f}
.mmws .langsw{margin-left:auto;display:inline-flex;gap:2px;padding:2px;align-items:center;border-radius:7px;background:transparent}
.mmws .langsw span{padding:1px 6px;border-radius:4px;font-size:10px;letter-spacing:.06em;color:var(--tx3);font-weight:700}
.mmws .langsw span.on{background:var(--wine);color:#fff}
.mmws .panel{position:absolute;right:0;top:0;bottom:0;width:360px;max-width:100%;background:#141117;border-left:1px solid var(--line);transform:translateX(100%);transition:transform .18s;z-index:70;box-shadow:-20px 0 40px #0009;display:flex;flex-direction:column}
.mmws .panel.on{transform:none}
.mmws .pbody{overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain;padding:14px 16px 20px;flex:1;scrollbar-width:thin;scrollbar-color:#4a3f57 transparent}
.mmws .pbar{padding:9px 16px;border-bottom:1px solid var(--line);display:flex;gap:8px;align-items:center;background:#100d12}
.mmws .pbar.bottom{border-bottom:none;border-top:1px solid var(--line)}
.mmws .pbar .x{margin-left:auto;cursor:pointer;color:var(--tx3);font-size:16px}
.mmws .openbtn{background:var(--wine);border:1px solid var(--wine);color:#fff;border-radius:6px;padding:3px 8px;font-size:12px;font-weight:600;cursor:pointer}
.mmws .pname{font-family:ui-monospace,Menlo,monospace;font-size:17px;color:#f0dbe4;background:#1d1420;border:1px solid #3a2030;border-radius:8px;padding:9px 11px;margin:0 0 10px;line-height:1.5;word-break:break-word}
.mmws .ptitle{font-size:14.5px;font-weight:650;margin:0 0 6px;line-height:1.35;color:var(--tx)}
.mmws .psum{font-size:13px;color:var(--tx2);background:#1a1520;border-left:3px solid var(--wine);padding:9px 11px;border-radius:0 7px 7px 0;margin:0 0 12px}
.mmws .kv{display:grid;grid-template-columns:92px 1fr;gap:4px 10px;font-size:12.5px;margin:0 0 12px}
.mmws .kv div:nth-child(odd){color:var(--tx3)}
.mmws .klist{list-style:none;padding:0;margin:0}
.mmws .klist li{font-size:12.5px;color:var(--tx2);padding:6px 0 6px 14px;border-bottom:1px solid var(--line);position:relative}
.mmws .klist li::before{content:"▸";position:absolute;left:0;color:var(--wine2)}
.mmws .why{font-size:11.5px;color:var(--tx3);background:#151119;border:1px dashed var(--line2);border-radius:7px;padding:8px 10px;margin:10px 0}
.mmws .pidfoot{margin-top:10px;padding-top:8px;border-top:1px solid var(--line);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:10px;line-height:1.45;color:var(--tx3);word-break:break-all;user-select:all}
.mmws .pidfoot span{text-transform:uppercase;letter-spacing:.06em;font-size:9px;opacity:.7;margin-right:4px}
.mmws .footrow{flex:0 0 var(--kbar-h);height:var(--kbar-h);display:flex;align-items:stretch;z-index:60;background:#0f0c13d9;backdrop-filter:blur(8px);border-top:1px solid var(--line2)}
.mmws .vbadge{width:var(--aside-ef);flex:0 0 var(--aside-ef);height:100%;display:flex;align-items:center;justify-content:flex-start;gap:7px;cursor:pointer;border-right:1px solid var(--line2);padding:0 10px;font:600 9.5px/1 ui-monospace,Menlo,monospace;letter-spacing:.11em;color:#c9a8f0}
.mmws.sinFiltros .vbadge{width:auto;flex:0 0 auto}
.mmws .vbadge:hover{background:#171320;color:#e6d3f2}
.mmws .vbadge b{font-weight:700;color:#eee6f3}
.mmws .vbadge i{width:5px;height:5px;border-radius:50%;background:#8fd0f5;box-shadow:0 0 6px #8fd0f5aa;font-style:normal}
.mmws .kbar{flex:1 1 auto;display:flex;align-items:stretch;gap:0;padding:0 4px}
.mmws .kbar .kpi{flex:1 1 0;position:relative;display:flex;flex-direction:row;align-items:flex-end;justify-content:flex-start;gap:6px;padding:7px 10px 8px}
.mmws .kbar .kpi+.kpi::before{content:"";position:absolute;left:0;top:6px;bottom:6px;width:1px;background:linear-gradient(180deg,transparent,#4a3d5e 22%,#4a3d5e 78%,transparent)}
.mmws .kbar .kpi b{display:block;font-size:17px;line-height:1.0;font-variant-numeric:tabular-nums;letter-spacing:-.02em;font-weight:650;margin:0 0 -1px 0}
.mmws .kbar .kpi .lb{display:flex;flex-direction:column;line-height:1.06}
.mmws .kbar .kpi .lb i{font-style:normal;font-size:8px;text-transform:uppercase;letter-spacing:.05em;color:var(--tx3)}
.mmws .kbar .kpi.accent b{color:var(--wine2)}
.mmws .kbar .kpi.good b{color:var(--ok)}
.mmws .kbar .kpi.gold b{color:var(--gold)}
.mmws .kbar .kpi.tok b{color:#4bb8d8}
.mmws .kbar .kpi.pst b{color:#c9c2d6}
.mmws .hint{font-size:11px;color:var(--tx3);margin:6px 0 0}
.mmws .modal{position:fixed;inset:0;background:#000a;display:flex;align-items:center;justify-content:center;z-index:90}
.mmws .modal .box{background:#17131a;border:1px solid var(--line2);border-radius:12px;padding:18px;width:min(580px,92vw);max-height:85vh;overflow:auto}
.mmws .modal input{width:100%;background:#100d13;border:1px solid var(--line2);color:var(--tx);border-radius:7px;padding:8px 10px;font-size:13px;font-family:ui-monospace,Menlo,monospace}
.mmws .modal .row{display:flex;gap:8px;justify-content:flex-end;margin-top:12px}
.mmws button.bok{margin-left:auto;background:#2a1a3d;border-color:#6b4a9e;color:#e8dde4}
.mmws button.bok:hover{background:#38234f;border-color:#8f6bc4}
`

/* ------------------------------------------------------------------ */
/* Gateway RPC & File Bridge                                          */
/* ------------------------------------------------------------------ */

async function callRpc(ctx, method, params) {
  const req = (ctx && ctx.host && ctx.host.request) || (host && host.request)
  if (typeof req !== 'function') return null
  try {
    const res = await req(method, params || {})
    return res && typeof res === 'object' ? res : null
  } catch (_) {
    return null
  }
}

async function copyText(ctx, text) {
  try {
    if (ctx && ctx.os && ctx.os.writeClipboard && (await ctx.os.writeClipboard(text))) return true
  } catch (_) {
    /* fallback below */
  }
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch (_) {
    try {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      const ok = document.execCommand('copy')
      ta.remove()
      return Boolean(ok)
    } catch (__e) {
      return false
    }
  }
}

/**
 * Fetch real sessions from Hermes Desktop via `profiles.list` + `session.list`
 * (and `profileRoutes` / `requestProfile` when configured), merging precomputed
 * metrics/facets from `index.json` and `facets.json` in plugin-data.
 */
async function loadCatalogue(ctx) {
  let idxData = null
  let facetsMap = {}

  if (ctx && ctx.files && typeof ctx.files.readText === 'function') {
    try {
      const [idxRes, facRes] = await Promise.all([
        ctx.files.readText('data', 'index.json').catch(() => null),
        ctx.files.readText('data', 'facets.json').catch(() => null),
      ])
      if (idxRes && idxRes.ok && idxRes.text) idxData = JSON.parse(idxRes.text)
      if (facRes && facRes.ok && facRes.text) facetsMap = JSON.parse(facRes.text)
    } catch (_) {
      /* optional cache */
    }
  }

  const idxById = new Map()
  if (idxData && Array.isArray(idxData.sessions)) {
    for (const s of idxData.sessions) {
      if (s && s.id) idxById.set(s.id, s)
    }
  }

  // 1. Discover profiles via host.request('profiles.list')
  const profNames = new Set(['default'])
  const profRes = await callRpc(ctx, 'profiles.list', { include_sessions: false })
  if (profRes && Array.isArray(profRes.profiles)) {
    for (const p of profRes.profiles) {
      if (p && p.name) profNames.add(String(p.name))
    }
  } else if (ctx && ctx.host && ctx.host.profiles && typeof ctx.host.profiles.list === 'function') {
    try {
      const list = await ctx.host.profiles.list()
      if (Array.isArray(list)) list.forEach((p) => p && p.name && profNames.add(String(p.name)))
    } catch (_) {
      /* ignore */
    }
  }

  // 2. Query session.list per profile via host.request
  const liveById = new Map()
  await Promise.all(
    [...profNames].map(async (prof) => {
      const res = await callRpc(ctx, 'session.list', { limit: 2000, profile: prof })
      if (res && Array.isArray(res.sessions)) {
        for (const row of res.sessions) {
          if (row && row.id && !liveById.has(row.id)) {
            liveById.set(row.id, { ...row, _prof: prof })
          }
        }
      }
    })
  )

  // 3. Also query remote profile routes via host.profileRoutes() + host.requestProfile()
  const routesFn = (ctx && ctx.host && ctx.host.profileRoutes) || (host && host.profileRoutes)
  const reqProfFn = (ctx && ctx.host && ctx.host.requestProfile) || (host && host.requestProfile)
  if (typeof routesFn === 'function' && typeof reqProfFn === 'function') {
    try {
      const routes = (await routesFn()) || []
      await Promise.all(
        routes.map(async (rt) => {
          try {
            const r = await reqProfFn(rt, 'session.list', { limit: 2000 })
            if (r && Array.isArray(r.sessions)) {
              for (const row of r.sessions) {
                if (row && row.id && !liveById.has(row.id)) {
                  liveById.set(row.id, { ...row, _prof: (rt && rt.profile) || 'remote' })
                }
              }
            }
          } catch (_) {
            /* skip unreachable route */
          }
        })
      )
    } catch (_) {
      /* ignore */
    }
  }

  // 4. Combine live gateway rows with index.json cache
  const allIds = new Set([...liveById.keys(), ...idxById.keys()])
  const merged = []

  for (const id of allIds) {
    const live = liveById.get(id)
    const idx = idxById.get(id) || {}
    const ex = facetsMap[id] || {}

    const rawTitle = String((live && live.title) || idx.raw || '').trim()
    const g = parseTitle(rawTitle)

    const fecha = toFecha(live && live.started_at, idx.fecha)
    const mes = fecha ? fecha.slice(0, 7) : idx.mes || ''
    const semana = isoWeek(fecha) || idx.semana || ''
    const anio = (ex.anio || idx.anio || ex.tag5 || idx.tag5 || (fecha ? fecha.slice(0, 4) : '') || '').trim()

    const sujeto = (
      (g && g.subject) ||
      ex.sujeto ||
      idx.sujeto ||
      (rawTitle ? rawTitle.slice(0, 36) : 'Sin título')
    ).trim()
    const tag1 = ((g && g.tag1) || ex.tag1 || idx.tag1 || '').trim()
    const tag2 = ((g && g.tag2) || ex.tag2 || idx.tag2 || '').trim()
    const tag3 = (ex.tag3 || idx.tag3 || '').trim()
    const pilar = (ex.pilar || idx.pilar || ex.tag4 || idx.tag4 || '').trim()
    const pais = (ex.pais || idx.pais || '').trim()
    const tag4 = (ex.tag4 || idx.tag4 || pais || pilar || '').trim()
    const tag5 = (ex.tag5 || idx.tag5 || anio || '').trim()
    const tag6 = (ex.tag6 || idx.tag6 || '').trim()
    const desc = ((g && g.desc) || idx.desc || (live && live.preview) || rawTitle || '').trim()
    const verb = ((g && g.verb) || idx.verb || '').trim()
    const prof = (live && live._prof) || idx.prof || 'default'
    const mc = Number((live && (live.live_message_count || live.message_count)) || ex.mc || idx.mc || idx.posts || 0)
    const posts = Number(idx.posts || Math.max(1, Math.round(mc / 2)) || 0)
    const tok = Number(idx.tok_tot || idx.tok || 0)
    const costo = Number(idx.costo || 0)
    const horas = Number(idx.horas || 0)
    const motor = (ex.motor || idx.motor || '').trim()
    const autor = (idx.autor || (prof === 'default' ? 'Lisa' : prof)).trim()
    const claves = Array.isArray(idx.claves) ? idx.claves : []
    const resumen = idx.resumen || (claves[0] || (live && live.preview) || '')

    merged.push({
      n: g ? parseInt(g.nnn, 10) : Number(idx.n || 0),
      mmm: g ? parseInt(g.mmm, 10) : Number(idx.mmm || 1),
      sujeto,
      tag1,
      tag2,
      tag3,
      tag4,
      tag5,
      tag6,
      tag7: ex.tag7 || idx.tag7 || '',
      tag8: ex.tag8 || idx.tag8 || '',
      tag9: ex.tag9 || idx.tag9 || '',
      pilar,
      pais,
      anio,
      dom: idx.dom || 'Software',
      tema: idx.tema || desc,
      desc,
      verb,
      raw: rawTitle || `${sujeto} ${desc}`.trim(),
      id,
      prof,
      autor,
      motor,
      motor_det: idx.motor_det || '',
      fecha,
      mes,
      semana,
      costo,
      horas,
      tok,
      tok_tot: tok,
      posts,
      mc,
      claves,
      resumen,
      esCron: Boolean(idx.esCron || /^cron[_-]/i.test(id) || /^cron[_-]/i.test(prof)),
      _canonical: Boolean(g),
    })
  }

  // Assign sequential NNN to sessions that don't have one yet (oldest first)
  let maxN = merged.reduce((m, r) => (r.n > m ? r.n : m), 0)
  const unnumbered = merged.filter((r) => !r.n).sort((a, b) => String(a.fecha).localeCompare(String(b.fecha)))
  for (const r of unnumbered) {
    maxN += 1
    r.n = maxN
  }

  merged.sort((a, b) => a.n - b.n)

  // Compute search synonym index per row once
  for (const d of merged) {
    d._s = sin([d.desc, d.tema, d.sujeto, d.tag1, d.tag2, d.pilar, d.n, d.id].join(' '))
  }

  const canonicalCount = merged.filter((d) => d._canonical).length
  return {
    sessions: merged,
    total: merged.length,
    canonicalCount,
    newCount: merged.length - canonicalCount,
    fromLiveRpc: liveById.size > 0,
  }
}

/* ------------------------------------------------------------------ */
/* Main React Component                                               */
/* ------------------------------------------------------------------ */

function App({ ctx }) {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [f, setF] = useState({
    tag1: null,
    tag2: null,
    tag3i: null,
    tag3: null,
    tag4: null,
    tag5: null,
    tag6: null,
    motor: null,
    autor: null,
    anio: null,
    mes: null,
    sem: null,
    dia: '',
    d1: '',
    d2: '',
  })
  const [folded, setFolded] = useState(() => new Set(['tag2', 'tag3']))
  const [expanded, setExpanded] = useState(() => new Set())
  const [openNodes, setOpenNodes] = useState(() => new Set())
  const [showElim, setShowElim] = useState(false)
  const [showCron, setShowCron] = useState(false)
  const [sinFiltros, setSinFiltros] = useState(false)
  const [orden, setOrden] = useState({ k: 'fecha', asc: false })
  const [sel, setSel] = useState(null)
  const [editModal, setEditModal] = useState(false)
  const [editVal, setEditVal] = useState('')
  const [vModal, setVModal] = useState(false)
  const [btnMsg, setBtnMsg] = useState({ copia: '', expc: '', updb: '', pcopia: '' })
  const [lang, setLang] = useState(() => {
    try {
      return localStorage.getItem('mmws-lang') === 'en' ? 'en' : 'es'
    } catch (_) {
      return 'es'
    }
  })

  const t = (k) => (I18N[lang] && I18N[lang][k]) || k

  const toggleLang = () => {
    const next = lang === 'es' ? 'en' : 'es'
    setLang(next)
    try {
      localStorage.setItem('mmws-lang', next)
    } catch (_) {
      /* ignore */
    }
  }

  const refreshData = async (reportBtn = false) => {
    const res = await loadCatalogue(ctx)
    setSessions(res.sessions)
    setLoading(false)
    // Open the newest year node in Fecha tree automatically
    const years = [...new Set(res.sessions.map((d) => (d.mes || '').slice(0, 4)).filter(Boolean))].sort().reverse()
    if (years.length) {
      setOpenNodes((prev) => {
        const next = new Set(prev)
        if (!next.has('init:' + years[0])) {
          next.add('y:' + years[0])
          next.add('init:' + years[0])
        }
        return next
      })
    }
    if (reportBtn) {
      setBtnMsg((p) => ({ ...p, updb: `✔ ${res.newCount} nuevas · ${res.canonicalCount} sin cambios` }))
      setTimeout(() => setBtnMsg((p) => ({ ...p, updb: '' })), 4000)
    }
  }

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const res = await loadCatalogue(ctx)
        if (!alive) return
        setSessions(res.sessions)
        const years = [...new Set(res.sessions.map((d) => (d.mes || '').slice(0, 4)).filter(Boolean))].sort().reverse()
        if (years.length) {
          setOpenNodes(new Set(['y:' + years[0], 'init:' + years[0]]))
        }
      } finally {
        if (alive) setLoading(false)
      }
    })()
    return () => {
      alive = false
    }
  }, [ctx])

  // Escape closes detail panel and modals
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') {
        setSel(null)
        setEditModal(false)
        setVModal(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // Lazily hydrate user messages from live session.resume when opening a session with no cached claves
  const selectSession = async (d) => {
    if (sel && sel.id === d.id) {
      setSel(null)
      return
    }
    setSel(d)
    if ((!d.claves || d.claves.length === 0) && d.id) {
      const res = await callRpc(ctx, 'session.resume', {
        session_id: d.id,
        profile: d.prof === 'default' ? undefined : d.prof,
        lazy: true,
      })
      if (res && Array.isArray(res.messages)) {
        const userMsgs = res.messages
          .filter((m) => m && m.role === 'user' && typeof m.content === 'string' && !esRuido(m.content))
          .map((m) => m.content.replace(/\s+/g, ' ').trim().slice(0, 400))
          .filter(Boolean)
          .slice(0, 6)
        const liveModel = (res.info && res.info.model) || d.motor
        if (userMsgs.length || liveModel) {
          d.claves = userMsgs
          if (liveModel && !d.motor) d.motor = liveModel
          setSel({ ...d })
        }
      }
    }
  }

  const nums = useMemo(() => numSel(q), [q])
  const qs = useMemo(() => (nums ? '' : sin(q)), [q, nums])
  const qNorm = useMemo(() => norm(q), [q])

  const pass = (d, ...skips) => {
    if (!showElim && !skips.includes('elim') && esBorrada(d)) return false
    if (!showCron && !skips.includes('cron') && esCron(d)) return false
    if (!skips.includes('tag3') && f.tag3 && d.pilar !== f.tag3) return false
    if (!skips.includes('tag3i') && f.tag3i && d.tag3 !== f.tag3i) return false
    if (!skips.includes('tag1') && f.tag1 && d.tag1 !== f.tag1) return false
    if (!skips.includes('tag2') && f.tag2 && d.tag2 !== f.tag2) return false
    if (!skips.includes('tag4') && f.tag4 && d.tag4 !== f.tag4) return false
    if (!skips.includes('tag5') && f.tag5 && d.tag5 !== f.tag5) return false
    if (!skips.includes('tag6') && f.tag6 && d.tag6 !== f.tag6) return false
    if (!skips.includes('motor') && f.motor && (d.motor || 'Sin dato') !== f.motor) return false
    if (!skips.includes('autor') && f.autor && d.autor !== f.autor) return false
    if (!skips.includes('anio') && f.anio && (d.fecha || '').slice(0, 4) !== f.anio) return false
    if (!skips.includes('mes') && f.mes && d.mes !== f.mes) return false
    if (!skips.includes('sem') && f.sem && d.mes + '|' + d.semana !== f.sem) return false
    if (nums) {
      if (!nums.has(+d.n)) return false
    } else if (qs && !(d._s || '').includes(qs)) {
      return false
    }
    if (f.dia && d.fecha !== f.dia) return false
    if (f.d1 && d.fecha < f.d1) return false
    if (f.d2 && d.fecha > f.d2) return false
    return true
  }

  const visible = useMemo(
    () => sessions.filter((d) => pass(d)),
    [sessions, f, q, nums, qs, showElim, showCron]
  )

  const sorted = useMemo(() => {
    const arr = visible.slice()
    arr.sort((a, b) => {
      if (orden.k === 'tag1') {
        const A = norm((a.tag1 || '') + ' ' + (a.tag2 || ''))
        const B = norm((b.tag1 || '') + ' ' + (b.tag2 || ''))
        if (!a.tag1 && b.tag1) return 1
        if (a.tag1 && !b.tag1) return -1
        return (A > B ? 1 : A < B ? -1 : 0) * (orden.asc ? 1 : -1)
      }
      let x = a[orden.k]
      let y = b[orden.k]
      if (typeof x === 'string') {
        x = norm(x)
        y = norm(y)
      }
      if (x === y) return b.n - a.n
      return (x > y ? 1 : x < y ? -1 : 0) * (orden.asc ? 1 : -1)
    })
    return arr
  }, [visible, orden])

  const facetCounts = (skipKeys, field) => {
    const c = {}
    const allValues = new Set()
    for (const d of sessions) {
      const v = d[field]
      if (v) allValues.add(v)
      if (pass(d, ...skipKeys) && v) {
        c[v] = (c[v] || 0) + 1
      }
    }
    return { c, allValues }
  }

  const totals = useMemo(
    () =>
      visible.reduce(
        (a, d) => ({
          costo: a.costo + (d.costo || 0),
          horas: a.horas + (d.horas || 0),
          posts: a.posts + (d.posts || 0),
          toks: a.toks + (d.tok_tot || d.tok || 0),
        }),
        { costo: 0, horas: 0, posts: 0, toks: 0 }
      ),
    [visible]
  )

  const nElim = useMemo(() => sessions.filter(esBorrada).length, [sessions])
  const nCron = useMemo(() => sessions.filter(esCron).length, [sessions])

  // Active chips list
  const activeChips = useMemo(() => {
    const out = []
    if (f.tag3i) out.push(['tag3i', f.tag3i])
    if (f.tag3) out.push(['tag3', f.tag3])
    if (f.tag1) out.push(['tag1', f.tag1])
    if (f.tag2) out.push(['tag2', f.tag2])
    if (f.tag4) out.push(['tag4', f.tag4])
    if (f.tag5) out.push(['tag5', f.tag5])
    if (f.tag6) out.push(['tag6', f.tag6])
    if (f.motor) out.push(['motor', f.motor])
    if (f.autor) out.push(['autor', f.autor])
    if (f.anio) out.push(['anio', f.anio])
    if (f.mes) out.push(['mes', nombreMes(f.mes, lang)])
    if (f.sem) {
      const [mPart, wPart] = f.sem.split('|')
      out.push(['sem', `${t('semAbbr')} ${(wPart || '').split('-W')[1] || ''} · ${nombreMes(mPart, lang)}`])
    }
    if (q) out.push(['q', `“${q}”`])
    if (f.dia) out.push(['dia', f.dia])
    if (f.d1 || f.d2) out.push(['rango', `${f.d1 || '…'} → ${f.d2 || '…'}`])
    return out
  }, [f, q, lang])

  const removeChip = (k) => {
    if (k === 'q') {
      setQ('')
      return
    }
    if (k === 'rango') {
      setF((p) => ({ ...p, d1: '', d2: '' }))
      return
    }
    if (k === 'anio') {
      setF((p) => ({ ...p, anio: null, mes: null, sem: null }))
      return
    }
    if (k === 'mes') {
      setF((p) => ({ ...p, mes: null, sem: null }))
      return
    }
    setF((p) => ({ ...p, [k]: k === 'dia' ? '' : null }))
  }

  const limpiar = () => {
    setF({
      tag1: null,
      tag2: null,
      tag3i: null,
      tag3: null,
      tag4: null,
      tag5: null,
      tag6: null,
      motor: null,
      autor: null,
      anio: null,
      mes: null,
      sem: null,
      dia: '',
      d1: '',
      d2: '',
    })
    setQ('')
    setOrden({ k: 'fecha', asc: false })
  }

  const copiarResultado = async () => {
    const vis = visible.slice().sort((a, b) => a.n - b.n)
    const txt = vis.map((d) => d.raw + '\t' + d.id).join('\n')
    const ok = await copyText(ctx, txt)
    setBtnMsg((p) => ({ ...p, copia: ok ? `✔ Copiado · ${vis.length}` : '✗ Sin permiso' }))
    setTimeout(() => setBtnMsg((p) => ({ ...p, copia: '' })), 2400)
  }

  const exportarCorrecciones = async () => {
    const vis = visible.slice().sort((a, b) => a.n - b.n)
    const esc = (v) => '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"'
    const head = [
      'n',
      'id',
      'fecha',
      'titulo_actual',
      'sujeto',
      'tag1',
      'tag2',
      'descripcion',
      'verbo',
      'sujeto_nuevo',
      'tag1_nuevo',
      'tag2_nuevo',
      'descripcion_nueva',
      'verbo_nuevo',
      'observaciones',
    ]
    const rows = vis.map((d) =>
      [d.n, d.id, d.fecha, d.raw, d.sujeto, d.tag1, d.tag2, d.desc, d.verb, '', '', '', '', '', '']
        .map(esc)
        .join(',')
    )
    const csv = '\ufeff' + head.join(',') + '\n' + rows.join('\n') + '\n'
    let nExp = 1
    try {
      nExp = (+(localStorage.getItem('mmws-export-count') || 0)) + 1
      localStorage.setItem('mmws-export-count', String(nExp))
    } catch (_) {
      /* ignore */
    }
    const tag = '[' + String(nExp).padStart(4, '0') + ']'
    const now = new Date()
    const z = (x) => String(x).padStart(2, '0')
    const fname = `${tag} ${now.getFullYear()}${z(now.getMonth() + 1)}${z(now.getDate())}_${z(now.getHours())}${z(now.getMinutes())}_${vis.length}sesiones.csv`

    if (ctx && ctx.files && typeof ctx.files.writeText === 'function') {
      try {
        await ctx.files.writeText('data', 'last-export.csv', csv)
      } catch (_) {
        /* ignore */
      }
    }
    try {
      const a = document.createElement('a')
      a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
      a.download = fname
      a.click()
      URL.revokeObjectURL(a.href)
    } catch (_) {
      /* headless test fallback */
    }
    setBtnMsg((p) => ({ ...p, expc: `✔ ${tag} · ${vis.length}` }))
    setTimeout(() => setBtnMsg((p) => ({ ...p, expc: '' })), 3000)
  }

  const fichaTexto = (d) => {
    const k = (v, alt) => (v === undefined || v === null || v === '' ? alt || '—' : v)
    const L = [
      d.raw,
      'sujeto: ' + d.sujeto + ' · ordinal ' + String(d.mmm).padStart(3, '0'),
      'tag1: ' + k(d.tag1) + ' | tag2: ' + k(d.tag2),
      'pilar: ' + k(d.pilar || d.tag3) + ' | país: ' + k(d.pais || d.tag4) + ' | año: ' + k(d.anio || d.tag5),
      'máquina: ' + k(d.tag6),
      'descripción: ' + k(d.desc),
      'fecha: ' + k(d.fecha) + ' · mensajes: ' + k(d.mc) + ' · posts: ' + k(d.posts),
      'costo: ' + fmtC(d.costo) + ' · horas: ' + fmtH(d.horas) + ' · tokens: ' + (d.tok_tot ? Math.round(d.tok_tot / 1000) + 'k' : '—'),
      'motor: ' + k(d.motor) + (d.motor_det ? ' (' + d.motor_det + ')' : '') + ' · autor: ' + k(d.autor) + ' · perfil: ' + k(d.prof),
    ]
    const cl = (d.claves || []).map((x) => String(x).replace(/\s+/g, ' ')).filter((x) => !esRuido(x))
    if (cl.length) {
      L.push('--- mensajes clave del usuario ---')
      cl.slice(0, 6).forEach((x) => L.push('> ' + x.slice(0, 400)))
    } else if (d.resumen && !esRuido(d.resumen)) {
      L.push('--- resumen ---')
      L.push('> ' + String(d.resumen).replace(/\s+/g, ' ').slice(0, 600))
    }
    L.push('id: ' + d.id)
    return L.join('\n')
  }

  const copyCard = async () => {
    if (!sel) return
    const ok = await copyText(ctx, fichaTexto(sel))
    setBtnMsg((p) => ({ ...p, pcopia: ok ? '✔ Copiada' : '✗ Sin permiso' }))
    setTimeout(() => setBtnMsg((p) => ({ ...p, pcopia: '' })), 1800)
  }

  const openSession = (s) => {
    if (!s) return
    const fn = (ctx && ctx.host && ctx.host.openSession) || (host && host.openSession)
    if (typeof fn === 'function') {
      fn(s.id, { profile: s.prof, intent: 'tab' })
    }
  }

  const saveEditedTitle = async () => {
    const v = editVal.trim()
    if (!v || !sel) {
      setEditModal(false)
      return
    }
    sel.raw = v
    const g = parseTitle(v)
    if (g) {
      sel.sujeto = g.subject.trim()
      sel.mmm = parseInt(g.mmm, 10)
      sel.tag1 = (g.tag1 || '').trim()
      sel.tag2 = (g.tag2 || '').trim()
      sel.desc = (g.desc || '').trim()
      sel.verb = (g.verb || '').trim()
    }
    setSel({ ...sel })
    setSessions((prev) => prev.map((x) => (x.id === sel.id ? { ...sel } : x)))
    setEditModal(false)

    // Persist in Hermes state.db via session.resume + session.title
    const res = await callRpc(ctx, 'session.resume', {
      session_id: sel.id,
      profile: sel.prof === 'default' ? undefined : sel.prof,
      lazy: true,
      omit_messages: true,
    })
    if (res && res.session_id) {
      await callRpc(ctx, 'session.title', { session_id: res.session_id, title: v })
    }
  }

  const toggleFold = (b) => {
    setFolded((prev) => {
      const next = new Set(prev)
      if (next.has(b)) next.delete(b)
      else next.add(b)
      return next
    })
  }

  const toggleExpand = (b) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(b)) next.delete(b)
      else next.add(b)
      return next
    })
  }

  const toggleNode = (k) => {
    setOpenNodes((prev) => {
      const next = new Set(prev)
      if (next.has(k)) next.delete(k)
      else next.add(k)
      return next
    })
  }

  // Render a foldable radio facet block (tag1, tag2, tag3i, tag3/pilar)
  const renderFacetBlock = (blockId, labelKey, stateKey, fieldName, sortSpecial) => {
    const isOff = folded.has(blockId)
    const { c, allValues } = facetCounts([stateKey === 'tag3' ? 'tag3' : stateKey === 'tag3i' ? 'tag3i' : stateKey], fieldName)
    const allKeys = [...allValues]
      .filter((k) => k && ((c[k] || 0) > 0 || f[stateKey] === k))
      .sort((a, b) => {
        if (sortSpecial) {
          if (a === 'Temas Varios') return 1
          if (b === 'Temas Varios') return -1
        }
        return (c[b] || 0) - (c[a] || 0)
      })
    const isExp = expanded.has(blockId) || allKeys.indexOf(f[stateKey]) >= 10
    const shown = isExp ? allKeys : allKeys.slice(0, 10)

    return [
      h(
        'h4',
        {
          key: 'hd-' + blockId,
          className: 'fold' + (isOff ? ' off' : ''),
          onClick: () => toggleFold(blockId),
        },
        h('span', { className: 'caret' }, isOff ? '▸' : '▾'),
        h('span', null, blockId + ' · '),
        h('span', null, t(labelKey))
      ),
      !isOff
        ? h(
            'div',
            { key: 'bd-' + blockId },
            shown.length
              ? shown.map((k) =>
                  h(
                    'label',
                    {
                      key: k,
                      className: 'opt' + (f[stateKey] === k ? ' sel' : ''),
                      onClick: (e) => {
                        e.preventDefault()
                        setF((p) => ({ ...p, [stateKey]: p[stateKey] === k ? null : k }))
                      },
                    },
                    h('input', { type: 'radio', checked: f[stateKey] === k, readOnly: true }),
                    h('span', null, k),
                    h('span', { className: 'n' }, c[k] || 0)
                  )
                )
              : h('div', { className: 'opt empty' }, '—'),
            allKeys.length > 10
              ? h(
                  'div',
                  { className: 'more', onClick: () => toggleExpand(blockId) },
                  isExp ? t('Menos') : `+ ${allKeys.length - 10} ${t('Mas')}`
                )
              : null
          )
        : null,
    ]
  }

  // Render Fecha tree (Year -> Month -> Week)
  const renderFechaTree = () => {
    const cMes = {}
    const cSem = {}
    const mesesMap = {}
    for (const d of sessions) {
      if (!d.mes) continue
      mesesMap[d.mes] = mesesMap[d.mes] || {}
      if (d.semana) mesesMap[d.mes][d.semana] = (mesesMap[d.mes][d.semana] || 0) + 1
      if (pass(d, 'anio', 'mes', 'sem')) {
        cMes[d.mes] = (cMes[d.mes] || 0) + 1
        if (d.semana) cSem[d.mes + '|' + d.semana] = (cSem[d.mes + '|' + d.semana] || 0) + 1
      }
    }
    const porAnio = {}
    Object.keys(mesesMap).forEach((m) => {
      const y = m.slice(0, 4)
      ;(porAnio[y] = porAnio[y] || []).push(m)
    })

    return Object.keys(porAnio)
      .sort()
      .reverse()
      .map((y) => {
        const meses = porAnio[y].sort().reverse()
        const totY = meses.reduce((s, m) => s + (cMes[m] || 0), 0)
        if (!totY && f.anio !== y) return null
        const ky = 'y:' + y
        const oy = openNodes.has(ky)
        return h(
          'div',
          { key: ky, className: 'node ynode' + (oy ? ' open' : '') + (f.anio === y ? ' sel' : '') },
          h(
            'div',
            {
              className: 'hd',
              onClick: (e) => {
                if (e.target.classList && e.target.classList.contains('caret')) {
                  toggleNode(ky)
                  return
                }
                const nextAnio = f.anio === y ? null : y
                setF((p) => ({ ...p, anio: nextAnio, mes: nextAnio ? p.mes : null, sem: nextAnio ? p.sem : null }))
                if (nextAnio) setOpenNodes((prev) => new Set([...prev, ky]))
              },
            },
            h('span', { className: 'caret' }, oy ? '▾' : '▸'),
            y,
            h('span', { className: 'n' }, totY)
          ),
          h(
            'div',
            { className: 'bd' },
            h(
              'label',
              {
                className: 'opt' + (f.anio === y && !f.mes ? ' sel' : ''),
                onClick: (e) => {
                  e.preventDefault()
                  const nextAnio = f.anio === y && !f.mes ? null : y
                  setF((p) => ({ ...p, anio: nextAnio, mes: null, sem: null }))
                },
              },
              h('input', { type: 'radio', checked: f.anio === y && !f.mes, readOnly: true }),
              h('span', null, h('b', null, `${t('todoAnio')} ${y}`)),
              h('span', { className: 'n' }, totY)
            ),
            meses.map((m) => {
              const km = 'm:' + m
              const om = openNodes.has(km)
              const nm = cMes[m] || 0
              if (!nm && f.mes !== m) return null
              return h(
                'div',
                { key: km, className: 'node mnode' + (om ? ' open' : '') + (f.mes === m ? ' sel' : '') },
                h(
                  'div',
                  {
                    className: 'hd',
                    onClick: (e) => {
                      if (e.target.classList && e.target.classList.contains('caret')) {
                        toggleNode(km)
                        return
                      }
                      const nextMes = f.mes === m ? null : m
                      setF((p) => ({ ...p, mes: nextMes, anio: nextMes ? m.slice(0, 4) : p.anio, sem: null }))
                      if (nextMes) setOpenNodes((prev) => new Set([...prev, km]))
                    },
                  },
                  h('span', { className: 'caret' }, om ? '▾' : '▸'),
                  nombreMes(m, lang),
                  h('span', { className: 'n' }, nm)
                ),
                h(
                  'div',
                  { className: 'bd' },
                  h(
                    'label',
                    {
                      className: 'opt' + (f.mes === m && !f.sem ? ' sel' : ''),
                      onClick: (e) => {
                        e.preventDefault()
                        const nextMes = f.mes === m && !f.sem ? null : m
                        setF((p) => ({ ...p, mes: nextMes, anio: nextMes ? m.slice(0, 4) : p.anio, sem: null }))
                      },
                    },
                    h('input', { type: 'radio', checked: f.mes === m && !f.sem, readOnly: true }),
                    h('span', null, h('b', null, `${t('todoAnio')} ${nombreMes(m, lang)}`)),
                    h('span', { className: 'n' }, nm)
                  ),
                  Object.keys(mesesMap[m])
                    .sort()
                    .map((w) => {
                      const id = m + '|' + w
                      const mm = cSem[id] || 0
                      if (!mm && f.sem !== id) return null
                      return h(
                        'label',
                        {
                          key: id,
                          className: 'opt' + (f.sem === id ? ' sel' : ''),
                          onClick: (e) => {
                            e.preventDefault()
                            setF((p) => ({ ...p, sem: p.sem === id ? null : id }))
                          },
                        },
                        h('input', { type: 'radio', checked: f.sem === id, readOnly: true }),
                        h(
                          'span',
                          null,
                          h('b', null, (w.split('-W')[1] || w) + ' '),
                          h('span', { style: { color: 'var(--tx3)', fontSize: '10px' } }, t('semAbbr'))
                        ),
                        h('span', { className: 'n' }, mm)
                      )
                    })
                )
              )
            })
          )
        )
      })
  }

  // Motor & Autor facets
  const motorStats = useMemo(() => {
    const cnt = {}
    for (const d of sessions) {
      if (pass(d)) {
        const k = d.motor || 'Sin dato'
        cnt[k] = (cnt[k] || 0) + 1
      }
    }
    const known = ['DeepSeek Flash', 'DeepSeek Pro', 'Claude', 'Gemini', 'Kimi', 'Ornit', 'Qwen', 'Mixta']
    const keys = Object.keys(cnt)
      .filter((k) => (cnt[k] || 0) > 0 || f.motor === k)
      .sort((a, b) => {
        const na = known.indexOf(a) < 0 ? 1 : 0
        const nb = known.indexOf(b) < 0 ? 1 : 0
        return na !== nb ? na - nb : (cnt[b] || 0) - (cnt[a] || 0)
      })
    return { cnt, keys }
  }, [sessions, visible, f.motor])

  const autorStats = useMemo(() => {
    const cnt = {}
    for (const d of sessions) {
      if (pass(d)) {
        const k = d.autor || d.prof || 'default'
        cnt[k] = (cnt[k] || 0) + 1
      }
    }
    const keys = Object.keys(cnt)
      .filter((k) => (cnt[k] || 0) > 0 || f.autor === k)
      .sort((a, b) => (cnt[b] || 0) - (cnt[a] || 0))
    return { cnt, keys }
  }, [sessions, visible, f.autor])

  const hiddenByFilterCount = useMemo(() => {
    if (visible.length > 0 || !qNorm) return 0
    return sessions.filter((d) =>
      norm([d.desc, d.tema, d.sujeto, d.tag1, d.tag2, d.pilar, d.n].join(' ')).includes(qNorm)
    ).length
  }, [visible.length, qNorm, sessions])

  const sortCol = (k, isNum = false) => {
    setOrden((p) => (p.k === k ? { k, asc: !p.asc } : { k, asc: !isNum }))
  }

  // Build two-line rows matching simulator_template.html
  const tableRows = sorted.flatMap((d) => {
    const cut = d.raw.lastIndexOf(']')
    const head = (cut > 0 ? d.raw.slice(0, cut + 1) : `[${d.sujeto}] ${String(d.mmm).padStart(3, '0')}`).replace(
      /^\d+\s+/,
      ''
    )
    const tail = cut > 0 ? d.raw.slice(cut + 1).trim() : d.desc
    const isDel = /borrad/i.test(d.sujeto) || esBorrada(d)
    const isSel = Boolean(sel && sel.id === d.id)

    return [
      h(
        'tr',
        {
          className: 't',
          key: d.id + '-t',
          onClick: () => selectSession(d),
        },
        h('td', { className: 'ncol t' }, d.n),
        h(
          'td',
          { colSpan: 6, className: 'ttitle' + (isDel ? ' borrada' : '') },
          h('b', { className: 'tfac' }, head),
          tail ? h('b', { className: 'tdesc' }, ' ' + tail) : null
        )
      ),
      h(
        'tr',
        {
          className: 'r' + (isSel ? ' sele' : ''),
          key: d.id + '-r',
          onClick: () => selectSession(d),
        },
        h('td', { className: 'ncol' }),
        h('td', { className: 'mono tight fecha' }, d.fecha),
        h(
          'td',
          { className: 'tight' },
          h(
            'span',
            {
              className: 'pill s pick' + (isDel ? ' del' : ''),
              title: 'Filtrar por este sujeto',
              onClick: (e) => {
                e.stopPropagation()
                setQ(d.sujeto)
                setSel(null)
              },
            },
            d.sujeto
          ),
          ' ',
          h('span', { className: 'mono', style: { color: 'var(--tx3)' } }, String(d.mmm || 1).padStart(3, '0')),
          d.tag1
            ? h(
                'span',
                {
                  className: 'pill tag1 pick',
                  style: { marginLeft: '4px' },
                  title: 'Filtrar por tag1',
                  onClick: (e) => {
                    e.stopPropagation()
                    setF((p) => ({ ...p, tag1: p.tag1 === d.tag1 ? null : d.tag1 }))
                    setSel(null)
                  },
                },
                d.tag1
              )
            : null,
          d.tag2
            ? h(
                'span',
                {
                  className: 'pill tag2 pick',
                  style: { marginLeft: '4px' },
                  title: 'Filtrar por tag2',
                  onClick: (e) => {
                    e.stopPropagation()
                    setF((p) => ({ ...p, tag2: p.tag2 === d.tag2 ? null : d.tag2 }))
                    setSel(null)
                  },
                },
                d.tag2
              )
            : null
        ),
        h('td', { className: 'num tight cen' }, fmtC(d.costo)),
        h('td', { className: 'num tight cen' }, fmtH(d.horas)),
        h('td', { className: 'num tight cen', style: { color: 'var(--tx3)' } }, fmtT(d.tok_tot)),
        h('td', { className: 'num tight cen', style: { color: 'var(--tx3)' } }, fmtP(d.posts))
      ),
    ]
  })

  const selClaves = sel ? (sel.claves || []).map((x) => String(x)).filter((x) => !esRuido(x)) : []

  return h(
    'div',
    { className: 'mmws' + (sinFiltros ? ' sinFiltros' : '') },
    h('style', null, CSS),

    /* ---------- Header ---------- */
    h(
      'header',
      { className: 'top' },
      h(
        'div',
        { className: 'brandrow' },
        h('h1', null, NAME),
        h(
          'span',
          { className: 'sub' },
          h('b', null, loading ? '—' : sessions.length),
          ' sesiones · NNN [Sujeto] MMM [Tag1] [Tag2] Descripción · Verbo'
        ),
        h(
          'button',
          {
            className: 'ghost langsw',
            onClick: toggleLang,
            title: 'Idioma de la interfaz · Interface language',
          },
          h('span', { className: lang === 'es' ? 'on' : '' }, 'ES'),
          h('span', { className: lang === 'en' ? 'on' : '' }, 'EN')
        )
      )
    ),

    /* ---------- Body (Aside + Main + Slide-over Detail Panel) ---------- */
    h(
      'div',
      { className: 'bodywrap' },

      /* Left Filters Aside */
      h(
        'aside',
        null,
        h('input', {
          type: 'text',
          placeholder: t('buscar'),
          value: q,
          onChange: (e) => setQ(e.target.value),
          style: {
            width: '100%',
            background: '#100d13',
            border: '1px solid var(--line2)',
            color: 'var(--tx)',
            borderRadius: '6px',
            padding: '5px 8px',
            fontSize: '12.5px',
          },
        }),
        renderFacetBlock('tag1', 'tag1', 'tag1', 'tag1', false),
        renderFacetBlock('tag2', 'tag2', 'tag2', 'tag2', false),
        renderFacetBlock('tag3', 'tag3', 'tag3i', 'tag3', false),
        renderFacetBlock('tag4', 'tema', 'tag3', 'pilar', true),

        h('h4', null, t('fecha')),
        h('div', null, renderFechaTree()),

        h('h4', null, t('diaExacto')),
        h('input', {
          type: 'date',
          value: f.dia,
          onChange: (e) => setF((p) => ({ ...p, dia: e.target.value })),
          style: {
            width: '100%',
            background: '#100d13',
            border: '1px solid var(--line2)',
            color: 'var(--tx)',
            borderRadius: '6px',
            padding: '5px 8px',
            fontSize: '12.5px',
          },
        }),

        h('h4', null, t('rango')),
        h(
          'div',
          { style: { display: 'flex', gap: '6px' } },
          h('input', {
            type: 'date',
            value: f.d1,
            onChange: (e) => setF((p) => ({ ...p, d1: e.target.value })),
            style: {
              flex: 1,
              background: '#100d13',
              border: '1px solid var(--line2)',
              color: 'var(--tx)',
              borderRadius: '6px',
              padding: '4px',
              fontSize: '11.5px',
            },
          }),
          h('input', {
            type: 'date',
            value: f.d2,
            onChange: (e) => setF((p) => ({ ...p, d2: e.target.value })),
            style: {
              flex: 1,
              background: '#100d13',
              border: '1px solid var(--line2)',
              color: 'var(--tx)',
              borderRadius: '6px',
              padding: '4px',
              fontSize: '11.5px',
            },
          })
        ),

        h(
          'h4',
          null,
          h('span', null, t('motor')),
          h('span', null, (f.motor ? t('de1') : '') + motorStats.keys.length + ' ' + t('motores'))
        ),
        h(
          'div',
          null,
          motorStats.keys.map((k) =>
            h(
              'label',
              {
                key: k,
                className: 'opt' + (f.motor === k ? ' sel' : '') + (k === 'Sin dato' ? ' empty' : ''),
                onClick: (e) => {
                  e.preventDefault()
                  setF((p) => ({ ...p, motor: p.motor === k ? null : k }))
                },
              },
              h('input', { type: 'radio', checked: f.motor === k, readOnly: true }),
              h('span', null, k),
              h('span', { className: 'n' }, motorStats.cnt[k])
            )
          )
        ),

        h(
          'h4',
          null,
          h('span', null, t('autor')),
          h('span', null, (f.autor ? t('de1') : '') + autorStats.keys.length + ' ' + t('autores'))
        ),
        h(
          'div',
          null,
          autorStats.keys.map((k) =>
            h(
              'label',
              {
                key: k,
                className: 'opt' + (f.autor === k ? ' sel' : ''),
                onClick: (e) => {
                  e.preventDefault()
                  setF((p) => ({ ...p, autor: p.autor === k ? null : k }))
                },
              },
              h('input', { type: 'radio', checked: f.autor === k, readOnly: true }),
              h('span', null, k),
              h('span', { className: 'n' }, autorStats.cnt[k])
            )
          )
        ),

        h('p', { className: 'hint' }, t('hintUnica'))
      ),

      /* Main Session List */
      h(
        'main',
        {
          onClick: (e) => {
            if (sel && !e.target.closest('tr.t') && !e.target.closest('tr.r')) {
              setSel(null)
            }
          },
        },
        h(
          'div',
          { className: 'toolbar' },
          h(
            'div',
            { className: 'trow' },
            h(
              'button',
              {
                onClick: () => setSinFiltros((v) => !v),
                title: 'Mostrar u ocultar los filtros',
              },
              '☰ Filtros'
            ),
            h('span', { className: 'sub', style: { fontSize: '11.5px' } }, t('ordenar')),
            h(
              'button',
              { className: orden.k === 'n' ? 'on' : '', onClick: () => sortCol('n', true) },
              t('colN')
            ),
            h(
              'button',
              { className: orden.k === 'costo' ? 'on' : '', onClick: () => sortCol('costo', true) },
              t('colCosto')
            ),
            h(
              'button',
              { className: orden.k === 'horas' ? 'on' : '', onClick: () => sortCol('horas', true) },
              t('colHoras')
            ),
            h(
              'button',
              { className: orden.k === 'fecha' ? 'on' : '', onClick: () => sortCol('fecha', true) },
              t('colFecha')
            ),
            h('span', { style: { flex: 1, minWidth: 0 } }),
            h(
              'span',
              { className: 'counter' },
              t('mostrando') + ' ',
              h('b', null, visible.length),
              ' ' + t('de') + ' ',
              h('b', null, sessions.length),
              hiddenByFilterCount > 0
                ? [
                    ' · ',
                    h(
                      'span',
                      { key: 'qh', className: 'qhint' },
                      `${hiddenByFilterCount} ${t('ocultasFiltro')}`
                    ),
                    h(
                      'button',
                      {
                        key: 'qs',
                        className: 'qshow',
                        onClick: () =>
                          setF({
                            tag1: null,
                            tag2: null,
                            tag3i: null,
                            tag3: null,
                            tag4: null,
                            tag5: null,
                            tag6: null,
                            motor: null,
                            autor: null,
                            anio: null,
                            mes: null,
                            sem: null,
                            dia: '',
                            d1: '',
                            d2: '',
                          }),
                      },
                      t('ver')
                    ),
                  ]
                : null
            ),
            h(
              'button',
              {
                className: showElim ? 'on' : '',
                onClick: () => setShowElim((v) => !v),
              },
              (showElim ? t('hideDel') : t('showDel')) + ' · ' + nElim
            ),
            h(
              'button',
              {
                className: showCron ? 'on' : '',
                onClick: () => setShowCron((v) => !v),
              },
              (showCron ? t('hideCron') : t('showCron')) + ' · ' + nCron
            )
          ),
          h(
            'div',
            { className: 'chips' },
            h(
              'button',
              {
                className: 'clrbtn primary' + (activeChips.length ? '' : ' ghost'),
                disabled: !activeChips.length,
                onClick: limpiar,
              },
              t('limpiar')
            ),
            h(
              'button',
              { className: 'ghost', onClick: copiarResultado },
              btnMsg.copia || `${t('copiar')} · ${visible.length}`
            ),
            h(
              'button',
              { className: 'ghost', onClick: exportarCorrecciones },
              btnMsg.expc || `${t('exportar')} · ${visible.length}`
            ),
            h(
              'button',
              { className: 'ghost', onClick: () => refreshData(true) },
              btnMsg.updb || t('actualizar')
            ),
            h(
              'span',
              { className: 'chipwrap' },
              activeChips.map(([k, val]) =>
                h(
                  'span',
                  { key: k, className: 'chip' },
                  val,
                  ' ',
                  h('b', { onClick: () => removeChip(k) }, '✕')
                )
              )
            )
          )
        ),

        h(
          'table',
          { id: 'tb' },
          h(
            'thead',
            null,
            h(
              'tr',
              null,
              h('th', { className: 'tight', onClick: () => sortCol('n', true) }, t('colN')),
              h('th', { className: 'tight fecha', onClick: () => sortCol('fecha', true) }, t('colFecha')),
              h('th', { className: 'tight', onClick: () => sortCol('sujeto', false) }, t('colSujeto')),
              h('th', { className: 'tight', onClick: () => sortCol('costo', true) }, t('colCosto')),
              h('th', { className: 'tight', onClick: () => sortCol('horas', true) }, t('colHoras')),
              h('th', { className: 'tight', onClick: () => sortCol('tok_tot', true) }, t('colTokens')),
              h('th', { className: 'tight', onClick: () => sortCol('posts', true) }, t('colPosts'))
            )
          ),
          h('tbody', null, tableRows)
        )
      ),

      /* Slide-over Detail Card Panel */
      h(
        'div',
        { className: 'panel' + (sel ? ' on' : '') },
        h(
          'div',
          { className: 'pbar' },
          h(
            'span',
            { className: 'x', onClick: () => setSel(null) },
            '✕'
          )
        ),
        sel
          ? h(
              'div',
              { className: 'pbody' },
              h('div', { className: 'pname' }, sel.raw),
              h('h3', { className: 'ptitle' }, sel.desc),
              sel.resumen && !esRuido(sel.resumen) ? h('p', { className: 'psum' }, sel.resumen) : null,
              h(
                'div',
                { className: 'kv' },
                h('div', null, t('sujeto')),
                h('div', null, h('b', null, sel.sujeto), ' · ' + String(sel.mmm || 1).padStart(3, '0')),
                h('div', { style: { gridColumn: '1/-1', borderTop: '1px solid var(--line)', margin: '6px 0 2px' } }),
                h('div', null, 'tag1 · ' + t('lblPlataforma')),
                h('div', null, h('span', { className: 'pill tag1' }, sel.tag1 || '—')),
                h('div', null, 'tag2 · ' + t('lblFamilia')),
                h('div', null, h('span', { className: 'pill tag2' }, sel.tag2 || '—')),
                h('div', null, 'tag3 · ' + t('lblPilar')),
                h('div', null, h('span', { className: 'pill tag3' }, sel.pilar || sel.tag3 || '—')),
                h('div', null, 'tag4 · ' + t('lblPais')),
                h('div', null, sel.pais || sel.tag4 ? h('span', { className: 'pill tag4' }, sel.pais || sel.tag4) : '—'),
                h('div', null, 'tag5 · ' + t('lblAnio')),
                h('div', null, sel.anio || sel.tag5 ? h('span', { className: 'pill tag5' }, sel.anio || sel.tag5) : '—'),
                h('div', null, 'tag6 · ' + t('lblMaquina')),
                h('div', null, h('span', { className: 'pill tag6' }, sel.tag6 || '—')),
                h('div', null, 'tag7 · ' + t('lblLibre')),
                h('div', null, sel.tag7 || '—'),
                h('div', null, 'tag8 · ' + t('lblLibre')),
                h('div', null, sel.tag8 || '—'),
                h('div', null, 'tag9 · ' + t('lblLibre')),
                h('div', null, sel.tag9 || '—'),
                h('div', { style: { gridColumn: '1/-1', borderTop: '1px solid var(--line)', margin: '6px 0 2px' } }),
                h('div', null, 'Ruta'),
                h('div', null, `${sel.dom || 'Software'} › ${sel.tag5 || '—'} › ${sel.tag1 || '—'}`),
                h('div', null, t('costo')),
                h('div', null, fmtC(sel.costo)),
                h('div', null, t('horas')),
                h('div', null, fmtH(sel.horas)),
                h('div', null, 'Mensajes'),
                h('div', null, sel.mc),
                h('div', null, t('fecha')),
                h('div', null, sel.fecha),
                h('div', null, t('motor')),
                h('div', null, sel.motor || '—'),
                h('div', null, t('autor')),
                h('div', null, sel.autor || '—'),
                h('div', null, t('perfil')),
                h('div', null, sel.prof)
              ),
              h('h4', { style: { marginTop: '14px' } }, t('mensajes')),
              h(
                'ul',
                { className: 'klist' },
                (selClaves.length ? selClaves : [t('sinMensajes')]).map((c, i) => h('li', { key: i }, c))
              ),
              h(
                'div',
                { className: 'why' },
                h('b', null, 'ADN de la sesión: '),
                'sujeto ',
                h('b', null, sel.sujeto),
                ' · tag1 ',
                h('b', null, sel.tag1 || '—'),
                ' (plataforma) · tag2 ',
                h('b', null, sel.tag2 || '—'),
                ' (familia de trabajo) · pilar ',
                h('b', null, sel.pilar || '—'),
                ' · máquina ',
                h('b', null, sel.tag6 || '—'),
                '. Solo tag1 y tag2 aparecen en el nombre; el resto son filtros.'
              ),
              h(
                'button',
                {
                  style: { marginTop: '6px' },
                  onClick: () => {
                    setEditVal(sel.raw)
                    setEditModal(true)
                  },
                },
                t('editarBtn')
              ),
              h(
                'div',
                { className: 'pidfoot' },
                h('span', null, 'id'),
                (sel.prof && sel.prof !== 'default' ? `· perfil ${sel.prof} · ` : '') + sel.id
              )
            )
          : h('div', { className: 'pbody' }, t('elegir')),
        h(
          'div',
          { className: 'pbar bottom' },
          h('button', { onClick: copyCard }, btnMsg.pcopia || t('copiarSesion')),
          h('button', { className: 'openbtn', onClick: () => openSession(sel) }, t('abrirSesion'))
        )
      )
    ),

    /* ---------- Bottom Footer Row (Version Badge + 5 KPIs) ---------- */
    h(
      'div',
      { className: 'footrow' },
      h(
        'div',
        {
          className: 'vbadge',
          onClick: () => setVModal(true),
          title: 'Ficha del plugin',
        },
        h('i', null),
        'V ',
        h('b', null, '0.23')
      ),
      h(
        'div',
        { className: 'kbar' },
        h(
          'div',
          { className: 'kpi accent' },
          h('b', null, visible.length),
          h('div', { className: 'lb' }, h('i', null, t('kSes1')), h('i', null, t('kSes2')))
        ),
        h(
          'div',
          { className: 'kpi good' },
          h('b', null, '$' + totals.costo.toFixed(2)),
          h('div', { className: 'lb' }, h('i', null, t('kCos1')), h('i', null, t('kCos2')))
        ),
        h(
          'div',
          { className: 'kpi gold' },
          h('b', null, Math.round(totals.horas / 60) + ' h'),
          h('div', { className: 'lb' }, h('i', null, t('kHor1')), h('i', null, t('kHor2')))
        ),
        h(
          'div',
          { className: 'kpi pst' },
          h('b', null, fmtP(totals.posts)),
          h('div', { className: 'lb' }, h('i', null, t('kPost1')), h('i', null, t('kPost2')))
        ),
        h(
          'div',
          { className: 'kpi tok' },
          h('b', null, fmtT(totals.toks)),
          h('div', { className: 'lb' }, h('i', null, t('kTok1')), h('i', null, t('kTok2')))
        )
      )
    ),

    /* ---------- Edit Title Modal ---------- */
    editModal
      ? h(
          'div',
          {
            className: 'modal',
            onClick: (e) => {
              if (e.target.classList && e.target.classList.contains('modal')) setEditModal(false)
            },
          },
          h(
            'div',
            { className: 'box' },
            h('h4', { style: { fontSize: '12px', marginBottom: '8px' } }, t('editarTit')),
            h('input', {
              value: editVal,
              onChange: (e) => setEditVal(e.target.value),
            }),
            h('p', { className: 'hint' }, t('editarHint')),
            h(
              'div',
              { className: 'row' },
              h('button', { onClick: () => setEditModal(false) }, t('cancelar')),
              h('button', { className: 'openbtn', onClick: saveEditedTitle }, t('guardar'))
            )
          )
        )
      : null,

    /* ---------- Version Modal ---------- */
    vModal
      ? h(
          'div',
          {
            className: 'modal',
            onClick: (e) => {
              if (e.target.classList && e.target.classList.contains('modal')) setVModal(false)
            },
          },
          h(
            'div',
            { className: 'box', style: { maxWidth: '520px' } },
            h(
              'div',
              { style: { display: 'flex', alignItems: 'baseline', gap: '10px', marginBottom: '12px' } },
              h('h4', { style: { fontSize: '13px', margin: 0, color: 'var(--tx)' } }, NAME),
              h('span', { className: 'mono', style: { fontSize: '11px', color: '#c9a8f0' } }, t('vSub'))
            ),
            h('p', { style: { fontSize: '12px', color: 'var(--tx2)', margin: '0 0 12px', lineHeight: 1.55 } }, t('vIntro')),
            h(
              'div',
              { style: { borderTop: '1px solid var(--line)', paddingTop: '10px' } },
              h('div', { className: 'mono', style: { fontSize: '9.5px', letterSpacing: '.1em', color: 'var(--tx3)', marginBottom: '6px' } }, t('vVer')),
              h(
                'ul',
                { style: { fontSize: '11.5px', lineHeight: 1.65, margin: '0 0 12px', paddingLeft: '18px', color: 'var(--tx2)' } },
                ['v1', 'v2', 'v3', 'v4', 'v5', 'v6', 'v7', 'v8', 'v9'].map((k) =>
                  h('li', { key: k, dangerouslySetInnerHTML: { __html: t(k) } })
                )
              ),
              h('div', { className: 'mono', style: { fontSize: '9.5px', letterSpacing: '.1em', color: 'var(--tx3)', marginBottom: '6px' } }, t('vReg')),
              h(
                'ul',
                { style: { fontSize: '11.5px', lineHeight: 1.65, margin: 0, paddingLeft: '18px', color: 'var(--tx2)' } },
                ['r1', 'r2', 'r3', 'r4'].map((k) => h('li', { key: k }, t(k)))
              )
            ),
            h(
              'div',
              { className: 'row' },
              h('button', { className: 'bok', onClick: () => setVModal(false) }, t('vCerrar'))
            )
          )
        )
      : null
  )
}

// Named exports so tests/test_plugin.mjs can exercise the pure helpers without React.
export { numSel, fmtC, fmtH, fmtN, loadCatalogue }

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
