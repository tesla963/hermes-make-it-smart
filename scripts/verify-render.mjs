// Render estático del panel real: sirve para medir geometría con browser_exec.
// Uso: node scripts/verify-render.mjs [salida.html]
import { readFileSync, writeFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'
import { resolve, dirname, join } from 'node:path'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const NM = process.env.HERMES_NODE_MODULES || '/Users/tesla369/.hermes/hermes-agent/apps/desktop/node_modules'
const asUrl = (p) => pathToFileURL(p).href
const out = process.argv[2] || '/tmp/panel-render.html'

const src = readFileSync(root + '/desktop/plugin.js', 'utf8')
  .replace(/from '@hermes\/plugin-sdk'/g, `from '${asUrl(root + '/tests/mocks/plugin-sdk.js')}'`)
  .replace(/from 'react\/jsx-runtime'/g, `from '${asUrl(NM + '/react/jsx-runtime.js')}'`)
  .replace(/from 'react'/g, `from '${asUrl(NM + '/react/index.js')}'`)

const tmp = join(tmpdir(), 'mms-render-under-test.mjs')
writeFileSync(tmp, src)

const mod = await import(asUrl(tmp) + '?v=' + Date.now())
const seen = []
mod.default.register({
  registerMany: (i) => seen.push(...i),
  register: (i) => seen.push(i),
  files: { readText: async () => ({ ok: false }), writeText: async () => ({ ok: false }) },
  os: {},
})

const { renderToStaticMarkup } = await import(asUrl(NM + '/react-dom/server.js'))
const { createElement } = await import(asUrl(NM + '/react/index.js'))
const entry = seen.find((x) => x.render)
const html = renderToStaticMarkup(createElement(entry.render))

writeFileSync(
  out,
  '<!doctype html><meta charset="utf-8">\n<style>html,body{margin:0;background:#0d0b0e;height:100%}.mmws{height:840px}</style>\n' + html
)
console.log('render chars:', html.length, '| toppanel:', html.includes('toppanel'), '| tabInfo:', html.includes('tabInfo'), '| →', out)
