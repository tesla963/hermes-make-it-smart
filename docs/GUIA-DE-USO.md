# Guía de uso — Hermes, make all my work Smart!

Esta guía es para el usuario, no para el programador. Cuenta **en qué orden**
hacer las cosas para que el plugin trabaje bien, y por qué ese orden importa.

---

## Antes de tocar nada: haz un respaldo

El plugin **renombra tus sesiones**. Renombrar no borra nada —los mensajes, los
costos y las fechas siguen intactos— pero un nombre es la única forma de
reconocer una sesión seis meses después. Si algo sale mal, quieres poder volver.

```bash
cp -a ~/.hermes/state.db \
      ~/state.db.backup-$(date +%Y%m%d-%H%M)
```

Y si tienes más de un perfil:

```bash
for f in ~/.hermes/profiles/*/state.db; do
  cp -a "$f" "$f.backup-$(date +%Y%m%d-%H%M)"
done
```

El plugin hace su propio respaldo antes de escribir, en
`/Volumes/<tu disco>/Backups-Lisa/<fecha>_<motivo>/`. **Pero no confíes solo en
él**: tu respaldo es el que sabes dónde está.

> Con el tiempo vas a querer versionar los nombres, no la base. Un archivo
> `titulos.txt` con una línea `id<TAB>titulo` es todo lo que hace falta para
> reconstruir el catálogo sin volver a clasificar nada.

---

## Paso 1 · Mira antes de escribir: el simulador

El plugin genera un **simulador en HTML** — un archivo único que se abre en el
navegador, sin servidor y sin conexión.

```
~/Documents/Reportes - [Lisa]/<fecha>/<fecha>_simulador-plugin-bodega-de-sesiones.html
```

Ahí ves **las 884 sesiones tal como quedarían**, con sus filtros, su buscador y
su ficha. Y lo más importante: **no escribe nada**.

| En el simulador puedes | Sin riesgo porque |
|---|---|
| filtrar por pilar, plataforma, familia | es una copia de lectura |
| buscar por número (`126,305`, `50-75`) | no toca la base |
| revisar la intención de cada sesión | no renombra |
| exportar un CSV de correcciones | el archivo es tuyo |

**Esta es la parte que hace que el plugin sea seguro.** El simulador y la app
leen exactamente el mismo índice; si algo se ve mal ahí, se verá mal en la app.
Pero corregirlo es una decisión tuya, no un efecto secundario.

Regla práctica: **ninguna corrección entra a la base sin haberse visto antes en
el simulador.**

---

## Paso 2 · Los pilares: lo primero que hay que definir

Un pilar es **el frente de trabajo al que pertenece una sesión**: Asistente IA,
VPS, Data Backup, Derecho, Productos, Compras, Youtuber, MindMap, Geopolítica,
Masoterapia.

Es el filtro que más veces vas a usar, y **es el que el plugin no puede adivinar
por ti**. Un modelo puede decir «esto trata de servidores»; solo tú sabes si en
tu mundo eso es *VPS* o es *WebHosting* o es *Infraestructura*.

### Cómo se definen

En `core/taxonomy.py`, la lista `PILLARS`. Cada uno con:

```python
{"name": "VPS", "hint": "el servidor propio: CyberPanel, DNS, correo, certificados"}
```

El `hint` no es decoración: **es lo que lee el clasificador para decidir**. Un
pilar con un hint vago («temas técnicos») atrae medio catálogo y arruina el
filtro. Un pilar con un límite claro («el servidor propio: …») se queda con lo
suyo.

### Las tres preguntas para saber si un pilar está bien

1. **¿Podrías decir en una frase qué NO es?** Si no, es un cajón de sastre.
2. **¿Tiene al menos cinco sesiones?** Un pilar con una sola sesión es una
   etiqueta, no un frente.
3. **¿Cada sesión cae en uno y solo uno?** Si dos pilares se pelean la misma
   sesión, sus límites no están escritos.

> El error más común es crear un pilar por cada tema que aparece. El resultado
> son veinte pilares con tres sesiones cada uno, y ninguno sirve para navegar.
> **Es mejor un pilar menos y bien delimitado.**

### Cuando dudes, no inventes: usa «Temas Varios»

Es el cajón honesto de lo que todavía no tiene frente propio. **No es un
fracaso**: es una lista de espera que te dice qué pilares te faltan. Cuando
«Temas Varios» llegue a veinte sesiones sobre lo mismo, ahí nace el pilar.

---

## Paso 3 · La batería: el diccionario que hace al plugin tuyo

`core/bateria.yaml` es lo que el plugin sabe de **tu** mundo. No es código: es
una lista de nombres con su contexto.

```yaml
marcas:
  dji:
    tag1: DJI
    productos: [Air 2S, Avata 360, RC 2]
programas:
  devonthink:
    marca: DEVONthink
    maker: Devon Technologies
    sitio: https://www.devontechnologies.com/
```

**Por qué esto es lo que más rinde:** cada nombre que agregas es una sesión
futura que el plugin resuelve **sin preguntarle a ningún modelo**. La batería es
la memoria del clasificador.

| Sin batería | Con batería |
|---|---|
| el modelo adivina si «Avata 360» es marca o producto | lo lee de la lista, gratis |
| «Devon Technologies» sale mal escrito cada vez | se escribe una vez, para siempre |
| cada sesión cuesta tokens | las conocidas cuestan cero |

### Reglas para escribirla bien

- **La marca va en Tag1, sola.** `Ground Advantage` es el producto; `USPS` es la
  marca. Nunca `USPS Ground Advantage` en el mismo campo.
- **La marca de un programa está en su sitio, no en su nombre.** `DEVONthink`
  es el programa; `devontechnologies.com` dice que la compañía es *Devon
  Technologies*.
- **Una línea por cosa.** Si dudas entre dos formas, escribe las dos en `alias`.
- **Nada de experiencia personal.** «Con este courier se pierden los paquetes»
  va en `bateria.personal.yaml`, que **no se publica**.

---

## Paso 4 · Corrige en el simulador, no en la base

El flujo es siempre el mismo:

```
mirar en el simulador  →  exportar el CSV  →  corregir  →  aplicar
```

El botón **Exportar** genera un CSV con una fila por sesión y columnas vacías
para lo que quieras cambiar:

```
n, id, fecha, titulo_actual, sujeto, tag1, tag2, descripcion,
sujeto_nuevo, tag1_nuevo, tag2_nuevo, descripcion_nueva, observaciones
```

Llenas solo lo que está mal y lo dejas volver. **Nada se aplica hasta que tú lo
pides.**

---

## Paso 5 · Aplica, y verifica

```bash
python3 tools/apply_protocol.py           # muestra qué cambiaría, no escribe
python3 tools/apply_protocol.py --apply   # respalda, escribe, relee
```

El primer comando **es el que usas el 90 % del tiempo**. Enseña la lista de
cambios propuestos con su motivo:

```
propuestas: 89 · sin cambio: 795

    2  tag2: IA → Instalar
       - 002 [Hermes Desktop] 001 [Hermes Agent] [IA] Instalar la app…
       + 002 [Hermes Desktop] 001 [Hermes Agent] [Instalar] Instalar la app…
```

Si algo no te gusta, no lo aplicas y ajustas la regla.

---

## Por qué entrenar el plugin importa tanto

El plugin **no sabe nada de tu vida al instalarse**. Sabe de software en
general, como cualquier modelo. Lo que lo vuelve útil es lo que tú le enseñas:

| Lo que le das | Lo que ganas |
|---|---|
| **pilares** | el filtro que de verdad usas |
| **batería** | sesiones resueltas sin gastar tokens |
| **correcciones** | las reglas que impiden repetir el error |
| **tus nombres** | el catálogo deja de sonar a máquina y suena a ti |

Y funciona así: **cada corrección se escribe como regla**, no como parche. La
sesión 369 salió mal porque el sujeto era el controlador y no la marca; de ahí
nació `subject-is-the-nearest-item`, y esa regla arregla las próximas cien antes
de que existan.

> **La forma más rápida de mejorar el plugin no es pedirle más inteligencia. Es
> darle más nombres.** Un archivo de batería bien cuidado hace más que un modelo
> más grande.

### La señal de que está entrenado

- Hay **pocas sesiones en «Temas Varios»** y las que hay son recientes.
- Los **Tag2 son verbos** (`Instalar`, `Testear`, `Cotizar`), no estantes
  (`Electronica`, `IA`).
- **Agregar una sesión nueva no requiere renombrar ninguna vieja.**
- El sujeto de una sesión **no repite la marca** ni lleva verbos.

Si esas cuatro cosas se cumplen, el plugin ya está trabajando solo.

---

## El orden, en una línea

```
respaldo → pilares → batería → simulador → correcciones → aplicar → repetir
```

Y el paso que nunca se salta: **mirar antes de escribir.**
