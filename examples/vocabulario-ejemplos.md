# Vocabulary examples

The plugin ships with **examples**, not with opinions. Every entry below is a shape you can
copy, edit or throw away: a brand is a name with its lines, a program is a name with its maker,
a product is a generic object that hangs from a brand.

Replace them with your own world in `~/.hermes/plugin-data/make-it-smart/vocab.personal.yaml`.
What stays here is the format.

> Rule that governs all of it: **a model never travels alone.** `A55` is a number; `A55 ·
> Samsung · Celular Android` is a filter.

---

## 1. Brand

A brand is a name, the lines it sells under, and whether the line stays inside the subject.

```yaml
marcas:
  lenovo:
    iq1: Lenovo
    strip: false          # the line stays in the subject: "ThinkPad P53", not "P53"
    lineas: [ThinkPad, ThinkCentre, Legion, IdeaPad]
    nota: ThinkPad is the LINE, not the brand.
```

| Brand | Lines | Notes |
|---|---|---|
| **Apple** | Mac mini, Mac Studio, iMac, MacBook, iPhone, iPad, Watch | the line decides the context: Desktop, Laptop, iPhone, iPad, Smartwatch |
| **Lenovo** | ThinkPad, ThinkCentre, ThinkVision, Legion | ThinkPad is the line; the subject keeps it |
| **Dell** | XPS, Latitude, Inspiron, OptiPlex, UltraSharp, Alienware, PowerEdge | the usual alternative when Lenovo is expensive |
| **Samsung** | Galaxy, 9100 PRO, 990 PRO, Odyssey | phones, disks and monitors under one name |
| **Nvidia** | GeForce RTX, RTX A, Quadro, Jetson | always a GPU, always the same context |
| **AMD** | Ryzen, Ryzen AI Max, Radeon, EPYC | CPU, APU, GPU and server — four contexts |
| **DJI** | Avata, Air, Mavic, Mini, Osmo, Ronin | drone, gimbal, audio |

```yaml
  apple:
    iq1: Apple
    strip: false
    lineas: [Mac mini, Mac Studio, MacBook, iMac, iPhone, iPad, Watch]
  dell:
    iq1: Dell
    strip: false
    lineas: [XPS, Latitude, Inspiron, OptiPlex, UltraSharp, Alienware, PowerEdge]
```

**When `strip` is true**, the line is dropped from the subject and only the model remains:
`Cafetera Nespresso Vertuo` → subject `Vertuo`, brand `Nespresso`. **When it is false**, the
line stays, because it *is* the identity: `ThinkPad P53` is not `P53`.

---

## 2. Program

A program is a name with the maker behind it. That maker is what iq1 receives when the program
itself is the subject.

```yaml
programas:
  cyberpanel:
    marca: CyberPanel
    maker: CyberPersons      # the company
    nota: the panel the VPS runs
  pinokio:
    marca: Pinokio
    maker: cocktailpeanut     # a person, because there is no company
    licencia: MIT
    nota: no company behind it, so the author takes the seat
```

| Program | Maker (goes to iq1) | Notes |
|---|---|---|
| **Brave** | Brave Software | browser |
| **CyberPanel** | CyberPersons | VPS panel |
| **Logseq** | Logseq Inc | notes, local-first |
| **Ollama** | Ollama | local models |
| **ComfyUI** | Comfy Org | image generation |
| **HandBrake** | HandBrake | video transcoding |
| **DEVONthink** | DEVONtechnologies | document database |
| **curl** | Open Source | no company: the ecosystem takes the seat |

**The open-source case:** a project with no commercial parent gets its ecosystem in iq1
(`curl · Open Source`), never an obscure maintainer nobody would filter by. If it has a
foundation or a company, that name wins.

---

## 3. Product

A product is the generic object, and the brand is what makes it a subject.

```yaml
productos:
  teclado:
    forma: subject = the generic object, iq1 = brand, iq2 = model
    ejemplos:
      - {sujeto: Teclado, iq1: Steren, iq2: COM-6900}
      - {sujeto: Teclado, iq1: Logitech, iq2: MX Keys}
```

| Generic object | Brand | Model |
|---|---|---|
| Teclado | Steren, Logitech, Keychron | COM-6900, MX Keys |
| Disco | Samsung, Crucial, WD | 9100 PRO, T7 |
| Tarjeta Gráfica | Nvidia, AMD | RTX 4070, Radeon RX 7800 |
| Dron | DJI, Autel | Avata 360, Air 2S |
| Case USB | ORICO, Ugreen | — |

---

## 4. Company

The company carries its trade. The **type** is what gets shared between users; the name is not.

```yaml
companias:
  mi_forwarder:
    nombre: "(tu forwarder)"
    tipo: Forwarder          # the shareable part
    contexto: Miami
```

| Type | What it does |
|---|---|
| `Forwarder` | receives in the US and ships to you |
| `Marketplace` | sells what others make (Amazon, eBay) |
| `Retailer` | sells its own stock (Best Buy, Newegg) |
| `Manufacturer` | makes the product (Apple, Dell, Lenovo) |
| `Hosting` | rents servers or panels |
| `Backup` | stores copies of your data |
| `Carrier` | moves the parcel (DHL, FedEx, UPS) |

---

## 5. Copy this and start

```bash
cp examples/vocab-personal.ejemplo.yaml \
   ~/.hermes/plugin-data/make-it-smart/vocab.personal.yaml
```

Then, in order:

1. Replace the brands you do not use. Keep three.
2. Add the models you actually own, each under its brand.
3. Write your companies with their type.
4. Leave the synonyms that match how you speak.

**Nothing here is published.** Your `vocab.personal.yaml` lives outside the repository, and
`tools/check_publish.py` refuses to publish anything that contains your names.
