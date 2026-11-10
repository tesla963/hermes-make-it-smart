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

## 7 · Aviso de higiene de cron — ✅ en el simulador, pendiente en el plugin

Un cron job con monitor deja sesiones vacías (bug #140222 de Hermes: la sesión se
crea antes de que el gate decida que no hay nada que reportar). El simulador
ahora lo detecta y lo dice.

**Hecho (2026-11-11, MVP del simulador):**

- `tools/make_simulator.py` cuenta las sesiones `source=cron` sin ningún mensaje y
  los cron jobs vivos leyendo `~/.hermes/cron/jobs.json`.
- La plantilla pinta un banner arriba de la tabla, en ES/EN. **No ordena pausar:**
  nombra la causa con enlace al [issue #140222](https://github.com/NousResearch/hermes-agent/issues/140222),
  señala la dirección (pausar y recrear en modo `no_agent`) y aclara que el panel no
  toca los cron jobs: eso se le pide al agente de Hermes.
- Botón para copiar el texto listo: «Lisa, tengo N sesiones vacías de cron…».
- **Filtro «Vacío»/«Empty»**, el tercero de la fila de estado y **activado por
  defecto**: las sesiones sin mensajes no aparecen en el listado. Se desactiva con
  un clic.
- Horas en **tiempo activo** (intervalos entre mensajes < 30 min), en minutos
  enteros y con días cuando pasa de 24 h (`1d 20h`). Antes se calculaba
  apertura→cierre y una sesión reabierta durante meses marcaba 2.019 horas.

**Regla del proyecto:** el panel solo pinta e informa. Pausar jobs, borrar sesiones o
escribir en la base es del dueño o de su agente. «No estamos invitados a ese velorio.»

**Pendiente (cuando exista `desktop/plugin.js`):**

| Pieza | Estado |
|---|---|
| El mismo aviso en el panel del plugin, al importar | no empezado |
| Botón para pausar el job desde la UI | no empezado — el panel solo pinta por diseño |
| Enlace al issue #140222 mientras no haya fix upstream | no empezado |

**Por qué entra en el MVP:** detectarlo es una consulta y una lectura de JSON; el
generador ya abre las 12 bases. Sin el aviso, el usuario culpa al plugin de una
basura que generó el cron.

## Estado al cerrar

```
base de Hermes     848 títulos escritos por la API oficial · 809 sesiones
                   46 sesiones vacías de cron borradas el 2026-11-11
simulador          864 sesiones · 851 con sujeto · 570 con intención
cron jobs          0 — los 4 borrados; definiciones en el registro del 11-nov
repos              trabajo: código, 0 data · entrega: solo el simulador
```
