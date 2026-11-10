# Alineación de reglas a la estructura nueva de filtros

Fecha: 2026-11-10 · base: 884 sesiones · 50 reglas · 13 intenciones

---

## 1 · La estructura, tal como quedó

| Tag | Eje | Responde | Ejemplo |
|---|---|---|---|
| **tag1** | **Marca** | ¿de quién es el sujeto? — un adjetivo | `DJI` |
| **tag2** | **Contexto** | ¿dónde o en qué marco? | `Amazon` · `Ebay` · `Panamá` |
| **tag3** | **Intención** | ¿qué quiso hacer el usuario? | `Comparar` |
| **tag4** | **Lugar** | país o tienda | `Panamá` · `Ebay` |
| **tag5** | **Tema** | el frente de trabajo | `IA Bot` · `VPS` |
| tag6 | Año | cuándo | `2026` |
| tag7 | Máquina | en qué equipo | `Mac mini M4` |

Y el título:

```
NNN [Sujeto] MMM [tag1] [tag2] [tag3] Descripción
```

> **tag2 y tag4 se solapan.** Los dos admiten `Ebay` y `Panamá`. Hay que
> decidirlo antes de escribir nada: o **tag4 es el lugar** y tag2 queda para
> contexto no geográfico, o **se fusionan** y el país y la tienda viven juntos.
> Recomiendo la primera: `tag4 = Ebay`, `tag2 = "comparación de precios"`.

---

## 2 · «Automation» no es una intención

Tenías razón en desconfiar. Medido:

```
Automation: 98 sesiones
  ├─ 67 son cron            (el usuario no las pidió: se programaron antes)
  └─ 31 son "encender el gateway", "configurar el bot"  → Instalar / Administrar
```

**Automation describe la ausencia de intención**, no una intención. Una tarea
automática es una tarea que el usuario **ya no hace**. Ponerla como Tag3 sería
como poner «ya está hecho» en la columna de lo que quiso hacer.

**Qué hacer con esas 98:**

| Grupo | Cuántas | Tag3 correcto |
|---|---|---|
| Vigilan algo periódicamente | 67 | **`Monitorear`** |
| Encienden o configuran un servicio | ~23 | **`Administrar`** |
| Las demás | ~8 | según su descripción |

`Monitorear` sí es una intención: alguien decidió que eso había que vigilarlo.
Y marca una diferencia útil en el filtro — «lo que hice» contra «lo que corre
solo».

**Propuesta:** retirar `Automation` del vocabulario de Tag3 y añadir
`Monitorear`. El hecho de que sea cron ya lo dice el id de la sesión.

---

## 3 · La medición de tag5

Con los nombres que diste, mapeando los pilares actuales:

| Subcategoría | Sesiones | % del total |
|---|---|---|
| **IA Bot** | 316 | 36 % |
| **VPS** | 187 | 21 % |
| **Data Backup** | 76 | 9 % |
| **Hardware** | 69 | 8 % |
| **MindMap** | 33 | 4 % |
| **IT Manager** (sin subcategoría) | 0 | — |
| **Network** | 13 | 1,5 % |
| **OS** | 27 | 3 % |
| **Total IT Manager** | **681** | **77 %** |

### El problema de Network y OS

Esas dos no son pilares de hoy: son **cortes transversales**.

```
Network = las 13 sesiones con tag2 "Networking"
OS      = las 27 sesiones con tag2 "File System"
```

Pero esas sesiones ya viven dentro de VPS, Data Backup o IA Bot. Si Network y OS
suben a subcategoría, **hay que decidir si se mueven o se copian**:

- **Si se mueven:** VPS baja de 187 a ~180, Data Backup baja, y Network/OS suben.
  Cada sesión en un solo sitio. **Recomendado.**
- **Si se copian:** una sesión viviría en dos subcategorías. El filtro deja de
  ser exclusivo y los conteos suman más que el total — el mismo problema del
  slice que arreglamos hoy.

### El problema de fondo: 77 %

IT Manager se come tres cuartos del catálogo. Con esas siete subcategorías,
`IA Bot` sola tiene 316 — más que las otras seis juntas.

**Dos lecturas posibles:**

1. **Es correcto:** tu trabajo *es* IT. El catálogo refleja tu vida, y tu vida es
   esta. Las siete subcategorías bastan para navegar.
2. **Falta un nivel:** `IA Bot` con 316 es lo que era `Asistente IA` — el cajón
   de todo lo que toca Hermes. Necesita partirse: *el asistente* (voz, modelos,
   gateway), *el plugin* (este proyecto), *las skills*, *las pruebas*.

Yo me inclino por la 2, pero **es tu llamada**: tú sabes si esas 316 sesiones se
sienten como una cosa o como cinco.

---

## 4 · Las 203 sesiones que quedan fuera de IT Manager

| Pilar actual | Sesiones | ¿Qué tema es? |
|---|---|---|
| Derecho | 61 | falta declararlo |
| Temas Varios | 43 | es la lista de espera |
| Compras | 41 | falta declararlo |
| Youtuber | 33 | falta declararlo |
| Geopolítica | 18 | falta declararlo |
| Masoterapia | 7 | falta declararlo |

Solo nombraste IT Manager como tema. **Los otros cinco siguen sin tag5** — y son
203 sesiones, el 23 % del catálogo.

---

## 5 · Las 50 reglas, una por una

### 5.1 · Reglas que NO cambian (siguen válidas tal cual) — 31

Estas hablan del **sujeto**, y el sujeto no se movió:

`subject-is-a-point-not-a-sentence` · `subject-never-carries-the-action` ·
`subject-strips-action-prefix` · `subject-does-not-repeat-tag1` ·
`subject-is-never-the-program` · `one-subject-only` ·
`qualifier-is-not-identity` · `subject-is-the-nearest-item` ·
`spelling-variants-are-one-subject` · `one-series-one-pillar` ·
`verb-first-then-subject` · `subject-preposition-exception` ·
`ventana-permisos-series` · `lisa-is-the-subject` ·
`third-party-program-is-tag1-not-subject` · `brand-equals-subject-exception` ·
`brand-and-product-are-two-things` · `brand-of-a-program-comes-from-its-site` ·
`brand-never-in-subject` · `closest-item-wins-in-compatibility` ·
y las once de series, fechas y formato.

### 5.2 · Reglas que CAMBIAN de destino — 4

| Regla | Antes | Ahora |
|---|---|---|
| `tag2-carries-the-intent` | la intención iba en **tag2** | va en **tag3** |
| `intent-not-topic` | «tag2 es el verbo» | «**tag3** es el verbo» |
| `two-layers-actors-then-intent` | resolvía tag1 + tag2 | resuelve tag1 + **tag3** |
| `python-decides-llm-investigates` | igual, pero el destino es tag3 | sin cambio de fondo |

**Y una consecuencia grande:** las 79 sesiones que corregimos ayer moviendo la
intención a tag2 **tienen que moverse otra vez a tag3**. Ese trabajo no se
pierde — el valor es el correcto — pero el campo cambia de sitio.

### 5.3 · Reglas nuevas que hacen falta — 5

**`tag1-is-an-adjective`**
> Tag1 califica al sujeto, no lo nombra. `DJI` califica a `Air 2S`; `DJI Avata 360`
> no califica nada, es un adjetivo con el sustantivo pegado.

**`place-not-platform`**
> Un país o una tienda nunca es Tag1. `Amazon` en Tag1 dice «esto trata de
> Amazon»; en Tag4 dice «lo compré en Amazon». La segunda frase es la útil.

**`intent-is-what-the-user-did`**
> Tag3 es un verbo en infinitivo que el usuario reconocería como suyo. Si no
> existe en la lista de 13, se usa `Investigar` — nunca se inventa uno nuevo.

**`automation-is-not-an-intent`**
> Una tarea programada no expresa lo que el usuario quiso: expresa lo que ya
> decidió antes. Va a `Monitorear`, y el id de la sesión ya dice que es cron.

**`one-session-one-theme`**
> Tag5 admite una sola subcategoría. Si una sesión cae en dos, la subcategoría
> está mal delimitada, no la sesión.

### 5.4 · Reglas que mueren — 2

**`productos-vs-compras`** — la distinción desaparece. `Productos` pasa a ser la
subcategoría `Hardware`, y `Compras` deja de ser pilar: comprar es una
**intención** (`Cotizar`) más un **lugar** (`Amazon`).

**`one-series-one-pillar`** — se queda en el fondo, pero cambia de nombre a
`one-series-one-theme`: la serie comparte **tag5**, no pilar.

### 5.5 · El resultado

```
50 reglas
 ├─ 31 intactas
 ├─  4 cambian de campo (tag2 → tag3)
 ├─  5 nuevas
 ├─  2 mueren o se renombran
 └─  8 pendientes de decisión (abajo)
```

---

## 6 · Lo que hay que decidir antes de migrar

1. **¿tag2 y tag4 se solapan?** Los dos admiten `Ebay`. O se especializan
   (tag2 = marco, tag4 = lugar) o se fusionan.
2. **¿Network y OS se mueven o se copian** de VPS y Data Backup?
3. **¿IA Bot con 316 se parte** en asistente / plugin / skills / pruebas?
4. **¿Qué tag5 llevan Derecho, Compras, Youtuber, Geopolítica y Masoterapia?**
   Son 203 sesiones sin tema.
5. **¿`Monitorear` entra** en el vocabulario de Tag3 y sale `Automation`?
6. **¿Las 79 correcciones de ayer se mudan a tag3** en la misma corrida?

---

## 7 · Orden de la migración, cuando esté decidido

```
1. declarar los tag5 que faltan (Derecho, Compras, Youtuber, Geopolítica, Medicina)
2. mover la intención de tag2 → tag3 en las 884
3. retirar Automation, añadir Monitorear, reclasificar sus 98
4. llenar tag4 (lugar) desde la batería: Amazon, Ebay, Panamá
5. limpiar las 303 sesiones con tag1 = "Hermes Agent"
6. medir en el simulador antes de escribir
7. aplicar con backup
```

Cada paso se puede medir en seco antes de tocar la base. **Ninguno se aplica sin
haberse visto en el simulador.**
