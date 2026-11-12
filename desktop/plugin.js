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
 * Visual & behavioral UI (docs/SPEC-UI.md).
 * Loaded uncompiled by Hermes Desktop: only `@hermes/plugin-sdk`, `react`, and
 * `react/jsx-runtime` are imported.
 */

import { host, ROUTES_AREA, SIDEBAR_NAV_AREA } from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'
import { useState, useEffect, useMemo, useRef } from 'react'

const ID = 'make-it-smart'
const NAME = 'Hermes, Make it Smart!'
const APP_TITLE = 'Make It Smart'
const VERSION = '0.25.0'
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

/** Duration formatter: supports '—' for <=0 and days ('Xd Yh') for >=1440 min. */
const fmtHoras = (v) => {
  const m = Math.round(Number(v) || 0)
  if (m <= 0) return '—'
  if (m >= 1440) {
    const d = Math.floor(m / 1440)
    const h = Math.floor((m % 1440) / 60)
    return h ? d + 'd ' + h + 'h' : d + 'd'
  }
  return m < 60
    ? m + 'm'
    : m % 60 < 5
      ? Math.floor(m / 60) + 'h'
      : Math.floor(m / 60) + 'h' + String(m % 60).padStart(2, '0') + 'm'
}

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

// The canonical Bot Chat's name IS its identity, and a subagent transcript is
// machinery, not work: neither is renamed, and neither counts as a pending change.
const esBotChat = (d) => Boolean(d && /^\s*bot chat\b/i.test(String(d.raw || '')))

const esSubagent = (d) =>
  Boolean(
    d &&
      (/^\s*subagent[\s:]/i.test(String(d.raw || '')) ||
        /^subagent/i.test(String(d.prof || '')) ||
        /^subagent/i.test(String(d.id || '')))
  )

/** Anything the renamer must never touch: cron, empty, deleted, Bot Chat, subagent. */
const esIntocable = (d) => Boolean(d && (esCron(d) || d.vacia || esBorrada(d) || esBotChat(d) || esSubagent(d)))

/* Bilingual synonym table */
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

function canonicalTitle(d) {
  if (!d) return ''
  if (esIntocable(d)) return d.raw || ''

  const nnn = String(Number(d.n) || 0).padStart(3, '0')
  const subj = (d.sujeto || d.tag0 || '').trim() || 'Sin sujeto'
  const mmm = String(Number(d.mmm) || 1).padStart(3, '0')

  let head = `${nnn} [${subj}] ${mmm}`
  const t1 = (d.tag1 || '').trim()
  const t2 = (d.tag2 || '').trim()
  if (t1) head += ` [${t1}]`
  if (t2) head += ` [${t2}]`

  if (head.length >= 100) {
    return head.slice(0, 100).trimEnd()
  }

  const verb = (d.verb || '').trim()
  const tail = verb ? ` · ${verb}` : ''
  const budget = 100 - head.length - 1 - tail.length

  let desc = (d.desc || '').trim()
  if (desc && budget > 0) {
    if (desc.length > budget) {
      desc = desc.slice(0, budget).trimEnd()
    }
    return `${head} ${desc}${tail}`.trim()
  }
  if (tail && head.length + tail.length + 1 <= 100) {
    return `${head}${tail}`.trim()
  }
  return head
}

function getBackupStamp(date = new Date()) {
  const z = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}${z(date.getMonth() + 1)}${z(date.getDate())}_${z(date.getHours())}${z(date.getMinutes())}`
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
  const [, mm] = m.split('-')
  const arr = MESNOM[lang] || MESNOM.es
  return arr[parseInt(mm, 10) - 1] || mm
}

/* ------------------------------------------------------------------ */
/* I18N dictionary (1:1 with 2026-11-11_simulador-solo-codigo.html)   */
/* ------------------------------------------------------------------ */

const I18N = {
  es: {
    navPrev: 'Sesión anterior',
    navNext: 'Sesión siguiente',
    tabInfo: 'Sesión',
    tabInfoTitle: 'Abrir la ficha de la primera sesión de la lista',
    mostrarLbl: 'Mostrar:',
    ordenar: 'Ordenar:',
    limpiar: 'Limpiar',
    copiar: 'Copiar',
    exportar: 'Exportar',
    actualizar: 'Actualizar BD',
    showDel: 'Borradas',
    hideDel: 'Borradas',
    showCron: 'Cron',
    hideCron: 'Cron',
    showVacio: 'Vacío',
    hideVacio: 'Vacío',
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
    colPending: 'Pendientes',
    pendMemTitulo: 'Pending Authorization IDs — Memory',
    pendSklTitulo: 'Pending Authorization IDs — Skills',
    pendHuerfanas: 'Sin sesión atribuible',
    pendFacet: 'Pendientes',
    pendFacetCount: 'con pendientes',
    sujetoFacet: 'tag0 · Sujeto',
    sujetosCount: 'sujetos',
    copyIds: '⧉ Copiar IDs',
    kPend1: 'PENDIENTES',
    kPend2: 'AUTORIZ',
    kPendTitle: 'Filtrar sesiones con solicitudes de autorización pendientes',
    mostrando: 'Mostrando',
    de: 'de',
    copiarSesion: 'Copiar sesión',
    abrirSesion: 'Abrir sesión',
    mensajes: 'MENSAJES CLAVE DEL USUARIO',
    mensajesLbl: 'Mensajes',
    sinMensajes: '(sin mensajes de usuario útiles en esta sesión)',
    elegir: 'Elige una sesión para ver su ficha.',
    sujeto: 'Sujeto',
    costo: 'Costo',
    horas: 'Horas',
    tokens: 'Tokens',
    perfil: 'Perfil',
    pais: 'País',
    anio: 'Año',
    ruta: 'Ruta',
    descripcion: 'descripción',
    adn: 'ADN de la sesión:',
    adnNota: 'Solo tag1 y tag2 aparecen en el nombre; el resto son filtros.',
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
    lblProyecto: 'Proyecto',
    kHor1: 'Horas',
    kHor2: 'trabajo',
    kPost1: 'Total',
    kPost2: 'posts',
    kTok1: 'Total',
    kTok2: 'tokens',
    sinMsgs: '(sin mensajes de usuario en esta sesión)',
    hintUnica: 'Selección única por faceta. Los filtros se combinan entre sí.',
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
    vacio: 'Vacío',
    vacioTitle: 'Ocultar las sesiones sin ningún mensaje (las muestra al desactivarlo)',
    avTit: 'Sesiones vacías de cron:',
    avCuerpo:
      '{n} sesiones creadas por cron jobs no tienen ni un mensaje. No es un fallo tuyo: es un bug conocido de Hermes, <a href="https://github.com/NousResearch/hermes-agent/issues/140222" target="_blank" rel="noopener">issue #140222</a>.',
    avActivos: '{n} cron jobs activos',
    avConsejo:
      'Dirección de la solución: pausar esos cron jobs y volver a crearlos en modo no_agent (sin LLM, sin sesión). Este panel no toca tus cron jobs: pídeselo a tu agente de Hermes.',
    avCopiar: 'Copiar mensaje para Lisa',
    avCopiado: 'Copiado',
    avTexto:
      'Lisa, tengo {n} sesiones vacías de cron (source=cron sin ningún mensaje). Bórralas y dime qué cron jobs tengo activos para pausarlos o pasarlos a modo no_agent.',
    vIntro:
      'Catálogo navegable de tus sesiones: las indexa de las 12 bases, les pone nombre canónico y las deja filtrar por plataforma, familia y pilar. La ventana del plugin solo pinta — el clasificador es Python puro y no sabe que existe Hermes.',
    vSub: 'v0.25 · plugin nativo',
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
    tabActual: 'Actual Hermes DB Sessions',
    tabActualTitle: 'Sesiones reales de la base de datos de Hermes (solo lectura)',
    tabTesting: 'Testing',
    tabTestingTitle: 'Simulación de nomenclatura canónica y herramientas de commit/revert',
    commitBtn: 'Commit Changes to Hermes DB',
    commitBtnTitle: 'Escribe los títulos canónicos simulados en state.db vía session.title',
    revertBtn: 'Revert',
    revertBtnTitle: 'Restaura los títulos anteriores desde el último backup',
    updateBtn: 'New Rules Update',
    updateBtnTitle: 'Relee index.json y facets.json, recalcula la simulación e informa cambios',
    infoPluginTitle: 'Ver información y reglas aprendidas del plugin Make It Smart',
    confirmCommit: '¿Aplicar {n} cambios de título en tu base de sesiones de Hermes?',
    confirmRevert: '¿Revertir {n} títulos a su estado anterior al último commit?',
    commitProgress: 'Commit {current}/{total}',
    commitDone: '{n} actualizados · {m} sin cambios',
    revertDone: '{n} títulos restaurados',
    updateDone: '{count} sesiones cambiarían con las reglas actuales',
    updateCount: '{count} cambiarían',
    updateClean: 'Todo al día · 0 cambios',
    updateStale: 'El índice tiene más de 24 h y está desactualizado; pídele a Hermes: reindexa el catálogo del plugin',
  },
  en: {
    navPrev: 'Previous session',
    navNext: 'Next session',
    tabInfo: 'Session',
    tabInfoTitle: 'Open the card of the first session in the list',
    mostrarLbl: 'Show:',
    ordenar: 'Sort:',
    limpiar: 'Clear',
    copiar: 'Copy',
    exportar: 'Export',
    actualizar: 'Refresh DB',
    showDel: 'Deleted',
    hideDel: 'Deleted',
    showCron: 'Cron',
    hideCron: 'Cron',
    showVacio: 'Empty',
    hideVacio: 'Empty',
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
    colPending: 'Pending',
    pendMemTitulo: 'Pending Authorization IDs — Memory',
    pendSklTitulo: 'Pending Authorization IDs — Skills',
    pendHuerfanas: 'Unattributed',
    pendFacet: 'Pending',
    pendFacetCount: 'with pending',
    sujetoFacet: 'tag0 · Subject',
    sujetosCount: 'subjects',
    copyIds: '⧉ Copy IDs',
    kPend1: 'PENDING',
    kPend2: 'AUTH',
    kPendTitle: 'Filter sessions with pending authorization requests',
    mostrando: 'Showing',
    de: 'of',
    copiarSesion: 'Copy session',
    abrirSesion: 'Open session',
    mensajes: 'KEY USER MESSAGES',
    mensajesLbl: 'Messages',
    sinMensajes: '(no useful user messages in this session)',
    elegir: 'Pick a session to see its card.',
    sujeto: 'Subject',
    costo: 'Cost',
    horas: 'Hours',
    tokens: 'Tokens',
    perfil: 'Profile',
    pais: 'Country',
    anio: 'Year',
    ruta: 'Path',
    descripcion: 'description',
    adn: 'Session DNA:',
    adnNota: 'Only tag1 and tag2 appear in the name; the rest are filters.',
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
    lblProyecto: 'Project',
    kHor1: 'Work',
    kHor2: 'hours',
    kPost1: 'Total',
    kPost2: 'posts',
    kTok1: 'Total',
    kTok2: 'tokens',
    sinMsgs: '(no user messages in this session)',
    hintUnica: 'Single selection per facet. Filters combine with each other.',
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
    vacio: 'Empty',
    vacioTitle: 'Hide sessions with no messages (turn it off to show them)',
    avTit: 'Cron sessions with no messages:',
    avCuerpo:
      '{n} sessions created by cron jobs have no messages at all. Not your fault: it is a known Hermes bug, <a href="https://github.com/NousResearch/hermes-agent/issues/140222" target="_blank" rel="noopener">issue #140222</a>.',
    avActivos: '{n} active cron jobs',
    avConsejo:
      'Where the fix goes: pause those cron jobs and recreate them in no_agent mode (no LLM, no session). This panel does not touch your cron jobs — ask your Hermes agent to do it.',
    avCopiar: 'Copy message for Lisa',
    avCopiado: 'Copied',
    avTexto:
      'Lisa, I have {n} empty cron sessions (source=cron with no messages). Delete them and tell me which cron jobs are active so I can pause them or move them to no_agent mode.',
    vIntro:
      'A browsable catalogue of your sessions: it indexes them from the 12 databases, gives each a canonical name and lets you filter by platform, family and pillar. The plugin window only paints — the classifier is pure Python and does not know Hermes exists.',
    vSub: 'v0.25 · native plugin',
    vVer: 'THIS VERSION',
    vReg: 'REGLAS QUE APRENDIÓ',
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
    tabActual: 'Actual Hermes DB Sessions',
    tabActualTitle: 'Actual sessions from Hermes database (read-only)',
    tabTesting: 'Testing',
    tabTestingTitle: 'Canonical nomenclature simulation and commit/revert tools',
    commitBtn: 'Commit Changes to Hermes DB',
    commitBtnTitle: 'Write simulated canonical titles to state.db via session.title',
    revertBtn: 'Revert',
    revertBtnTitle: 'Restore previous titles from the last backup',
    updateBtn: 'New Rules Update',
    updateBtnTitle: 'Re-read index.json and facets.json, recalculate simulation and report changes',
    infoPluginTitle: 'View plugin information and learned rules for Make It Smart',
    confirmCommit: 'Apply {n} title changes to your Hermes session database?',
    confirmRevert: 'Revert {n} titles back to their state before the last commit?',
    commitProgress: 'Commit {current}/{total}',
    commitDone: '{n} updated · {m} unchanged',
    revertDone: '{n} titles restored',
    updateDone: '{count} sessions would change with current rules',
    updateCount: '{count} would change',
    updateClean: 'All up to date · 0 changes',
    updateStale: 'The index is older than 24h and stale; ask Hermes: rebuild plugin catalog',
  },
}

/* ------------------------------------------------------------------ */
/* Scoped CSS (1:1 from 2026-11-11_simulador-solo-codigo.html)        */
/* ------------------------------------------------------------------ */

const CSS = `
.mmws{--tabw:62px;--tabx:16px;--kbar-h:33px;--aside-ef:264px;--bg:#0d0b0e;--bg2:#141117;--card:#17131a;--line:#2a2330;--line2:#3a3040;--tx:#eae4ee;--tx2:#b9aec4;--tx3:#857a92;--wine:#a3234a;--wine2:#d94f78;--gold:#c9a227;--ok:#3f9e6a;
position:relative;display:flex;flex-direction:column;width:100%;height:100%;min-height:0;overflow:hidden;background:var(--bg);color:var(--tx);font:14px/1.55 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",sans-serif}
.mmws *{box-sizing:border-box}
.mmws h1{font-size:12.5px;margin:0;letter-spacing:.01em;font-weight:800;color:var(--tx);cursor:pointer;transition:color .12s}
.mmws h1:hover{color:var(--wine2)}
.mmws h4{margin:13px 0 5px;font-size:9.5px;text-transform:uppercase;letter-spacing:.08em;color:var(--tx3);display:flex;justify-content:space-between;align-items:center;gap:4px;flex-wrap:wrap}
.mmws h4 span{font-weight:400;text-transform:none;letter-spacing:0;color:var(--tx3);font-size:9.5px}
.mmws .sub{color:var(--tx2);font-size:12.5px}
.mmws .mono{font-family:ui-monospace,Menlo,monospace;font-size:12px}
.mmws header.top{flex:0 0 auto;z-index:40;background:linear-gradient(180deg,#100d12,#0d0b0e);border-bottom:1px solid var(--line);padding:10px 18px}
.mmws .brandrow{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.mmws .headtabs{display:inline-flex;align-items:flex-end;gap:2px;background:transparent;border:0;border-bottom:1px solid var(--line2);border-radius:0;padding:0;margin-left:10px}
.mmws .headtab{position:relative;border:0;border-bottom:2px solid transparent;background:transparent;color:var(--tx3);font-size:11.5px;font-weight:600;padding:6px 16px 5px;border-radius:6px 6px 0 0;cursor:pointer;display:inline-flex;align-items:center;gap:6px;margin-bottom:-1px;transition:color .12s,background .12s,border-color .12s}
/* Cada pestaña lleva su color a los lados, como una pestaña de ventana:
   verde la base real, amarillo la simulación. */
.mmws .headtab::before,.mmws .headtab::after{content:'';position:absolute;top:5px;bottom:-1px;width:2px;border-radius:1px;opacity:.4;transition:opacity .12s,background .12s}
.mmws .headtab::before{left:0}
.mmws .headtab::after{right:0}
.mmws .headtab:first-child::before,.mmws .headtab:first-child::after{background:var(--ok)}
.mmws .headtab:last-child::before,.mmws .headtab:last-child::after{background:var(--gold)}
.mmws .headtab:hover{color:var(--tx);background:rgba(255,255,255,.04)}
.mmws .headtab:hover::before,.mmws .headtab:hover::after{opacity:.75}
.mmws .headtab.on{background:transparent;color:#fff;border-bottom-color:var(--ok);box-shadow:none}
.mmws .headtab.on::before,.mmws .headtab.on::after{opacity:1}
.mmws .headtab.on.testing{background:transparent;color:var(--gold);border-bottom-color:var(--gold)}
.mmws .headtab.on.testing::before,.mmws .headtab.on.testing::after{background:var(--gold);opacity:1}
.mmws .bodywrap{flex:1 1 auto;min-height:0;display:flex;align-items:stretch;position:relative;overflow:hidden}
.mmws .abarra{flex:none;padding:9px 0 8px;background:var(--bg2);border-bottom:1px solid var(--line);z-index:2}
.mmws .ascroll{flex:1 1 auto;min-height:0;overflow-y:auto;overflow-x:hidden;padding:8px 0 14px;scrollbar-width:none;-ms-overflow-style:none;overscroll-behavior:contain}
.mmws .ascroll::-webkit-scrollbar{display:none;width:0;height:0}
.mmws aside{width:var(--aside-ef);flex:0 0 var(--aside-ef);height:100%;display:flex;flex-direction:column;overflow:hidden;border-right:1px solid var(--line);background:var(--bg2);padding:0 10px}
.mmws aside::-webkit-scrollbar{display:none;width:0;height:0}
.mmws main{flex:1 1 auto;min-width:0;height:100%;overflow-y:auto;overflow-x:hidden;padding:0 0 40px}
.mmws #tabInfo{position:absolute;right:0;top:0;bottom:0;width:44px;display:flex;align-items:center;justify-content:center;writing-mode:vertical-rl;text-orientation:mixed;background:#191420;border:0;border-left:1px solid var(--line);border-bottom:1px solid var(--line);border-radius:0 0 0 6px;color:var(--tx3);font-size:9.5px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;cursor:pointer;padding:8px 4px;white-space:normal;line-height:1.1;text-align:center;z-index:45}
.mmws #tabInfo:hover{background:#241c2e;color:#fff}
.mmws #tabInfo:active{background:#2d2338}
.mmws .toolbar{position:sticky;top:0;z-index:30;background:rgba(13,11,14,.98);backdrop-filter:blur(6px);border-bottom:1px solid var(--line);padding:8px 54px 7px 16px;display:flex;gap:8px;row-gap:6px;align-items:center;flex-wrap:wrap}
.mmws .counter{font-size:12.5px;color:var(--tx2);flex:0 0 auto;white-space:nowrap}
.mmws .counter b{color:#fff}
.mmws .trow{display:flex;flex-wrap:nowrap;align-items:center;gap:6px;width:100%;min-width:0;overflow:hidden}
.mmws .trow>button{flex:0 0 auto;white-space:nowrap}
.mmws #acciones{display:flex;gap:6px;align-items:center;flex:0 0 auto;min-width:0}
.mmws #acciones>button{flex:0 0 auto;white-space:nowrap}
.mmws button{font:inherit;font-size:12px;cursor:pointer;border-radius:6px;border:1px solid var(--line2);background:#1d1822;color:var(--tx2);padding:3px 8px;white-space:nowrap}
.mmws button:hover{border-color:var(--wine);color:#fff}
.mmws button.on{background:var(--wine);border-color:var(--wine);color:#fff}
.mmws .chipsrow{display:flex;align-items:center;gap:10px;margin-top:2px;flex:1 0 100%;width:100%}
.mmws .chips{display:flex;gap:6px;flex-wrap:wrap;align-items:center;flex:1 1 auto;min-height:28px;justify-content:flex-start}
.mmws .chipsrow .counter{margin-left:auto;flex:0 0 auto}
.mmws .chipwrap{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-left:0}
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
.mmws .qshow,#qshow{font-size:10.5px;padding:1px 7px;border-radius:5px;background:#2a2110;border:1px solid #4a3a12;color:#f0b529;cursor:pointer;margin-left:4px}
.mmws .qshow:hover,#qshow:hover{background:#3a2c14;color:#ffd166}
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
.mmws .aviso{display:flex;gap:10px;align-items:flex-start;flex-wrap:wrap;margin:8px 16px 10px;padding:9px 12px;border-radius:8px;background:#2a1d0c;border:1px solid #6b4a12;color:#f0d9a8;font-size:12.3px;line-height:1.45}
.mmws .aviso[hidden]{display:none}
.mmws .aviso b{color:#ffcf70}
.mmws .aviso .acc{margin-left:auto;display:flex;gap:6px;align-items:center}
.mmws .aviso button{background:#3a2a0e;border:1px solid #7a5716;color:#ffe1a0;border-radius:6px;padding:4px 9px;font-size:11.5px;cursor:pointer}
.mmws .aviso button:hover{background:#4a3612}
.mmws .aviso a{color:#ffd98a;text-underline-offset:2px}
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
.mmws #tb th:nth-child(8){width:64px;text-align:center}
.mmws #tb th:nth-child(1),.mmws #tb td.ncol{padding:6px 0;text-align:center;white-space:nowrap;width:48px}
.mmws td.fecha{padding-left:8px !important;text-align:left !important;color:var(--tx3)}
.mmws #tb td.ttitle{padding:6px 8px 2px 0;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:10.5px;line-height:1.45;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;border-bottom:none !important;color:#f4e6ee;font-weight:700}
.mmws tr.t{cursor:pointer}
.mmws tr.t.sele{background:#251521;box-shadow:inset 3px 0 0 var(--wine2)}
.mmws tr.t td.ncol.t{font-family:ui-monospace,Menlo,monospace;font-size:10.5px;line-height:1.45;font-weight:700;color:#f4e6ee;border-bottom:none !important;vertical-align:baseline}
.mmws tr.t .ttitle .tfac{color:#f4e6ee;font-weight:700}
.mmws tr.t .ttitle .tdesc{color:#f4e6ee;font-weight:700;letter-spacing:.005em}
.mmws tr.t:hover .ttitle .tfac{color:var(--tx2)}
.mmws tr.t .ttitle.borrada .tdesc{text-decoration:line-through;text-decoration-color:rgba(217,79,120,.65);text-decoration-thickness:1px}
.mmws tr.r{cursor:pointer}
.mmws tr.r:hover{background:#1b1620}
.mmws tr.r.sele{background:#1b1420}
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
.mmws .pbar{padding:9px 16px;border-bottom:1px solid var(--line);display:flex;gap:8px;align-items:center;justify-content:space-between;background:#100d12}
.mmws .pbar.bottom{border-bottom:none;border-top:1px solid var(--line);justify-content:flex-start}
.mmws .pbar-l{display:flex;gap:6px;align-items:center}
.mmws .pbar button{font-size:10.5px;padding:3px 8px;border-radius:6px;border:1px solid var(--line2);background:#1c1721;color:var(--tx2);cursor:pointer}
.mmws .pbar button:hover{filter:brightness(1.35);border-color:var(--wine2)}
.mmws .pbar .x{cursor:pointer;color:var(--tx3);font-size:16px}
.mmws .openbtn{background:var(--wine);border:1px solid var(--wine);color:#fff;border-radius:6px;padding:3px 8px;font-size:11px;font-weight:600;cursor:pointer}
.mmws .pendsec{grid-column:1/-1;margin:10px 0 4px}
.mmws .pendhead{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.mmws .pendtitle{font-size:11px;font-weight:700;color:#d8ec8f;text-transform:uppercase;letter-spacing:.05em;margin:0}
.mmws .pendbtn{font-size:10.5px;padding:2px 7px;border-radius:5px;border:1px solid var(--line2);background:#1c1721;color:var(--tx2);cursor:pointer}
.mmws .pendbtn:disabled{opacity:.4;cursor:default}
.mmws .pendbox{max-height:140px;overflow-y:auto;overflow-x:hidden;background:#0d0a10;border:1px solid var(--line);border-radius:6px;padding:6px 8px;scrollbar-width:thin}
.mmws .penditem{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:10.5px;line-height:1.45;color:var(--tx2);cursor:default}
.mmws .penditem:hover{color:#fff}
.mmws .pendempty{color:var(--tx3);font-size:11.5px;padding:4px 0}
.mmws .pendorph{grid-column:1/-1;margin:10px 0 4px;border-top:1px dashed var(--line);padding-top:8px}
.mmws .pendorphtog{font-size:11px;font-weight:600;color:var(--tx3);cursor:pointer;display:flex;align-items:center;gap:4px}
.mmws .pendorphtog:hover{color:var(--tx2)}
.mmws .pname{font-family:ui-monospace,Menlo,monospace;font-size:17px;color:#f0dbe4;background:#1d1420;border:1px solid #3a2030;border-radius:8px;padding:9px 11px;margin:0 0 10px;line-height:1.5;word-break:break-word}
.mmws .pthead{display:flex;align-items:flex-start;gap:10px;margin:0 0 10px}
.mmws .pthead .pname{flex:1 1 auto;min-width:0;margin:0;overflow:hidden;text-overflow:ellipsis}
.mmws .pnaveg{flex:0 0 26px;width:26px;display:flex;flex-direction:column;gap:3px;justify-content:flex-start;padding-top:9px}
.mmws .navb{width:26px;height:22px;padding:0;font-size:9.5px;line-height:1;border-radius:5px;border:1px solid var(--line2);background:#1c1721;color:var(--tx2);cursor:pointer}
.mmws .navb:hover:not(:disabled){filter:brightness(1.45);border-color:var(--wine2)}
.mmws .navb:disabled{opacity:.28;cursor:default}
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
.mmws .footrow{flex:0 0 var(--kbar-h);height:var(--kbar-h);display:flex;align-items:stretch;justify-content:space-between;z-index:60;background:#0f0c13d9;backdrop-filter:blur(8px);border-top:1px solid var(--line2)}
.mmws .footbtns{display:flex;align-items:center;gap:8px;padding:0 12px;flex:0 0 auto}
.mmws .footbtns button{height:24px;padding:1px 10px;font-size:11px;font-weight:600;border-radius:5px;cursor:pointer;white-space:nowrap;display:inline-flex;align-items:center;gap:6px;transition:filter .12s,background .12s}
.mmws .commitbtn{background:var(--wine);border:1px solid var(--wine);color:#fff}
.mmws .commitbtn:hover:not(:disabled){background:var(--wine2);border-color:var(--wine2)}
.mmws .commitbtn:disabled{opacity:.5;cursor:default}
.mmws .revertbtn{background:var(--ok);border:1px solid var(--ok);color:#fff}
.mmws .revertbtn:hover:not(:disabled){filter:brightness(1.18)}
.mmws .revertbtn:disabled{opacity:.5;cursor:default}
.mmws .updatebtn{background:#1d1822;border:1px solid var(--line2);color:var(--tx2)}
.mmws .updatebtn:hover:not(:disabled){border-color:var(--wine);color:#fff}
.mmws .updatebtn:disabled{opacity:.5;cursor:default}
.mmws .footmsg{font-size:11px;color:var(--tx2);margin-left:6px;white-space:nowrap}
.mmws .kbar{flex:1 1 auto;display:flex;align-items:stretch;justify-content:flex-end;gap:0;padding:0 4px}
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
.mmws .kbar .kpi.pend b{color:#d8ec8f}
.mmws .kbar .kpi.clickable{cursor:pointer;user-select:none}
.mmws .kbar .kpi.clickable:hover{background:#1a1422}
.mmws .kbar .kpi.active{background:#231728;box-shadow:inset 0 -2px 0 var(--wine2)}
.mmws .hint{font-size:11px;color:var(--tx3);margin:6px 0 0}
.mmws .modal{position:fixed;inset:0;background:#000a;display:flex;align-items:center;justify-content:center;z-index:90}
.mmws .modal .box{background:#17131a;border:1px solid var(--line2);border-radius:12px;padding:18px;width:min(580px,92vw);max-height:85vh;overflow:auto}
.mmws .modal input{width:100%;background:#100d13;border:1px solid var(--line2);color:var(--tx);border-radius:7px;padding:8px 10px;font-size:13px;font-family:ui-monospace,Menlo,monospace}
.mmws .modal .row{display:flex;gap:8px;justify-content:flex-end;margin-top:12px}
.mmws button.bok{margin-left:auto;background:#2a1a3d;border-color:#6b4a9e;color:#e8dde4}
.mmws button.bok:hover{background:#38234f;border-color:#8f6bc4}
.mmws .errbanner{background:#2b1118;border-bottom:1px solid #8c2d3e;color:#ffd4dc;padding:7px 14px;font-size:12px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.mmws .errbanner b{color:#ff7a90;font-family:ui-monospace,Menlo,monospace}
.mmws .errbanner .errlist{flex:1 1 auto;display:flex;flex-direction:column;gap:2px;font-family:ui-monospace,Menlo,monospace;font-size:11.5px}
`

/* ------------------------------------------------------------------ */
/* Gateway RPC & File Bridge                                          */
/* ------------------------------------------------------------------ */

async function callRpc(ctx, method, params, errors) {
  const req = (ctx && ctx.host && ctx.host.request) || (host && host.request)
  if (typeof req !== 'function') {
    if (Array.isArray(errors)) {
      errors.push({ method, message: 'host.request no está disponible en @hermes/plugin-sdk ni en ctx.host' })
    }
    return null
  }
  try {
    const res = await req(method, params || {})
    return res && typeof res === 'object' ? res : null
  } catch (err) {
    const msg = (err && (err.message || err.code || String(err))) || 'Error RPC desconocido'
    try {
      console.error('[make-it-smart] RPC error:', method, params, err)
    } catch (_) {
      /* ignore console error */
    }
    if (Array.isArray(errors)) {
      errors.push({ method, message: String(msg) })
    }
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
 * Fetch real sessions from Hermes Desktop via:
 * 1) `ctx.files.readText('data', 'index.json' | 'facets.json')`
 * 2) `profiles.list` + `host.listPersistedSessions` (`/api/profiles/sessions`)
 * 3) `host.request('session.list', { limit: 200, scope: 'stored', include_hidden: true })`
 * recording any RPC/HTTP/file errors for visible diagnostic display in the UI.
 */
async function loadCatalogue(ctx) {
  const errors = []
  let idxData = null
  let facetsMap = {}
  let pendData = null
  let pendMap = null
  let pendAttr = null

  const filesApi = (ctx && ctx.files) || (host && host.files)
  if (filesApi && typeof filesApi.readText === 'function') {
    try {
      const [idxRes, facRes, pendRes] = await Promise.all([
        filesApi.readText('data', 'index.json').catch((e) => ({ ok: false, error: String((e && e.message) || e) })),
        filesApi.readText('data', 'facets.json').catch((e) => ({ ok: false, error: String((e && e.message) || e) })),
        filesApi.readText('data', 'pending_index.json').catch((e) => ({ ok: false, error: String((e && e.message) || e) })),
      ])
      if (idxRes && idxRes.ok && idxRes.text) {
        try {
          idxData = JSON.parse(idxRes.text)
        } catch (e) {
          errors.push({ method: 'JSON.parse(index.json)', message: String((e && e.message) || e) })
        }
      } else {
        const err = (idxRes && (idxRes.error || idxRes.message)) || 'no se pudo leer index.json'
        errors.push({ method: "files.readText('data','index.json')", message: String(err) })
      }
      if (facRes && facRes.ok && facRes.text) {
        try {
          facetsMap = JSON.parse(facRes.text)
        } catch (e) {
          errors.push({ method: 'JSON.parse(facets.json)', message: String((e && e.message) || e) })
        }
      }
      if (pendRes && pendRes.ok && pendRes.text) {
        try {
          pendData = JSON.parse(pendRes.text)
          pendMap = (pendData && pendData.by_session) || null
          pendAttr = (pendData && pendData.attribution) || null
        } catch (e) {
          errors.push({ method: 'JSON.parse(pending_index.json)', message: String((e && e.message) || e) })
        }
      }
    } catch (e) {
      errors.push({ method: 'files.readText', message: String((e && e.message) || e) })
    }
  } else {
    errors.push({ method: 'files.readText', message: 'API files.readText no disponible' })
  }

  const idxById = new Map()
  if (idxData && Array.isArray(idxData.sessions)) {
    for (const s of idxData.sessions) {
      if (s && s.id) idxById.set(s.id, s)
    }
  }

  // 1. Discover profiles via host.request('profiles.list')
  const profNames = new Set(['default'])
  const profRpcErrors = []
  const profRes = await callRpc(ctx, 'profiles.list', { include_sessions: false }, profRpcErrors)
  if (profRes && Array.isArray(profRes.profiles)) {
    for (const p of profRes.profiles) {
      if (p && p.name) profNames.add(String(p.name))
    }
  } else {
    const profListFn =
      (ctx && ctx.host && ctx.host.profiles && ctx.host.profiles.list) ||
      (host && host.profiles && host.profiles.list)
    if (typeof profListFn === 'function') {
      try {
        const list = await profListFn()
        if (Array.isArray(list)) list.forEach((p) => p && p.name && profNames.add(String(p.name)))
      } catch (e) {
        errors.push({ method: 'host.profiles.list', message: String((e && e.message) || e) })
      }
    } else if (profRpcErrors.length && idxById.size === 0) {
      errors.push(...profRpcErrors)
    }
  }

  const liveById = new Map()

  // 2. Query persisted sessions across all profiles in state.db via SDK host.listPersistedSessions
  const listPersistedFn =
    (ctx && ctx.host && ctx.host.listPersistedSessions) || (host && host.listPersistedSessions)

  if (typeof listPersistedFn === 'function') {
    await Promise.all(
      [...profNames].map(async (prof) => {
        try {
          const rows = await listPersistedFn(null, { profile: prof, limit: 500 })
          if (Array.isArray(rows)) {
            for (const row of rows) {
              if (row && row.id && !liveById.has(row.id)) {
                liveById.set(row.id, { ...row, _prof: row.profile || prof })
              }
            }
          }
        } catch (e) {
          errors.push({
            method: `host.listPersistedSessions(${prof})`,
            message: String((e && e.message) || e),
          })
        }
      })
    )
  }

  // 3. Query active gateway session.list with valid session_controls.py parameters (limit <= 200, scope: 'stored', no sibling profile)
  const sessRpcErrors = []
  const resStored = await callRpc(
    ctx,
    'session.list',
    { limit: 200, scope: 'stored', include_hidden: true },
    sessRpcErrors
  )
  if (resStored && Array.isArray(resStored.sessions)) {
    for (const row of resStored.sessions) {
      if (row && row.id && !liveById.has(row.id)) {
        liveById.set(row.id, { ...row, _prof: row.profile || 'default' })
      }
    }
  } else if (sessRpcErrors.length && liveById.size === 0 && idxById.size === 0) {
    errors.push(...sessRpcErrors)
  }

  // 4. Also query remote profile routes via host.profileRoutes() + host.requestProfile() with valid limit <= 200
  const routesFn = (ctx && ctx.host && ctx.host.profileRoutes) || (host && host.profileRoutes)
  const reqProfFn = (ctx && ctx.host && ctx.host.requestProfile) || (host && host.requestProfile)
  if (typeof routesFn === 'function' && typeof reqProfFn === 'function') {
    try {
      const routes = (await routesFn()) || []
      await Promise.all(
        routes.map(async (rt) => {
          try {
            const r = await reqProfFn(rt, 'session.list', {
              limit: 200,
              scope: 'stored',
              include_hidden: true,
            })
            if (r && Array.isArray(r.sessions)) {
              for (const row of r.sessions) {
                if (row && row.id && !liveById.has(row.id)) {
                  liveById.set(row.id, { ...row, _prof: (rt && rt.profile) || 'remote' })
                }
              }
            }
          } catch (_) {
            /* skip unreachable remote route */
          }
        })
      )
    } catch (_) {
      /* ignore */
    }
  }

  if (liveById.size === 0 && idxById.size === 0 && errors.length === 0) {
    errors.push({
      method: 'loadCatalogue',
      message: 'No se recibieron sesiones de index.json, /api/profiles/sessions ni session.list.',
    })
  }

  // 5. Use the index as the authoritative source of rows (importing is not filtering: 910 rows).
  // Live gateway listing is used to check for live runtime and enrich runtime metrics (duration, costs).
  const hasIndex = Boolean(idxData && Array.isArray(idxData.sessions) && idxData.sessions.length > 0)
  const sessionList = hasIndex ? idxData.sessions : [...liveById.values()]
  const merged = []

  for (const item of sessionList) {
    const id = item && item.id
    if (!id) continue
    const idx = hasIndex ? item : (idxById.get(id) || {})
    const live = liveById.get(id)
    const ex = facetsMap[id] || {}
    const isLive = Boolean(live)

    // The live gateway title is the truth. index.json is a snapshot: if a commit
    // is written after it was built, idx.raw still holds the pre-commit title and
    // the session reappears as pending forever. Prefer the live title.
    const rawTitle = String((live && live.title) || idx.raw || '').trim()
    const g = parseTitle(rawTitle)

    const fecha = String(idx.fecha || toFecha(live && live.started_at, '')).slice(0, 10)
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
    // A title that already parsed as canonical must never become its own
    // description: '925 [Sin título] 001' came out as
    // '925 [Sin título] 001 925 [Sin título] 001' on the next commit.
    const desc = (
      (g && g.desc) ||
      idx.desc ||
      (live && live.preview) ||
      (g ? '' : rawTitle) ||
      ''
    ).trim()
    const verb = ((g && g.verb) || idx.verb || '').trim()
    const prof = (live && (live._prof || live.profile)) || idx.prof || 'default'
    const mc = Number((live && (live.live_message_count || live.message_count)) || ex.mc || idx.mc || idx.posts || 0)
    const posts = Number(idx.posts || (mc > 0 ? Math.max(1, Math.round(mc / 2)) : 0))
    const liveTok =
      (Number(live && live.input_tokens) || 0) +
      (Number(live && live.output_tokens) || 0) +
      (Number(live && live.cache_read_tokens) || 0) +
      (Number(live && live.cache_write_tokens) || 0) +
      (Number(live && live.reasoning_tokens) || 0)
    const tok = Number(idx.tok_tot || idx.tok || liveTok || 0)
    const liveCost = Number((live && (live.actual_cost_usd != null ? live.actual_cost_usd : live.estimated_cost_usd)) || 0)
    const costo = Number(idx.costo != null && idx.costo > 0 ? idx.costo : (liveCost || idx.costo || 0))
    const liveEnd = live && (live.ended_at || live.last_activity_at || live.last_active)
    const liveMin =
      live && live.started_at && liveEnd && liveEnd > live.started_at
        ? Math.min(480, Math.max(1, Math.round((liveEnd - live.started_at) / 60)))
        : 0
    const horas = Number(idx.horas || liveMin || 0)
    const motor = (ex.motor || idx.motor || (live && live.model) || '').trim()
    const autor = (idx.autor || (prof === 'default' ? 'Lisa' : prof)).trim()
    const claves = Array.isArray(idx.claves) ? idx.claves : []
    const resumen = idx.resumen || (claves[0] || (live && live.preview) || '')

    const pnd = (pendMap && pendMap[id]) || null
    const pendMem = pnd ? (pnd.memoria || []) : []
    const pendSkl = pnd ? (pnd.skills || []) : []
    const pendTot = pendMem.length + pendSkl.length

    merged.push({
      n: g ? parseInt(g.nnn, 10) : Number(idx.n || 0),
      mmm: g ? parseInt(g.mmm, 10) : Number(idx.mmm || 1),
      sujeto,
      tag0: sujeto,
      tag1,
      tag2,
      tag3,
      tag4,
      tag5,
      tag6,
      tag7: ex.tag7 || idx.tag7 || '',
      tag8: ex.tag8 || idx.tag8 || '',
      tag9: pendTot > 0 ? 'Pending' : (ex.tag9 || idx.tag9 || ''),
      pendMem,
      pendSkl,
      pendTot,
      pending: pendTot,
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
      vacia: Boolean(idx.vacia != null ? idx.vacia : mc <= 0 && (!claves || claves.length === 0)),
      esCron: Boolean(idx.esCron || /^cron[_-]/i.test(id) || /^cron[_-]/i.test(prof)),
      _canonical: Boolean(g),
      isLive,
      runtimeVivo: isLive,
      vivo: isLive,
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

  // A commit written after index.json was built leaves idx.raw holding the old
  // title. For sessions the gateway no longer lists live, the commit ledger
  // records what was actually written, so it stands in for the live title.
  if (filesApi && typeof filesApi.readText === 'function') {
    try {
      const ledRes = await filesApi.readText('data', 'commit-last.json')
      if (ledRes && ledRes.ok && ledRes.text) {
        const led = JSON.parse(ledRes.text)
        if (led && led.committed && !led.reverted && Array.isArray(led.entries)) {
          const written = new Map(led.entries.map((e) => [e.id, e.title_after]))
          for (const d of merged) {
            if (!d.vivo && written.has(d.id)) d.raw = written.get(d.id)
          }
        }
      }
    } catch (_) {
      /* a missing or broken ledger is not fatal */
    }
  }

  // Compute canonical simulated title and search synonym index per row once
  for (const d of merged) {
    d.canonTitle = canonicalTitle(d)
    d._s = sin([d.raw, d.canonTitle, d.desc, d.resumen, d.tema, d.sujeto, d.tag1, d.tag2, d.pilar, d.n, d.id].join(' '))
  }

  const vaciasCron = merged.filter((d) => esCron(d) && d.vacia).length
  const jobsActivos = Number((idxData && idxData.cron_info && idxData.cron_info.jobs_activos) || 0)

  const canonicalCount = merged.filter((d) => d._canonical).length
  return {
    sessions: merged,
    total: merged.length,
    canonicalCount,
    newCount: merged.length - canonicalCount,
    fromLiveRpc: liveById.size > 0,
    cronInfo: { vacias: vaciasCron, jobs_activos: jobsActivos },
    errors,
    pendData,
    pendMap,
    pendAttr,
  }
}

/* ------------------------------------------------------------------ */
/* Main React Component                                               */
/* ------------------------------------------------------------------ */

function App({ ctx }) {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [rpcErrors, setRpcErrors] = useState([])
  const [cronInfo, setCronInfo] = useState({ vacias: 0, jobs_activos: 0 })
  const [pendData, setPendData] = useState(null)
  const [pendMap, setPendMap] = useState(null)
  const [pendAttr, setPendAttr] = useState(null)
  const [expandSujetos, setExpandSujetos] = useState(false)
  const [openOrphans, setOpenOrphans] = useState(false)
  const [q, setQ] = useState('')
  const [f, setF] = useState({
    tag1: null,
    tag2: null,
    tag3i: null,
    tag3: null,
    tag4: null,
    tag5: null,
    tag6: null,
    tag8: null,
    tag9: null,
    sujeto: null,
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
  const [showVacio, setShowVacio] = useState(false)
  const [showCron, setShowCron] = useState(false)
  const [orden, setOrden] = useState({ k: 'fecha', asc: false })
  const [sel, setSel] = useState(null)
  const [editModal, setEditModal] = useState(false)
  const [editVal, setEditVal] = useState('')
  const [vModal, setVModal] = useState(false)
  // The panel always opens on the real session database. Testing is a deliberate
  // step the user takes to preview a rename, so it is never restored on open.
  const [activeTab, setActiveTab] = useState('actual')
  const [lastBackup, setLastBackup] = useState(null)
  const [canRevert, setCanRevert] = useState(false)
  const [isCommitting, setIsCommitting] = useState(false)
  const [isReverting, setIsReverting] = useState(false)
  const [staleNotice, setStaleNotice] = useState('')
  const [btnMsg, setBtnMsg] = useState({
    copia: '',
    expc: '',
    updb: '',
    pcopia: '',
    avcopia: '',
    pendMem: '',
    pendSkl: '',
    pendOrph: '',
    commit: '',
    revert: '',
    update: '',
    foot: '',
  })
  const [lang, setLang] = useState(() => {
    try {
      // English is the plugin's default language; Spanish is the opt-in.
      return localStorage.getItem('mmws-lang') === 'es' ? 'es' : 'en'
    } catch (_) {
      return 'en'
    }
  })

  const t = (k, vars) => {
    let s = (I18N[lang] && I18N[lang][k]) || k
    if (vars && typeof vars === 'object') {
      for (const [key, val] of Object.entries(vars)) {
        s = s.replaceAll('{' + key + '}', String(val))
      }
    }
    return s
  }

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
    setCronInfo(res.cronInfo || { vacias: 0, jobs_activos: 0 })
    setRpcErrors(Array.isArray(res.errors) ? res.errors : [])
    setPendData(res.pendData || null)
    setPendMap(res.pendMap || null)
    setPendAttr(res.pendAttr || null)
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
    const run = async () => {
      try {
        const res = await loadCatalogue(ctx)
        if (!alive) return
        setSessions(res.sessions)
        setCronInfo(res.cronInfo || { vacias: 0, jobs_activos: 0 })
        setRpcErrors(Array.isArray(res.errors) ? res.errors : [])
        setPendData(res.pendData || null)
        setPendMap(res.pendMap || null)
        setPendAttr(res.pendAttr || null)
        const years = [...new Set(res.sessions.map((d) => (d.mes || '').slice(0, 4)).filter(Boolean))].sort().reverse()
        if (years.length) {
          setOpenNodes(new Set(['y:' + years[0], 'init:' + years[0]]))
        }
        const filesApi = (ctx && ctx.files) || (host && host.files)
        if (filesApi && typeof filesApi.readText === 'function') {
          try {
            const lastRes = await filesApi.readText('data', 'commit-last.json')
            if (lastRes && lastRes.ok && lastRes.text) {
              const lastData = JSON.parse(lastRes.text)
              if (lastData && typeof lastData === 'object') {
                setLastBackup(lastData)
                if (lastData.committed && !lastData.reverted && lastData.changedCount > 0) {
                  setCanRevert(true)
                }
              }
            }
          } catch (_) {}
        }
      } catch (err) {
        if (!alive) return
        setRpcErrors([{ method: 'loadCatalogue', message: String((err && err.message) || err) }])
      } finally {
        if (alive) setLoading(false)
      }
    }
    run()

    const gw =
      (ctx && ctx.host && ctx.host.state && ctx.host.state.gateway) ||
      (host && host.state && host.state.gateway)
    let unsub = null
    if (gw && typeof gw.subscribe === 'function') {
      try {
        unsub = gw.subscribe((st) => {
          if (alive && st === 'open') run()
        })
      } catch (_) {
        /* ignore */
      }
    }
    return () => {
      alive = false
      if (typeof unsub === 'function') {
        try {
          unsub()
        } catch (_) {
          /* ignore */
        }
      }
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
  const selectSession = async (d, keepOpen = false) => {
    if (!keepOpen && sel && sel.id === d.id) {
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

  // Mutually exclusive state filter: Borradas | Vacío | Cron
  const setEstado = (cual) => {
    const yaActivo =
      (cual === 'elim' && showElim) ||
      (cual === 'vacio' && showVacio) ||
      (cual === 'cron' && showCron)
    setShowElim(!yaActivo && cual === 'elim')
    setShowVacio(!yaActivo && cual === 'vacio')
    setShowCron(!yaActivo && cual === 'cron')
  }

  const copyPendingIds = async (ids, key) => {
    if (!ids || !ids.length) return
    const ok = await copyText(ctx, ids.join('\n'))
    setBtnMsg((p) => ({ ...p, [key]: ok ? `✔ ${ids.length}` : '✗' }))
    setTimeout(() => setBtnMsg((p) => ({ ...p, [key]: '' })), 2000)
  }

  const getAttrTooltip = (pid) => {
    const att = pendAttr && pendAttr[pid]
    const m = att ? att.method : 'orphan'
    if (m === 'exact') {
      return lang === 'en'
        ? "Exact: found in this session's tool result"
        : 'Exacta: está en el resultado de herramienta de esta sesión'
    }
    if (m === 'window') {
      return lang === 'en'
        ? 'Approximate: session active within ±120 s'
        : 'Aproximada: sesión activa en ±120 s'
    }
    if (m === 'window_amb') {
      const n = (att && att.candidates ? att.candidates.length : 0) + 1
      return lang === 'en'
        ? `Approximate — ${n} sessions nearby, closest chosen`
        : `Aproximada — ${n} sesiones cercanas, se eligió la más próxima`
    }
    return lang === 'en'
      ? 'No session could be attributed'
      : 'No se pudo atribuir a una sesión'
  }

  const orphanIds = useMemo(() => {
    if (!pendAttr) return []
    return Object.keys(pendAttr).filter((id) => pendAttr[id] && pendAttr[id].method === 'orphan')
  }, [pendAttr])

  const nums = useMemo(() => numSel(q), [q])
  const qs = useMemo(() => (nums ? '' : sin(q)), [q, nums])
  const qNorm = useMemo(() => norm(q), [q])

  const pass = (d, ...skips) => {
    const modo = showElim ? 'elim' : showVacio ? 'vacio' : showCron ? 'cron' : null
    if (!skips.includes('estado')) {
      if (modo === 'elim') {
        if (!esBorrada(d)) return false
      } else if (modo === 'vacio') {
        if (!d.vacia) return false
      } else if (modo === 'cron') {
        if (!esCron(d)) return false
      } else {
        if (!skips.includes('elim') && esBorrada(d)) return false
        if (!skips.includes('cron') && esCron(d)) return false
        if (!skips.includes('vacio') && d.vacia) return false
      }
    }
    if (!skips.includes('tag3') && f.tag3 && d.pilar !== f.tag3) return false
    if (!skips.includes('tag3i') && f.tag3i && d.tag3 !== f.tag3i) return false
    if (!skips.includes('tag1') && f.tag1 && d.tag1 !== f.tag1) return false
    if (!skips.includes('tag2') && f.tag2 && d.tag2 !== f.tag2) return false
    if (!skips.includes('tag4') && f.tag4 && d.tag4 !== f.tag4) return false
    if (!skips.includes('tag5') && f.tag5 && d.tag5 !== f.tag5) return false
    if (!skips.includes('tag6') && f.tag6 && d.tag6 !== f.tag6) return false
    if (!skips.includes('tag8') && f.tag8 && d.tag8 !== f.tag8) return false
    if (!skips.includes('tag9') && f.tag9 && (d.pendTot > 0 ? 'Pending' : '') !== f.tag9) return false
    if (!skips.includes('sujeto') && f.sujeto && norm(d.tag0 || d.sujeto) !== norm(f.sujeto)) return false
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
    [sessions, f, q, nums, qs, showElim, showVacio, showCron]
  )

  const sorted = useMemo(() => {
    const arr = visible.slice()
    arr.sort((a, b) => {
      if (orden.k === 'pending') {
        const diff = (Number(a.pendTot) || 0) - (Number(b.pendTot) || 0)
        if (diff !== 0) return diff * (orden.asc ? 1 : -1)
        return b.n - a.n
      }
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
  const nVacio = useMemo(() => sessions.filter((d) => d.vacia).length, [sessions])
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
    if (f.tag8) out.push(['tag8', f.tag8])
    if (f.tag9) out.push(['tag9', f.tag9])
    if (f.sujeto) out.push(['sujeto', f.sujeto])
    if (f.motor) out.push(['motor', f.motor])
    if (f.autor) out.push(['autor', f.autor])
    if (f.anio) out.push(['anio', f.anio])
    if (f.mes) out.push(['mes', nombreMes(f.mes, lang)])
    if (f.sem) {
      const [, wPart] = f.sem.split('|')
      out.push(['sem', `${t('semAbbr')} ${(wPart || '').split('-W')[1] || ''}`])
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
      tag8: null,
      tag9: null,
      sujeto: null,
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
      'pending',
      'pend_mem',
      'pend_skl',
      'sujeto_nuevo',
      'tag1_nuevo',
      'tag2_nuevo',
      'descripcion_nueva',
      'verbo_nuevo',
      'observaciones',
    ]
    const rows = vis.map((d) =>
      [
        d.n,
        d.id,
        d.fecha,
        d.raw,
        d.sujeto,
        d.tag1,
        d.tag2,
        d.desc,
        d.verb,
        d.pendTot || 0,
        (d.pendMem || []).length,
        (d.pendSkl || []).length,
        '',
        '',
        '',
        '',
        '',
        '',
      ]
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
      t('sujeto').toLowerCase() + ': ' + d.sujeto + ' · ordinal ' + String(d.mmm).padStart(3, '0'),
      'tag1 (' + t('lblPlataforma').toLowerCase() + '): ' + k(d.tag1) + ' | tag2 (' + t('lblFamilia').toLowerCase() + '): ' + k(d.tag2),
      'tag3 (' + t('lblPilar').toLowerCase() + '): ' + k(d.pilar || d.tag3) + ' | tag4 (' + t('lblPais').toLowerCase() + '): ' + k(d.pais || d.tag4) + ' | tag5 (' + t('lblAnio').toLowerCase() + '): ' + k(d.anio || d.tag5),
      'tag6 (' + t('lblMaquina').toLowerCase() + '): ' + k(d.tag6),
      'tag7: ' + k(d.tag7) + ' | tag8 (' + t('lblProyecto').toLowerCase() + '): ' + k(d.tag8) + ' | tag9: ' + k(d.tag9),
      t('descripcion') + ': ' + k(d.desc),
      t('fecha').toLowerCase() + ': ' + k(d.fecha) + ' · ' + t('mensajes').toLowerCase() + ': ' + k(d.mc) + ' · posts: ' + k(d.posts),
      t('costo').toLowerCase() + ': ' + fmtC(d.costo) + ' · ' + t('horas').toLowerCase() + ': ' + fmtHoras(d.horas) + ' · tokens: ' + (d.tok_tot ? Math.round(d.tok_tot / 1000) + 'k' : '—'),
      t('motor').toLowerCase() + ': ' + k(d.motor) + (d.motor_det ? ' (' + d.motor_det + ')' : '') + ' · ' + t('autor').toLowerCase() + ': ' + k(d.autor) + ' · ' + t('perfil').toLowerCase() + ': ' + k(d.prof),
    ]
    const cl = (d.claves || []).map((x) => String(x).replace(/\s+/g, ' ')).filter((x) => !esRuido(x))
    if (cl.length) {
      L.push('--- ' + t('mensajes').toLowerCase() + ' ---')
      cl.slice(0, 6).forEach((x) => L.push('> ' + x.slice(0, 400)))
    } else if (d.resumen && !esRuido(d.resumen)) {
      L.push('--- ' + (lang === 'en' ? 'summary' : 'resumen') + ' ---')
      L.push('> ' + String(d.resumen).replace(/\s+/g, ' ').slice(0, 600))
    }
    L.push('id: ' + d.id)
    return L.join('\n')
  }

  // Sequential navigation across visible rows from the detail card
  const filasVisibles = () => sorted

  const sesionActualIdx = (rows = sorted) => {
    if (!sel) return -1
    return rows.findIndex((r) => r.id === sel.id)
  }

  const updNaveg = () => {
    const rows = filasVisibles()
    const i = sesionActualIdx(rows)
    return {
      prevDisabled: i <= 0,
      nextDisabled: i < 0 || i >= rows.length - 1,
    }
  }

  const navSesion = (dir) => {
    const rows = filasVisibles()
    if (!rows.length) return
    let i = sesionActualIdx(rows)
    i = i < 0 ? 0 : Math.max(0, Math.min(rows.length - 1, i + dir))
    const target = rows[i]
    if (!target) return
    try {
      const tr = typeof document !== 'undefined' && document.querySelector(`#tb tbody tr.r[data-id="${target.id}"]`)
      if (tr && typeof tr.getBoundingClientRect === 'function') {
        const rect = tr.getBoundingClientRect()
        const vh = window.innerHeight || document.documentElement.clientHeight
        const margenArriba = vh * 0.22
        const margenAbajo = vh * 0.74
        if (rect.top < margenArriba || rect.bottom > margenAbajo) {
          tr.scrollIntoView({ block: 'center', behavior: 'smooth' })
        }
      }
    } catch (_) {
      /* ignore in headless tests */
    }
    selectSession(target, true)
  }

  // Notice banner for empty cron sessions
  const pintaAviso = () => {
    const n = cronInfo.vacias || 0
    const j = cronInfo.jobs_activos || 0
    if (n <= 0 && j <= 0) return null
    const tit = t('avTit').replace('{n}', n)
    const cuerpo = t('avCuerpo').replace('{j}', j)
    const act = j > 0 ? t('avActivos').replace('{j}', j) : ''
    const copyAviso = async () => {
      const ok = await copyText(ctx, t('avTexto'))
      setBtnMsg((p) => ({ ...p, avcopia: ok ? t('avCopiado') : '✗' }))
      setTimeout(() => setBtnMsg((p) => ({ ...p, avcopia: '' })), 2400)
    }
    return h(
      'div',
      { id: 'avisoCron', className: 'aviso on' },
      h(
        'div',
        { className: 'avhead' },
        h('b', null, '⚠ ' + tit),
        act ? h('span', { className: 'avpill' }, act) : null,
        h(
          'button',
          { id: 'avCopiar', onClick: copyAviso },
          btnMsg.avcopia || t('avCopiar')
        )
      ),
      h(
        'div',
        null,
        h('span', { dangerouslySetInnerHTML: { __html: cuerpo } }),
        ' ',
        h('span', { dangerouslySetInnerHTML: { __html: t('avConsejo') } })
      )
    )
  }

  // Detail card body renderer (re-evaluates cleanly when switching ES|EN)
  const pintaPanel = (d) => {
    if (!d) return h('div', { className: 'pbody' }, t('elegir'))
    const { prevDisabled, nextDisabled } = updNaveg()
    const selClaves = (d.claves || []).map((x) => String(x)).filter((x) => !esRuido(x))
    return h(
      'div',
      { className: 'pbody' },
      h(
        'div',
        { className: 'pthead' },
        h('div', { className: 'pname', id: 'pname' }, activeTab === 'testing' ? (d.canonTitle || d.raw) : d.raw),
        h(
          'div',
          { className: 'pnaveg' },
          h(
            'button',
            {
              className: 'navb',
              id: 'pPrev',
              title: t('navPrev'),
              disabled: prevDisabled,
              onClick: (e) => {
                e.stopPropagation()
                navSesion(-1)
              },
            },
            '▲'
          ),
          h(
            'button',
            {
              className: 'navb',
              id: 'pNext',
              title: t('navNext'),
              disabled: nextDisabled,
              onClick: (e) => {
                e.stopPropagation()
                navSesion(1)
              },
            },
            '▼'
          )
        )
      ),
      h('h3', { className: 'ptitle', id: 'ptitle' }, d.desc),
      d.resumen && !esRuido(d.resumen) ? h('p', { className: 'psum', id: 'psum' }, d.resumen) : null,
      h(
        'div',
        { className: 'kv', id: 'pkv' },
        h('div', null, 'tag0 · ' + t('sujeto')),
        h(
          'div',
          null,
          h('b', null, d.tag0 || d.sujeto),
          ' · ' + String(d.mmm || 1).padStart(3, '0'),
          d.vacia
            ? h(
                'span',
                {
                  className: 'pill',
                  style: {
                    marginLeft: '6px',
                    background: '#2a1d1f',
                    borderColor: '#5a3a40',
                    color: '#e6b8c0',
                  },
                  title: t('vacioTitle'),
                },
                t('vacio')
              )
            : null
        ),
        h('div', { style: { gridColumn: '1/-1', borderTop: '1px solid var(--line)', margin: '6px 0 2px' } }),
        pendMap
          ? [
              h(
                'div',
                { key: 'pend-mem', className: 'pendsec' },
                h(
                  'div',
                  { className: 'pendhead' },
                  h(
                    'button',
                    {
                      className: 'pendbtn',
                      disabled: (d.pendMem || []).length === 0,
                      onClick: () => copyPendingIds(d.pendMem || [], 'pendMem'),
                    },
                    btnMsg.pendMem || t('copyIds')
                  )
                ),
                h('h4', { className: 'pendtitle' }, t('pendMemTitulo')),
                h(
                  'div',
                  { className: 'pendbox' },
                  (d.pendMem || []).length > 0
                    ? d.pendMem.map((pid) =>
                        h('div', { key: pid, className: 'penditem', title: getAttrTooltip(pid) }, pid)
                      )
                    : h('div', { className: 'pendempty' }, '—')
                )
              ),
              h(
                'div',
                { key: 'pend-skl', className: 'pendsec' },
                h(
                  'div',
                  { className: 'pendhead' },
                  h(
                    'button',
                    {
                      className: 'pendbtn',
                      disabled: (d.pendSkl || []).length === 0,
                      onClick: () => copyPendingIds(d.pendSkl || [], 'pendSkl'),
                    },
                    btnMsg.pendSkl || t('copyIds')
                  )
                ),
                h('h4', { className: 'pendtitle' }, t('pendSklTitulo')),
                h(
                  'div',
                  { className: 'pendbox' },
                  (d.pendSkl || []).length > 0
                    ? d.pendSkl.map((pid) =>
                        h('div', { key: pid, className: 'penditem', title: getAttrTooltip(pid) }, pid)
                      )
                    : h('div', { className: 'pendempty' }, '—')
                )
              ),
              orphanIds.length > 0
                ? h(
                    'div',
                    { key: 'pend-orph', className: 'pendorph' },
                    h(
                      'div',
                      {
                        className: 'pendorphtog',
                        onClick: () => setOpenOrphans((v) => !v),
                      },
                      h('span', null, openOrphans ? '▾' : '▸'),
                      h('span', null, `${t('pendHuerfanas')} (${orphanIds.length})`)
                    ),
                    openOrphans
                      ? h(
                          'div',
                          { style: { marginTop: '8px' } },
                          h(
                            'div',
                            { className: 'pendhead' },
                            h(
                              'button',
                              {
                                className: 'pendbtn',
                                onClick: () => copyPendingIds(orphanIds, 'pendOrph'),
                              },
                              btnMsg.pendOrph || t('copyIds')
                            )
                          ),
                          h(
                            'div',
                            { className: 'pendbox' },
                            orphanIds.map((pid) =>
                              h('div', { key: pid, className: 'penditem', title: getAttrTooltip(pid) }, pid)
                            )
                          )
                        )
                      : null
                  )
                : null,
              h('div', { key: 'pend-div', style: { gridColumn: '1/-1', borderTop: '1px solid var(--line)', margin: '6px 0 2px' } }),
            ]
          : null,
        h('div', null, 'tag1 · ' + t('lblPlataforma')),
        h('div', null, h('span', { className: 'pill tag1' }, d.tag1 || '—')),
        h('div', null, 'tag2 · ' + t('lblFamilia')),
        h('div', null, h('span', { className: 'pill tag2' }, d.tag2 || '—')),
        h('div', null, 'tag3 · ' + t('lblPilar')),
        h('div', null, h('span', { className: 'pill tag3' }, d.pilar || d.tag3 || '—')),
        h('div', null, 'tag4 · ' + t('lblPais')),
        h('div', null, d.pais || d.tag4 ? h('span', { className: 'pill tag4' }, d.pais || d.tag4) : '—'),
        h('div', null, 'tag5 · ' + t('lblAnio')),
        h('div', null, d.anio || d.tag5 ? h('span', { className: 'pill tag5' }, d.anio || d.tag5) : '—'),
        h('div', null, 'tag6 · ' + t('lblMaquina')),
        h('div', null, h('span', { className: 'pill tag6' }, d.tag6 || '—')),
        h('div', null, 'tag7 · ' + t('lblLibre')),
        h('div', null, d.tag7 || '—'),
        h('div', null, 'tag8 · ' + t('lblProyecto')),
        h('div', null, d.tag8 ? h('span', { className: 'pill tag8' }, d.tag8) : '—'),
        h('div', null, 'tag9 · Pending'),
        h('div', null, d.tag9 ? h('span', { className: 'pill tag9' }, d.tag9) : '—'),
        h('div', { style: { gridColumn: '1/-1', borderTop: '1px solid var(--line)', margin: '6px 0 2px' } }),
        h('div', null, t('ruta')),
        h('div', null, `${d.dom || 'Software'} › ${d.tag5 || '—'} › ${d.tag1 || '—'}`),
        h('div', null, t('costo')),
        h('div', null, fmtC(d.costo)),
        h('div', null, t('horas')),
        h('div', null, fmtHoras(d.horas)),
        h('div', null, t('mensajes')),
        h('div', null, d.mc),
        h('div', null, t('fecha')),
        h('div', null, d.fecha),
        h('div', null, t('motor')),
        h('div', null, d.motor || '—'),
        h('div', null, t('autor')),
        h('div', null, d.autor || '—'),
        h('div', null, t('perfil')),
        h('div', null, d.prof)
      ),
      h('h4', { style: { marginTop: '14px' } }, t('mensajes')),
      h(
        'ul',
        { className: 'klist', id: 'pklist' },
        (selClaves.length ? selClaves : [t('sinMensajes')]).map((c, i) => h('li', { key: i }, c))
      ),
      h(
        'div',
        { className: 'why', id: 'pwhy' },
        h('b', null, t('adn') + ': '),
        t('sujeto').toLowerCase() + ' ',
        h('b', null, d.sujeto),
        ' · tag1 ',
        h('b', null, d.tag1 || '—'),
        ' (' + t('lblPlataforma').toLowerCase() + ') · tag2 ',
        h('b', null, d.tag2 || '—'),
        ' (' + t('lblFamilia').toLowerCase() + ') · tag3 ',
        h('b', null, d.pilar || d.tag3 || '—'),
        ' · ' + t('lblMaquina').toLowerCase() + ' ',
        h('b', null, d.tag6 || '—'),
        '. ' + t('adnNota')
      ),
      h(
        'button',
        {
          id: 'pedit',
          style: { marginTop: '6px' },
          onClick: () => {
            setEditVal(d.raw)
            setEditModal(true)
          },
        },
        t('editarBtn')
      ),
      h(
        'div',
        { className: 'pidfoot', id: 'pidfoot' },
        h('span', null, 'id'),
        (d.prof && d.prof !== 'default' ? `· ${t('perfil').toLowerCase()} ${d.prof} · ` : '') +
          d.id +
          (d.isLive ? ' · [runtime vivo]' : '')
      )
    )
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

  const createCommitBackup = async (sessionsList, opts) => {
    const keepLedger = Boolean(opts && opts.keepLedger)
    const list = sessionsList || sessions || []
    const entries = list
      .filter((d) => !esIntocable(d) && d.canonTitle && d.canonTitle !== d.raw)
      .map((d) => ({
        id: d.id,
        title_before: d.raw,
        title_after: d.canonTitle,
        prof: d.prof,
        ts: new Date().toISOString(),
      }))
    const fname = `commit-backup-${getBackupStamp()}.json`
    const payload = {
      filename: fname,
      ts: Date.now(),
      committed: false,
      reverted: false,
      changedCount: entries.length,
      entries,
    }
    const filesApi = (ctx && ctx.files) || (host && host.files)
    if (filesApi && typeof filesApi.writeText === 'function') {
      try {
        await filesApi.writeText('data', fname, JSON.stringify(payload, null, 2))
        // commit-last.json is the revert ledger. Do not overwrite it while it
        // still holds a commit that has not been reverted: that would lose the
        // only record Revert can restore from.
        if (!keepLedger) {
          await filesApi.writeText('data', 'commit-last.json', JSON.stringify(payload, null, 2))
        }
      } catch (_) {}
    }
    if (!keepLedger) setLastBackup(payload)
    return payload
  }

  const switchTab = async (tab) => {
    setActiveTab(tab)
    if (tab === 'testing') {
      const pendingRevert = lastBackup && lastBackup.committed && !lastBackup.reverted
      await createCommitBackup(sessions, { keepLedger: pendingRevert })
    }
  }

  const handleCommit = async () => {
    let curBackup = lastBackup
    // Reuse a fresh backup only when it is still pending: one that is already
    // committed describes titles that are already written, and re-applying it
    // would report the previous commit's count as if it were new work.
    if (
      !curBackup ||
      curBackup.committed ||
      curBackup.reverted ||
      !curBackup.ts ||
      Date.now() - curBackup.ts > 600000
    ) {
      curBackup = await createCommitBackup(sessions)
    }
    const targets = (curBackup && curBackup.entries) || []
    const eligibleCount = sessions.filter((d) => !esIntocable(d)).length
    const unchangedCount = eligibleCount - targets.length

    if (targets.length === 0) {
      setBtnMsg((p) => ({
        ...p,
        commit: t('commitDone', { n: 0, m: unchangedCount }),
      }))
      setTimeout(() => setBtnMsg((p) => ({ ...p, commit: '' })), 4000)
      return
    }

    const ok = window.confirm(t('confirmCommit', { n: targets.length }))
    if (!ok) return

    setIsCommitting(true)
    let updated = 0
    for (let i = 0; i < targets.length; i++) {
      const ent = targets[i]
      setBtnMsg((p) => ({
        ...p,
        commit: t('commitProgress', { current: i + 1, total: targets.length }),
      }))
      try {
        const res = await callRpc(ctx, 'session.resume', {
          session_id: ent.id,
          profile: ent.prof === 'default' ? undefined : ent.prof,
          lazy: true,
          omit_messages: true,
        })
        if (res && res.session_id) {
          await callRpc(ctx, 'session.title', { session_id: res.session_id, title: ent.title_after })
        }
        updated++
      } catch (err) {
        console.error('Error committing title for', ent.id, err)
      }
    }

    const idMap = new Map(targets.map((e) => [e.id, e.title_after]))
    setSessions((prev) =>
      prev.map((s) => (idMap.has(s.id) ? { ...s, raw: idMap.get(s.id) } : s))
    )

    const updatedBackup = {
      ...curBackup,
      committed: true,
      reverted: false,
      commitTs: Date.now(),
      changedCount: updated,
    }
    setLastBackup(updatedBackup)
    const filesApi = (ctx && ctx.files) || (host && host.files)
    if (filesApi && typeof filesApi.writeText === 'function') {
      try {
        await filesApi.writeText('data', 'commit-last.json', JSON.stringify(updatedBackup, null, 2))
        if (updatedBackup.filename) {
          await filesApi.writeText('data', updatedBackup.filename, JSON.stringify(updatedBackup, null, 2))
        }
      } catch (_) {}
    }

    setIsCommitting(false)
    if (updated > 0) {
      setCanRevert(true)
    }
    setBtnMsg((p) => ({
      ...p,
      commit: '',
      foot: t('commitDone', { n: updated, m: unchangedCount }),
    }))
    setTimeout(() => setBtnMsg((p) => ({ ...p, foot: '' })), 4500)
  }

  const handleRevert = async () => {
    if (!lastBackup || !Array.isArray(lastBackup.entries) || lastBackup.entries.length === 0) return
    const targets = lastBackup.entries

    const ok = window.confirm(t('confirmRevert', { n: targets.length }))
    if (!ok) return

    setIsReverting(true)
    let reverted = 0
    for (let i = 0; i < targets.length; i++) {
      const ent = targets[i]
      setBtnMsg((p) => ({
        ...p,
        revert: `Revert ${i + 1}/${targets.length}`,
      }))
      try {
        const res = await callRpc(ctx, 'session.resume', {
          session_id: ent.id,
          profile: ent.prof === 'default' ? undefined : ent.prof,
          lazy: true,
          omit_messages: true,
        })
        if (res && res.session_id) {
          await callRpc(ctx, 'session.title', { session_id: res.session_id, title: ent.title_before })
        }
        reverted++
      } catch (err) {
        console.error('Error reverting title for', ent.id, err)
      }
    }

    const revMap = new Map(targets.map((e) => [e.id, e.title_before]))
    setSessions((prev) =>
      prev.map((s) => (revMap.has(s.id) ? { ...s, raw: revMap.get(s.id) } : s))
    )

    const updatedBackup = {
      ...lastBackup,
      committed: false,
      reverted: true,
      revertTs: Date.now(),
    }
    setLastBackup(updatedBackup)
    const filesApi = (ctx && ctx.files) || (host && host.files)
    if (filesApi && typeof filesApi.writeText === 'function') {
      try {
        await filesApi.writeText('data', 'commit-last.json', JSON.stringify(updatedBackup, null, 2))
        if (updatedBackup.filename) {
          await filesApi.writeText('data', updatedBackup.filename, JSON.stringify(updatedBackup, null, 2))
        }
      } catch (_) {}
    }

    setIsReverting(false)
    setCanRevert(false)
    setBtnMsg((p) => ({
      ...p,
      revert: '',
      foot: t('revertDone', { n: reverted }),
    }))
    setTimeout(() => setBtnMsg((p) => ({ ...p, foot: '' })), 4500)
  }

  const handleUpdateRules = async () => {
    let idx = null
    const filesApi = (ctx && ctx.files) || (host && host.files)
    if (filesApi && typeof filesApi.readText === 'function') {
      try {
        const iRes = await filesApi.readText('data', 'index.json').catch(() => null)
        if (iRes && iRes.ok && iRes.text) idx = JSON.parse(iRes.text)
      } catch (_) {}
    }

    // Re-read the catalogue from disk. This button exists to pick up new rules and
    // a rebuilt index, so a count computed from the in-memory rows would be a lie.
    let rows = sessions
    try {
      const res = await loadCatalogue(ctx)
      if (res && Array.isArray(res.sessions)) {
        rows = res.sessions
        setSessions(rows)
        setRpcErrors(Array.isArray(res.errors) ? res.errors : [])
        setPendData(res.pendData || null)
        setPendMap(res.pendMap || null)
        setPendAttr(res.pendAttr || null)
      }
    } catch (_) {}

    let isStale = false
    if (idx && idx.generated) {
      const genTs = new Date(idx.generated).getTime()
      if (!isNaN(genTs) && Date.now() - genTs > 24 * 3600 * 1000) {
        isStale = true
      }
    }

    const diffCount = rows.filter(
      (d) => !esIntocable(d) && d.canonTitle && d.canonTitle !== d.raw
    ).length

    setStaleNotice(isStale ? t('updateStale') : '')
    const label = diffCount === 0 ? t('updateClean') : t('updateCount', { count: diffCount })
    setBtnMsg((p) => ({ ...p, update: label, foot: isStale ? `${label} · ${t('updateStale')}` : label }))
    setTimeout(() => setBtnMsg((p) => ({ ...p, update: '', foot: '' })), 8000)
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

  // Only keep one month open at a time when expanding a month node
  const openSoloUnMes = (km) => {
    setOpenNodes((prev) => {
      const next = new Set()
      for (const k of prev) {
        if (!k.startsWith('m:') || k === km) next.add(k)
      }
      next.add(km)
      return next
    })
  }

  // Render a foldable radio facet block (tag1, tag2, tag3i, tag3/pilar)
  const renderFacetBlock = (blockId, labelKey, stateKey, fieldName, sortSpecial) => {
    const isOff = folded.has(blockId)
    const { c, allValues } = facetCounts([stateKey === 'tag3' ? 'tag3' : stateKey === 'tag3i' ? 'tag3i' : stateKey], fieldName)
    const FIJOS1 = blockId === 'tag1' ? ['Bot'] : []
    const allKeys = [...new Set([...allValues, ...FIJOS1])]
      .filter((k) => k && ((c[k] || 0) > 0 || f[stateKey] === k))
      .sort((a, b) => {
        if (sortSpecial) {
          if (a === 'Temas Varios') return 1
          if (b === 'Temas Varios') return -1
        }
        return (c[b] || 0) - (c[a] || 0)
      })
    const isExp = expanded.has(blockId) || allKeys.indexOf(f[stateKey]) >= 10
    let shown = isExp ? allKeys : allKeys.slice(0, 10)
    if (blockId === 'tag1') {
      FIJOS1.forEach((fk) => {
        if (allKeys.includes(fk) && !shown.includes(fk)) shown = [...shown, fk]
      })
    }

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
                  isExp ? t('Menos') : `+ ${allKeys.length - shown.length} ${t('Mas')}`
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
                        if (om) toggleNode(km)
                        else openSoloUnMes(km)
                        return
                      }
                      const nextMes = f.mes === m ? null : m
                      setF((p) => ({ ...p, mes: nextMes, anio: nextMes ? m.slice(0, 4) : p.anio, sem: null }))
                      if (nextMes) openSoloUnMes(km)
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

  const pendStats = useMemo(() => {
    let n = 0
    for (const d of sessions) if (pass(d) && d.pendTot > 0) n++
    return n
  }, [sessions, visible, f.tag9])

  const sujetoStats = useMemo(() => {
    const cnt = {}
    for (const d of sessions) {
      if (pass(d)) {
        const k = d.tag0 || d.sujeto || 'Sin sujeto'
        cnt[k] = (cnt[k] || 0) + 1
      }
    }
    const keys = Object.keys(cnt)
      .filter((k) => (cnt[k] || 0) > 0 || f.sujeto === k)
      .sort((a, b) => (cnt[b] || 0) - (cnt[a] || 0))
    return { cnt, keys }
  }, [sessions, visible, f.sujeto])

  const hiddenByFilterCount = useMemo(() => {
    if (visible.length > 0 || !qNorm) return 0
    return sessions.filter((d) =>
      norm([d.desc, d.tema, d.sujeto, d.tag1, d.tag2, d.pilar, d.n].join(' ')).includes(qNorm)
    ).length
  }, [visible.length, qNorm, sessions])

  const sortCol = (k, isNum = false) => {
    setOrden((p) => (p.k === k ? { k, asc: !p.asc } : { k, asc: !isNum }))
  }

  // Build two-line rows matching 2026-11-11_simulador-solo-codigo.html
  const tableRows = sorted.flatMap((d) => {
    const rawToDisplay = (activeTab === 'testing' ? (d.canonTitle || d.raw) : d.raw) || ''
    const cut = rawToDisplay.lastIndexOf(']')
    const head = (cut > 0 ? rawToDisplay.slice(0, cut + 1) : `[${d.sujeto}] ${String(d.mmm).padStart(3, '0')}`).replace(
      /^\d+\s+/,
      ''
    )
    const tail = cut > 0 ? rawToDisplay.slice(cut + 1).trim() : d.desc
    const isDel = /borrad/i.test(d.sujeto) || esBorrada(d)
    const isSel = Boolean(sel && sel.id === d.id)

    return [
      h(
        'tr',
        {
          className: 't' + (isSel ? ' sele' : ''),
          key: d.id + '-t',
          onClick: () => selectSession(d),
        },
        h('td', { className: 'ncol t' }, d.n),
        h(
          'td',
          { colSpan: pendMap ? 7 : 6, className: 'ttitle' + (isDel ? ' borrada' : '') },
          h('b', { className: 'tfac' }, head),
          tail ? h('b', { className: 'tdesc' }, ' ' + tail) : null
        )
      ),
      h(
        'tr',
        {
          className: 'r' + (isSel ? ' sele' : ''),
          'data-id': d.id,
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
                setF((p) => ({ ...p, sujeto: p.sujeto === d.sujeto ? null : d.sujeto }))
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
        h('td', { className: 'num tight cen' }, fmtHoras(d.horas)),
        h('td', { className: 'num tight cen', style: { color: 'var(--tx3)' } }, fmtT(d.tok_tot)),
        h('td', { className: 'num tight cen', style: { color: 'var(--tx3)' } }, fmtP(d.posts)),
        pendMap
          ? h(
              'td',
              { className: 'num tight cen' },
              d.pendTot > 0
                ? h(
                    'span',
                    {
                      className: 'pill tag9',
                      title: `(mem) ${(d.pendMem || []).length} · (skills) ${(d.pendSkl || []).length}`,
                    },
                    'Pending'
                  )
                : '—'
            )
          : null
      ),
    ]
  })

  return h(
    'div',
    { className: 'mmws' },
    h('style', null, CSS),

    /* ---------- Header ---------- */
    h(
      'header',
      { className: 'top' },
      h(
        'div',
        { className: 'brandrow' },
        h(
          'h1',
          {
            onClick: () => setVModal(true),
            style: { cursor: 'pointer' },
            title: t('infoPluginTitle'),
          },
          APP_TITLE
        ),
        h(
          'span',
          { className: 'sub' },
          h('b', null, loading ? '—' : sessions.length),
          ' sesiones · NNN [Sujeto] MMM [Tag1] [Tag2] Descripción · Verbo'
        ),
        h(
          'div',
          { className: 'headtabs', role: 'tablist' },
          h(
            'button',
            {
              role: 'tab',
              className: 'headtab' + (activeTab === 'actual' ? ' on' : ''),
              onClick: () => switchTab('actual'),
              title: t('tabActualTitle'),
            },
            t('tabActual')
          ),
          h(
            'button',
            {
              role: 'tab',
              className: 'headtab' + (activeTab === 'testing' ? ' on testing' : ''),
              onClick: () => switchTab('testing'),
              title: t('tabTestingTitle'),
            },
            t('tabTesting')
          )
        ),
        h(
          'button',
          {
            className: 'ghost langsw',
            id: 'btnLang',
            onClick: toggleLang,
            title: 'Idioma de la interfaz · Interface language',
          },
          h('span', { className: lang === 'es' ? 'on' : '' }, 'ES'),
          h('span', { className: lang === 'en' ? 'on' : '' }, 'EN')
        )
      )
    ),

    /* ---------- Stale Notice Banner ---------- */
    staleNotice
      ? h(
          'div',
          {
            className: 'aviso',
            style: { margin: '6px 16px', background: '#2e1c14', borderColor: '#733a1e' },
          },
          h('b', null, 'ℹ '),
          staleNotice,
          h(
            'button',
            {
              className: 'ghost',
              onClick: () => setStaleNotice(''),
              style: { marginLeft: 'auto', padding: '1px 6px', fontSize: '11px' },
            },
            '✕'
          )
        )
      : null,

    /* ---------- Visible Diagnostic Error Banner ---------- */
    rpcErrors && rpcErrors.length > 0
      ? h(
          'div',
          { className: 'errbanner', role: 'alert' },
          h('b', null, '⚠ Error de carga RPC:'),
          h(
            'div',
            { className: 'errlist' },
            rpcErrors.map((er, idx) =>
              h(
                'span',
                { key: idx },
                `[${er.method}] ${er.message}`
              )
            )
          ),
          h(
            'button',
            {
              className: 'ghost',
              onClick: () => refreshData(true),
              style: { fontSize: '11px', padding: '2px 7px' },
            },
            'Reintentar'
          ),
          h(
            'button',
            {
              className: 'ghost',
              onClick: () => setRpcErrors([]),
              style: { fontSize: '11px', padding: '2px 7px' },
            },
            '✕'
          )
        )
      : null,

    /* ---------- Body (Aside + Main + Slide-over Detail Panel) ---------- */
    h(
      'div',
      { className: 'bodywrap' },

      /* Left Filters Aside */
      h(
        'aside',
        null,
        h(
          'div',
          { className: 'abarra' },
          h('input', {
            id: 'q',
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
          })
        ),
        h(
          'div',
          { className: 'ascroll' },
          pendMap
            ? [
                h(
                  'h4',
                  { key: 'pend-h4' },
                  h('span', null, t('pendFacet')),
                  h('span', null, pendStats + ' ' + t('pendFacetCount'))
                ),
                h(
                  'div',
                  { key: 'pend-opt' },
                  h(
                    'label',
                    {
                      className: 'opt' + (f.tag9 === 'Pending' ? ' sel' : ''),
                      onClick: (e) => {
                        e.preventDefault()
                        setF((p) => ({ ...p, tag9: p.tag9 === 'Pending' ? null : 'Pending' }))
                      },
                    },
                    h('input', { type: 'radio', checked: f.tag9 === 'Pending', readOnly: true }),
                    h('span', null, 'Pending'),
                    h('span', { className: 'n' }, pendStats)
                  )
                ),
              ]
            : null,

          h(
            'h4',
            null,
            h('span', null, t('sujetoFacet')),
            h('span', null, (f.sujeto ? t('de1') : '') + sujetoStats.keys.length + ' ' + t('sujetosCount'))
          ),
          h(
            'div',
            null,
            (expandSujetos ? sujetoStats.keys : sujetoStats.keys.slice(0, 20)).map((k) =>
              h(
                'label',
                {
                  key: k,
                  className: 'opt' + (f.sujeto === k ? ' sel' : '') + (k === 'Sin sujeto' ? ' empty' : ''),
                  onClick: (e) => {
                    e.preventDefault()
                    setF((p) => ({ ...p, sujeto: p.sujeto === k ? null : k }))
                  },
                },
                h('input', { type: 'radio', checked: f.sujeto === k, readOnly: true }),
                h('span', null, k),
                h('span', { className: 'n' }, sujetoStats.cnt[k] || 0)
              )
            ),
            sujetoStats.keys.length > 20
              ? h(
                  'button',
                  {
                    className: 'navb',
                    style: {
                      width: '100%',
                      height: '24px',
                      fontSize: '11px',
                      marginTop: '4px',
                      textAlign: 'center',
                    },
                    onClick: () => setExpandSujetos((v) => !v),
                  },
                  expandSujetos
                    ? (lang === 'en' ? 'Show less' : 'Ver menos')
                    : `+ ${sujetoStats.keys.length - 20} ${lang === 'en' ? 'more' : 'más'}`
                )
              : null
          ),

          renderFacetBlock('tag1', 'tag1', 'tag1', 'tag1', false),
          renderFacetBlock('tag2', 'tag2', 'tag2', 'tag2', false),
          renderFacetBlock('tag3', 'tag3', 'tag3i', 'tag3', false),
          renderFacetBlock('tag4', 'tema', 'tag3', 'pilar', true),
          renderFacetBlock('tag8', 'lblProyecto', 'tag8', 'tag8', false),

          h('h4', null, t('fecha')),
          h('div', null, renderFechaTree()),

          h('h4', null, t('diaExacto')),
          h('input', {
            id: 'dia',
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
              id: 'd1',
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
              id: 'd2',
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
        )
      ),

      /* Main Session List */
      h(
        'main',
        {
          onClick: (e) => {
            if (
              sel &&
              !e.target.closest('tr.t') &&
              !e.target.closest('tr.r') &&
              !e.target.closest('#tabInfo')
            ) {
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
              'span',
              { id: 'acciones' },
              h(
                'button',
                {
                  id: 'clr',
                  className: 'clrbtn primary' + (activeChips.length ? '' : ' ghost'),
                  disabled: !activeChips.length,
                  onClick: limpiar,
                  title: 'Limpiar todos los filtros activos',
                },
                t('limpiar')
              ),
              h(
                'button',
                {
                  id: 'copia',
                  className: 'ghost',
                  onClick: copiarResultado,
                  title: 'Copia los nombres e IDs de las sesiones visibles al portapapeles',
                },
                btnMsg.copia || `${t('copiar')} · ${visible.length}`
              ),
              h(
                'button',
                {
                  id: 'expc',
                  className: 'ghost',
                  onClick: exportarCorrecciones,
                  title: 'Descarga CSV de las sesiones visibles para anotar correcciones',
                },
                btnMsg.expc || `${t('exportar')} · ${visible.length}`
              )
            ),
            h('span', { className: 'sub', style: { fontSize: '11.5px', marginLeft: '14px' } }, t('mostrarLbl')),
            h(
              'button',
              {
                id: 'btnElim',
                className: showElim ? 'on' : '',
                onClick: () => setEstado('elim'),
                title: 'Mostrar u ocultar sesiones marcadas como borradas',
              },
              (showElim ? t('hideDel') : t('showDel')) + ' · ' + nElim
            ),
            h(
              'button',
              {
                id: 'btnVacio',
                className: showVacio ? 'on' : '',
                onClick: () => setEstado('vacio'),
                title: t('vacioTitle'),
              },
              (showVacio ? t('hideVacio') : t('showVacio')) + ' · ' + nVacio
            ),
            h(
              'button',
              {
                id: 'btnCron',
                className: showCron ? 'on' : '',
                onClick: () => setEstado('cron'),
                title: 'Mostrar u ocultar sesiones automáticas de cron',
              },
              (showCron ? t('hideCron') : t('showCron')) + ' · ' + nCron
            ),
            h('span', { style: { flex: 1, minWidth: 0 } })
          ),
          h(
            'div',
            { className: 'chipsrow' },
            h(
              'div',
              { className: 'chips', id: 'chips' },
              h(
                'span',
                { id: 'chipwrap', className: 'chipwrap' },
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
            ),
            h(
              'span',
              { className: 'counter', id: 'counter' },
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
                            tag8: null,
                            tag9: null,
                            sujeto: null,
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
            )
          ),
          h(
            'button',
            {
              id: 'tabInfo',
              title: t('tabInfoTitle'),
              onClick: (e) => {
                e.stopPropagation()
                if (sorted.length > 0) {
                  selectSession(sorted[0], true)
                }
              },
            },
            h('span', null, t('tabInfo'))
          )
        ),

        pintaAviso(),

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
              h('th', { className: 'tight', onClick: () => sortCol('posts', true) }, t('colPosts')),
              pendMap
                ? h('th', { className: 'tight cen', onClick: () => sortCol('pending', true) }, t('colPending'))
                : null
            )
          ),
          h('tbody', null, tableRows)
        )
      ),

      /* Slide-over Detail Card Panel */
      h(
        'div',
        { className: 'panel' + (sel ? ' on' : ''), id: 'panel' },
        h(
          'div',
          { className: 'pbar' },
          h(
            'div',
            { className: 'pbar-l' },
            h('button', { id: 'pcopia-top', onClick: copyCard }, btnMsg.pcopia || t('copiarSesion')),
            h('button', { className: 'openbtn', id: 'popen-top', onClick: () => openSession(sel) }, t('abrirSesion'))
          ),
          h(
            'span',
            { className: 'x', id: 'px', onClick: () => setSel(null) },
            '✕'
          )
        ),
        pintaPanel(sel),
        h(
          'div',
          { className: 'pbar bottom' },
          h('button', { id: 'pcopia', onClick: copyCard }, btnMsg.pcopia || t('copiarSesion')),
          h('button', { className: 'openbtn', id: 'popen', onClick: () => openSession(sel) }, t('abrirSesion'))
        )
      )
    ),

    /* ---------- Bottom Footer Row (Unified Actions + 5 KPIs) ---------- */
    h(
      'div',
      { className: 'footrow' },
      activeTab === 'testing'
        ? h(
            'div',
            { className: 'footbtns' },
            !canRevert
              ? h(
                  'button',
                  {
                    className: 'commitbtn',
                    id: 'btnCommit',
                    disabled: isCommitting || isReverting,
                    onClick: handleCommit,
                    title: t('commitBtnTitle'),
                  },
                  btnMsg.commit || t('commitBtn')
                )
              : h(
                  'button',
                  {
                    className: 'revertbtn',
                    id: 'btnRevert',
                    disabled: isCommitting || isReverting,
                    onClick: handleRevert,
                    title: t('revertBtnTitle'),
                  },
                  btnMsg.revert || t('revertBtn')
                ),
            h(
              'button',
              {
                className: 'updatebtn',
                id: 'btnUpdate',
                disabled: isCommitting || isReverting,
                onClick: handleUpdateRules,
                title: t('updateBtnTitle'),
              },
              btnMsg.update || t('updateBtn')
            ),
            btnMsg.foot ? h('span', { className: 'footmsg' }, btnMsg.foot) : null
          )
        : h('div', { className: 'footbtns' }),
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
          { className: 'kpi pst' },
          h('b', null, fmtP(totals.posts)),
          h('div', { className: 'lb' }, h('i', null, t('kPost1')), h('i', null, t('kPost2')))
        ),
        h(
          'div',
          { className: 'kpi tok' },
          h('b', null, fmtT(totals.toks)),
          h('div', { className: 'lb' }, h('i', null, t('kTok1')), h('i', null, t('kTok2')))
        ),
        pendData
          ? h(
              'div',
              {
                className: 'kpi pend clickable' + (f.tag9 === 'Pending' ? ' active' : ''),
                onClick: () => setF((p) => ({ ...p, tag9: p.tag9 === 'Pending' ? null : 'Pending' })),
                title: t('kPendTitle'),
              },
              h('b', null, (pendData.counts && pendData.counts.total) || 0),
              h('div', { className: 'lb' }, h('i', null, t('kPend1')), h('i', null, t('kPend2')))
            )
          : null
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
              h('h4', { style: { fontSize: '13px', margin: 0, color: 'var(--tx)' } }, APP_TITLE),
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
export { numSel, fmtC, fmtH, fmtN, loadCatalogue, canonicalTitle }

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
