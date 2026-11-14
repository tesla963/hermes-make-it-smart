# Cómo trabajamos dos agentes en el mismo repositorio

Dos agentes (el asistente y Antigravity) editan el mismo código para el mismo dueño. Sin reglas, uno
pisa el trabajo del otro y el dueño paga el costo. Estas son las reglas, y son verificables.

---

## 1 · Un archivo, un dueño a la vez

- Antes de tocar un archivo, se **anuncia** en el chat: qué archivo, qué función, qué se va a
  cambiar.
- Si ese archivo o esa función la tocó el otro agente desde la última línea base, **no se toca**:
  se pide aprobación explícita y se espera la respuesta.
- Terminada la tarea, el archivo se **libera** (se dice "liberado") para que el otro pueda
  seguir.

## 2 · La hoja de entrega es obligatoria

Al final de cada tarea, cada agente corre:

```bash
python3 tools/delivery_sheet.py --check --json > entrega-<agente>-<fecha>.json
```

Ese archivo dice **exactamente** qué archivos cambiaron desde la línea base, con su hash antes y
después. Si un archivo no aparece en la hoja, no cambió. Si aparece y nadie lo declaró, es una
modificación silenciosa y se revierte.

La línea base la saca quien empieza una ronda:

```bash
python3 tools/delivery_sheet.py --snapshot --who "<agente>"
```

## 3 · Prohibido reescribir para cambiar un fragmento

Reescribir un archivo completo para modificar una función borra los cambios del otro agente sin
que nadie lo note. Se edita **por función**, y después se comprueba:

```bash
python3 tools/delivery_sheet.py --check
```

En esta sesión pasó exactamente eso: un parche preparado dejó de coincidir porque el otro agente
había reescrito la función, y el parche **falló en silencio**. La regla nace de ese error.

## 4 · Un parche que no aplica se informa, no se ignora

Si un reemplazo no encuentra su texto, **se dice en el reporte**: "el parche X no aplicó porque
la función cambió". Nunca se asume que aplicó. Un cambio que se cree hecho y no se hizo es peor
que un cambio que falta.

## 5 · Aprobación antes de aplicar, no después

El ciclo es: **propuesta → aprobación → aplicación**.

- El agente que propone entrega el diff y la hoja de entrega.
- El agente que revisa dice **aprobado** o **rechazado con motivo**.
- Recién entonces se aplica y se commitea.

Nadie commitea ni hace push del trabajo del otro sin su aprobación.

## 6 · Los datos del dueño no se tocan

`~/.hermes/plugin-data/`, las bases de `~/.hermes/` y cualquier archivo personal: **prohibido**
escribir, migrar o aplicar renombrados. Se leen si hace falta; se escriben solo cuando el dueño
lo pide, y con respaldo previo.

## 7 · Lo que el dueño corrige queda como prueba

Cada caso que el dueño marca como error se convierte en un test. Si la regla se rompe otra vez,
falla la suite antes que su ojo. Una corrección sin prueba es una corrección que va a volver.
