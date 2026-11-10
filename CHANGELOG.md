# Changelog

## v0.1.0-preview — 2026-11-10 · GUI instalable, sin funcionalidad de escritura

**Qué es:** la primera versión que un tercero puede instalar y ver funcionando con sus propios
datos. La ventana nativa de Hermes Desktop lee las sesiones reales del gateway y las muestra en el
catálogo. **No escribe nada**: no renombra, no clasifica, no actualiza la base.

### Hito — la GUI nativa muestra las 910 sesiones reales

Verificado sobre la instalación del autor: tabla con las columnas del simulador, aside con árbol
de fechas, y barra KPI con **768 sesiones visibles · $69.85 acumulados · 267M tokens**.

### Añadido

- `register(ctx)` con el hook `on_session_end`, que refresca `index.json` con
  `build(with_messages=False)` para no reconstruir los cuerpos de mensaje en cada turno.
- Página nativa (`desktop/plugin.js`) registrada en `ROUTES_AREA` (`/smart`) y en el sidebar como
  **Make It Smart**, gemela del simulador: fila de dos líneas, nueve slots de tag, pills, aside con
  facetas, barra KPI de cinco cifras, ficha de detalle, copiar/exportar y switch ES|EN.
- Carga de datos desde el host: `session.list` por perfil (vía `host.request` /
  `host.listPersistedSessions`), con costo, horas, tokens y motor calculados desde `state.db`.
- **Banner de diagnóstico** visible: si un RPC falla, muestra el método, el mensaje literal y un
  botón Reintentar, en lugar de callar el error.

### Corregido

- La tabla salía vacía porque `ctx.files.readText('data', …)` lee de
  `~/Library/Application Support/Hermes/plugin-files/data/<plugin>/` y no de
  `~/.hermes/plugin-data/<plugin>/`. Los datos se publican ahora en la ruta que el host lee.
- Los cargadores se tragaban los fallos con `catch(_)`, lo que hacía invisible la causa.

### Limitaciones conocidas de esta versión

- **No escribe.** Editar y persistir títulos desde la ventana, y el clasificador en lote, son la
  siguiente etapa.
- El botón *Actualizar BD* detecta sesiones sin título canónico pero **no** ejecuta el clasificador
  Python: no existe todavía un método RPC del host que lo dispare.
- Los ejes de tags siguen el orden viejo en `core/taxonomy.py`; el remapeo a la nomenclatura de
  `docs/FEATURES.md` está pendiente.
- Paridad visual incompleta: chips de filtros activos, sinónimos en la búsqueda, pills clicables,
  filtro de sesiones borradas, export con contador.

### Instalación

```bash
git clone https://github.com/tesla963/hermes-make-all-my-work-smart
cd hermes-make-all-my-work-smart
python3 tools/build_index.py          # construye index.json desde tus state.db (solo lectura)
cp desktop/plugin.js ~/.hermes/desktop-plugins/make-all-my-work-smart/plugin.js
```

Reinicia Hermes Desktop y abre **Make It Smart** en el sidebar. La especificación funcional completa
está en `docs/FEATURES.md`.
