# Pendientes

Estado al cerrar la sesión del **2026-11-10**. Ordenados por prioridad, no por
tamaño.

## 1 · Rotar la clave de DeepSeek  🔴 urgente

La clave que se pegó en la sesión 23 («API Key», 11-ago) viajó dentro del campo
`claves` del dataset, de ahí al HTML del simulador y al historial de este repo.
Ya está redactada en `tools/sim80.json` y en el HTML (`[REDACTED-API-KEY]`),
pero **sanear los archivos no borra el historial ni lo que ya viajó**.

Pasos:

1. Panel de DeepSeek → revocar la clave de DeepSeek del 11-ago y crear una nueva.
2. Actualizar `~/.hermes/auth.json` (hermes config / el panel de credenciales).
3. Comprobar que Hermes responde con la nueva.
4. Opcional: reescribir el historial de este repo para purgar el blob
   (`git filter-repo`). Solo si se decide que el repo vaya a publicarse; con la
   clave rotada el riesgo desaparece y el historial no vale el trabajo.

## 2 · Identificador interno — ✅ HECHO (2026-11-11)

El id interno es `make-all-my-work-smart` en todas partes, igual que el nombre
visible. Verificado: el índice se reconstruye en
`~/.hermes/plugin-data/make-all-my-work-smart/index.json` con **910 sesiones**,
460 sujetos, tag3 en 570 y tag4 en 854.

| Archivo | Antes | Ahora |
|---|---|---|
| `core/paths.py` | `PLUGIN = "make-my-work-smart"` | `"make-all-my-work-smart"` |
| `desktop/plugin.js` | `ID = 'make-my-work-smart'` | `'make-all-my-work-smart'` |
| `README.md`, `docs/STORAGE.md`, `tests/` | id viejo | id nuevo |

Los directorios de datos se **copiaron** (`cp -R`) a
`~/.hermes/plugin-data/make-all-my-work-smart/` y
`~/.hermes/desktop-plugins/make-all-my-work-smart/`. El directorio viejo sigue
en su sitio: solo se borra después de reiniciar Desktop y ver que carga.

## 3 · Las 15 sesiones con sujeto = marca

```
41,71,76,80,93,102,110,136,137,139,218,365,446,454,835
```

Se pegan en el buscador del simulador tal cual. La regla: la marca va en tag1 y
el sujeto describe qué se hizo con ella. Ojo con los dos casos que el propio
Jorge ya resolvió antes:

- **365 Pinokio** → tag1 `Pinokio`, sujeto `Control CLI`.
- **93** → el sujeto correcto es `Unsloth Studio` (lo comparado), no Ollama.

Y la excepción guardada: si al quitar la marca el sujeto queda sin sentido
(`Bot`, `3.8 27B`), **no se quita** — un sujeto vacío es peor que uno repetido.

## 4 · Afinar las reglas de tag

Jorge lo dejó para mañana. Contexto útil: de **460 sujetos**, **369 aparecen una
sola vez**; cuatro concentran 206 sesiones. El mapa completo está en
`~/Documents/Reportes - [Lisa]/2026-11-10_[reporte]_sujetos-del-plugin-frecuencia.md`.

## 5 · Correr el set de evaluación

`tests/eval/` y el set de 50 sesiones están congelados y **no se han corrido
contra el esquema nuevo**. Sin eso, afinar las reglas es a ojo.

## 6 · Publicar el repo de entrega — miércoles

```bash
gh repo edit tesla963/make-all-my-work-smart \
  --visibility public --accept-visibility-change-consequences
```

Solo ese repo. `hermes-make-all-my-work-smart` (datos y documentos internos) se
queda privado **siempre**.

## Estado al cerrar

```
base de Hermes     848 títulos escritos por la API oficial
simulador          909 sesiones · 762 visibles · 42 borradas · 105 cron
plugin instalado   909 sesiones · 460 sujetos · tag3 en 570 · tag4 en 854
repos              trabajo y entrega, ambos privados, ambos renombrados
```
