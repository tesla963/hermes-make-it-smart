# Tarea: la trampa y después sin trampa

Ejercicio pedido por el dueño: usar los **títulos que ya existen** en su base como referencia
(el "maestro"), lograr que el algoritmo los reproduzca, y después **quitar la trampa** para que
el renombrado salga igual o mejor por sí solo.

---

## Paso 0 · Tu propio respaldo (obligatorio, antes de nada)

```
mkdir -p /tmp/antigravity-backup-<fecha>
sqlite3 ~/.hermes/state.db "VACUUM INTO '/tmp/antigravity-backup-<fecha>/state.db'"
tar -czf /tmp/antigravity-backup-<fecha>/plugin-worktree.tar.gz -C ~/Documents/hermes-make-it-smart --exclude=.git .
```

Con eso podés revertir cualquier cosa que hagas, sin pedirme nada. Si algo sale mal, **vos**
restaurás y me lo decís.

Prohibido: escribir en `~/.hermes/plugin-data/`, aplicar renombrados, `git commit`, `git push`.

---

## Paso 1 · Construir el maestro (la trampa)

De `~/.hermes/plugin-data/make-it-smart/index.json` (887 sesiones), tomar cada sesión cuyo
título ya sea canónico (`^\d{3,4} \[`) y guardar sus campos como verdad de referencia:

```json
{"<id>": {"n": 24, "sujeto": "DeepSeek", "iq1": "DeepSeek", "iq2": "", "iq3": "Web Search",
          "desc": "...", "verb": "...", "raw": "024 [DeepSeek] 001 ..."}}
```

Escribilo en `tools/teacher.json` **sin datos personales** (nada de nombres propios del dueño,
proveedores ni rutas: correr `python3 tools/check_publish.py` antes de terminar).

## Paso 2 · Corrida con trampa

`propose_rename.py --teacher`: para cada sesión que esté en el maestro, usar **sus campos** y
reconstruir el título. Objetivo: reproducir **el 100 %** de los títulos existentes. Si no
reproduce uno, el bug está en el ensamblado del título, no en las reglas.

Reportá: N sesiones, M títulos reproducidos exactos, diferencias con su motivo.

## Paso 3 · Corrida sin trampa (la de verdad)

`propose_rename.py` (sin `--teacher`): derivar los campos de cada sesión **solo** con las reglas
y el texto (título, sujeto, descripción, primer prompt), sin consultar el maestro.

Medí **acuerdo**: cuántos títulos coinciden exactamente con el maestro, y de los que no,
cuántos son mejores y cuántos peores según las reglas (sujeto ≤3 palabras, sin duplicar iq1,
sin frases, intención canónica, par estrecho+ancho).

Reportá el acuerdo en porcentaje y los **5 patrones de falla más frecuentes**, con un ejemplo
real de cada uno.

## Paso 4 · Mejorar las reglas

Con esos patrones, agregar o corregir reglas **en Python** (`core/normalize.py`,
`tools/propose_rename.py`) y volver a medir. Meta: subir el acuerdo sin empeorar ningún título
(ningún sujeto mutilado, ninguna descripción duplicada, ningún título más largo que el original
sin razón).

## Paso 5 · Entregar

Escribí `~/Documents/hermes-make-it-smart/INFORME-TRAMPA.md` con:

1. Tabla: acuerdo con trampa / sin trampa / después de mejorar.
2. Los patrones de falla y la regla que agregaste para cada uno.
3. Qué archivos tocaste y en qué líneas.
4. Qué quedó pendiente y por qué.

Corré al final: `node --check desktop/plugin.js`, `node tests/test_plugin.mjs`,
`python3 tests/test_invariants.py`, `hermes plugins validate .`, `python3 tools/check_publish.py`.

Avisame en una línea: acuerdo antes, acuerdo después, y cuántas reglas agregaste.

---

## Paso 6 · El aprendizaje se escribe en la documentación (obligatorio)

El ejercicio no termina con números: termina con **reglas escritas** para que los scripts sean
más inteligentes la próxima vez. Nada de lo que aprendas puede quedar solo en el código.

Actualizá, según lo que hayas medido:

| Documento | Qué agregar |
|---|---|
| `docs/ALGORITHM.md` | una sección **"What the teacher taught us"**: los patrones de falla medidos y la regla que resuelve cada uno, con el ejemplo real y el número de casos |
| `docs/VOCABULARY.md` | los casos de vocabulario que aparecieron (modelos sin marca, derivas de contexto, siglas) con su regla |
| `core/corrections.yaml` | cada regla nueva, con `id` estable, `rule`, `examples` y `control_question` — es lo que el clasificador lee |
| `docs/FEATURES.md` | si cambia el reparto de responsabilidades entre Process, New Rules y los scripts |

Regla de estilo: **una lección por regla, en imperativo, con el ejemplo que la prueba y sin
narrar el incidente**. Nada de "hoy descubrimos que…": la documentación describe cómo funciona,
no la crónica del día.

Criterio de aceptación: un lector que nunca vio esta sesión debe poder leer `ALGORITHM.md` y
entender **por qué** el sujeto se recorta así, **cuándo** se omite una sesión y **qué** la hace
no renombrable.

---

## CORRECCIÓN IMPORTANTE (del dueño, hoy): el maestro NO es todo el catálogo

La base actual **no está al 100 %**, no está mal. Es un catálogo trabajado durante meses: la
mayoría sirve como ejemplo y una minoría no cumple las reglas nuevas. **No es un catálogo roto y
no hay que tratarlo como tal.**

El dueño lo dijo **a ojo de cubero**: es una impresión, no una medición. Ninguna cifra suya se
usa como dato — la compuerta produce el número real y ese es el que vale.

Copiar todo sin mirar sería enseñarle al algoritmo a reproducir también esa minoría imperfecta;
descartar todo sería tirar el trabajo que ya está bien hecho. De ahí la compuerta del punto
siguiente: separar **lo que ya está fino** de **lo que se puede mejorar**.

### El maestro se parte en dos

| Conjunto | Qué es | Para qué se usa |
|---|---|---|
| **`teacher_good`** | solo las sesiones que **cumplen** las reglas nuevas | verdad de referencia: el acuerdo se mide **únicamente** contra éstas |
| **`teacher_bad`** | las que **rompen** alguna regla | contraejemplos: cada una enseña qué NO hacer y qué regla la corrige |

### La compuerta de calidad (una sesión entra a `teacher_good` solo si pasa todo)

1. `sujeto` de 1 a 3 palabras, sin verbo, sin frase, distinto de `Sin sujeto`.
2. `sujeto` ≠ `iq1` (una respuesta en dos campos).
3. Si hay `iq3`, es uno de los siete canónicos.
4. Si hay `iq2`, es tienda, país o máquina; si no lo es, la sesión va a `teacher_bad`.
5. El título no termina en conector (`de`, `en`, `y`, `o`, `con`, `para`).
6. No hay descripción duplicada dentro del título.

Cada sesión que falle se guarda con **el motivo**, no se descarta en silencio.

### Cómo cambia la medición

- El **acuerdo** se calcula contra `teacher_good`, nunca contra el catálogo entero.
- El informe debe decir el tamaño de cada conjunto: cuántas pasaron la compuerta y cuántas no,
  con el desglose de motivos.
- Las reglas que agregues tienen que **subir el acuerdo con `teacher_good`** y, al mismo tiempo,
  **corregir** las de `teacher_bad`. Una mejora que copia un error no es una mejora.

**Se espera que `teacher_good` sea la mayoría del catálogo.** Si queda chico, la compuerta está
demasiado estricta: revisá el criterio antes de reportarlo. El número tiene que ser creíble, no
un filtro que descarte por deporte: el objetivo es mejorar lo que falta, no rehacer lo que ya
está bien.
