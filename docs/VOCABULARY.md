# The vocabulary system

A session name is only as smart as the dictionary behind it. This document defines what a
vocabulary term is, how the plugin finds it, and which part of that vocabulary the user owns.

**Read this with** [`ALGORITHM.md`](ALGORITHM.md) (the fields) and
[`BRAND-CONTEXT.md`](BRAND-CONTEXT.md) (which context each brand produces).

---

## 0. What we call things

| Concept | Español | English | Never |
|---|---|---|---|
| the dictionary the classifier reads | **batería** | **Cheat-Sheet** | "chuleta" |
| the file | `cheat_sheet.yaml` | `cheat_sheet.yaml` | `bateria.yaml` |

The Spanish word is **batería** (what a band plays; what you have ready). The English word is
**Cheat-Sheet**, with the hyphen. The code keeps `cheat_sheet` in snake_case because a file name
cannot have a hyphen.

## 1. What counts as a term

| Is a term | Is not a term |
|---|---|
| a brand: `AMD`, `Lenovo`, `DJI` | a greeting: `Hola DeepSeek` |
| a product or model **with its brand**: `Samsung A55` | a model alone: `A55`, `T1000` |
| a program: `Brave`, `CyberPanel` | a file name: `plugin.js`, `state.db` |
| a machine family: `ThinkPad`, `Mac mini` | a date or a year alone: `14-sep-2026` |
| an event with its year: `Nous Hackaton 2026` | a numeric range from a list: `56-110` |
| a capacity **being bought**: `16GB RAM` | a bare size: `27B`, `192GB` |
| a company with its trade: `(tu forwarder)` (Forwarder) | a personal identifier: a username, a phone number |

Five rules govern this, and each one exists because the catalogue broke without it:

1. **A model is never alone.** `A55` means nothing; `A55 · Samsung · Celular Android` is a
   filter. When the miner finds a model, it must look for its brand and its device context.
2. **One idea, one value.** `Portátil` → `Laptop`, `GPU` → `Tarjeta Gráfica`, `dron` → `Drone`.
   Two spellings of one thing are two filters nobody can see are the same.
3. **Sizes are attributes, not terms.** `27B` is a parameter of a model; `16GB RAM` is a
   configuration being compared. The test is whether the number is the subject or a property
   of the subject.
4. **Acronyms and file names are not subjects.** `DNS`, `API`, `IP`, `UI` alone are attributes;
   `plugin.js` is an implementation detail. The subject is the component that contains them.
5. **Companies carry their trade.** A company without what it does is a word.

---

## 2. Device families — the closed list

A device family is a value of iq2 (context). The list is closed so a phone never appears under
three different names, and it is **complete on both sides**: the Apple ecosystem and the
Android ecosystem live side by side, never one inside the other.

| Family | Members (brand → model) |
|---|---|
| `Celular Android` | Samsung Galaxy, Google Pixel, Xiaomi, OnePlus, Motorola |
| `iPhone` | iPhone SE, iPhone 15 Pro Max, iPhone Air |
| `iPad` | iPad, iPad Air, iPad Pro, iPad mini |
| `Tablet` | Galaxy Tab, Lenovo Tab, Surface Pro (tablet mode) |
| `Smartwatch` | Apple Watch (iWatch), Galaxy Watch, Band |
| `Laptop` | ThinkPad, MacBook, XPS, Latitude, Framework 13/16, Surface Laptop |
| `Desktop` | Mac mini, Mac Studio, iMac, ThinkCentre, OptiPlex, Framework Desktop |
| `Monitor` | UltraSharp, ThinkVision, Odyssey, ProArt |
| `Drone` | DJI Avata, Air, Mavic, Mini; Autel |
| `Tarjeta Gráfica` | Nvidia RTX, AMD Radeon, Intel Arc |
| `Disco` | Samsung 9100 PRO, Crucial, WD, Seagate |
| `NAS` | Synology, QNAP, TrueNAS |
| `Servidor` | VPS, PowerEdge, ProLiant, EPYC |
| `Impresora` | Xerox, HP LaserJet, Brother |

**The rule behind the list:** if `Celular Android` exists as a context, then `iPhone`, `iPad`
and `iWatch` must exist too. A vocabulary that only knows one ecosystem forces the other one
into the wrong filter — and the user notices immediately.

---

## 3. Company types — the shareable part

A specific company belongs to one person; **the type of company belongs to everyone.**
"(tu forwarder)" is useful only to its client. "Forwarder" is useful to any user who imports.

| Type | What it does | Known examples |
|---|---|---|
| `Forwarder` | receives in the US and ships to the user's country | (tu forwarder) (personal) |
| `Marketplace` | sells what others make | Amazon, eBay, Alibaba, AliExpress |
| `Retailer` | sells its own stock | Best Buy, Walmart, Newegg |
| `Manufacturer` | makes the product | Apple, Lenovo, DJI, Samsung, AMD, Nvidia |
| `Distributor` | sells to retailers, not to people | — |
| `Hosting` | rents servers or panels | CyberPersons, DigitalOcean, Vultr |
| `Backup` | stores copies of data | Backblaze, Time Machine, rsync.net |
| `Carrier` | moves the parcel | DHL, FedEx, UPS, Correos |
| `Repair` | fixes hardware | — |

So the shareable file ships the **types**, and the personal file ships the **names**.
That keeps the repository useful without exposing anybody's supplier.

---

## 4. The two files

| File | Lives in | Travels with the repo | What it holds |
|---|---|---|---|
| `core/cheat_sheet.yaml` | the repo | **yes** | what every user shares: brands, programs, company types, device families |
| `vocab.personal.yaml` | `~/.hermes/plugin-data/make-it-smart/` | **no** | the user's own brands, models, suppliers, people, places, events |

```yaml
# vocab.personal.yaml — the user's own world, editable by hand
companias:
  mi_forwarder: {nombre: (tu forwarder), tipo: Forwarder, contexto: Miami}
marcas:
  lenovo: {preferencia: 1, contexto: [Laptop, Desktop]}
  dell:   {preferencia: 2, contexto: [Laptop, Desktop]}
productos:
  thinkpad_p53: {marca: Lenovo, contexto: Laptop, parte: Tarjeta Gráfica}
personas:
  pareja: {nombre: the partner, relacion: pareja}
lugares:
  panama: {tipo: país}
eventos:
  nous_hackaton_2026: {tipo: hackathon, año: 2026}
sinonimos:
  portatil: Laptop
  gpu: Tarjeta Gráfica
```

### Preference chains

People do not shop by brand, they shop by **an order of brands** and a **reason to leave it**.
The file records that order, because it changes what a session is really about:

```yaml
preferencias:
  laptops:
    orden: [Lenovo, Dell, Apple]
    motivo_cambio: "cuando el precio del Lenovo es alto, buscar la misma parte en otra marca"
```

That is why a session about a Dell laptop can really be a session about a **Lenovo GPU price**.
The classifier reads the chain and files it accordingly: the subject is the part, the brands
are the context of the decision.

### Parts, and why they break the brand

A laptop part is rarely proprietary. When the whole machine is too expensive, the search moves
to the part — and the part lives inside another brand's machine:

```
Lenovo laptop (too expensive) → the GPU → same GPU in a Dell → the Dell laptop (cheaper)
```

The vocabulary records the chain `producto → parte → producto alternativo` so the plugin can
recognise the pattern instead of seeing three unrelated sessions.

---

## 5. How the plugin uses the vocabulary

```
title + first turns
        │
        ▼
condense_session.py      → strips the filler, protects names, units and verbs
        │
        ▼
extract_entities.py      → objects, brands, models, companies, people, places, events,
        │                  intention and context (deterministic first, model for the rest)
        ▼
model → brand → context  → a model without a brand is not written: it is completed
        │                  (A55 → Samsung; Samsung → Celular Android)
        ▼
narrow + wide pair       → iq0 is the narrow word, iq1 the wide one
```

---

## 6. What a user has to write, and what the plugin infers

| The user writes | The plugin infers |
|---|---|
| `Lenovo` in their brands | `ThinkPad` → Laptop, `ThinkCentre` → Desktop |
| `Apple` in their brands | iPhone → iPhone, Mac mini → Desktop, MacBook → Laptop |
| a company with `tipo: Forwarder` | the trade, the context city, the sessions that mention it |
| `A55` as a model of `Samsung` | the device family, from the brand's context list |

**The goal is that the user never types `Celular Android` next to `A55`.** They type the model
once, under its brand, and the context follows from [`BRAND-CONTEXT.md`](BRAND-CONTEXT.md).

---

## 7. Special vocabulary cases: unbranded models, context drifts, and acronyms

### 1 · Models without a brand (unbranded models)

Users frequently write a product model or component without mentioning the parent company (`COM-6900`, `3.1 Flash Lite`, `Avata 2`).

- **Rule**: A model number or tier name alone is never a standalone subject. It must be resolved to its commercial anchor (`Steren COM-6900`, `Gemini 3.1 Flash Lite`, `DJI Avata 2`). If the brand is known from the prompt, pair them together.

### 2 · Context drifts (store vs. machine vs. country)

`iq2` (Context) is strictly restricted to three mutually exclusive real-world anchors: **store**, **country**, or **machine**.

- **Rule**: Conceptual domains, themes, or software categories (e.g. `Networking`, `IA`, `Educación`) must never drift into `iq2`. If the session runs on the local computer, `iq2` takes the machine (`Mac mini M4`, `ThinkPad P53`); if it occurs in a physical market, `iq2` takes the country or platform (`Panamá`, `Amazon`, `VPS`).

### 3 · Acronyms and CamelCase tokens

Technical protocols (`SMTP`, `DMARC`, `DNS`, `CLI`, `MCP`) and CamelCase product names (`iPhone`, `macOS`, `iTerm`, `CyberPanel`) have specific structural behavior:

- **Rule**: Protocol acronyms are technical attributes belonging in the description unless the session's explicit purpose is configuring that exact protocol (e.g. `DMARC` in `#534`).
- **Rule**: CamelCase words with lowercase prefixes (`iPhone`, `macOS`, `iCloud`) are full proper nouns. Tokenizers and subject cutters must never treat their lowercase prefix as a common word, nor slice them into broken fragments.
