# Brand → context

Which iq2 a brand produces. This is the bridge that makes rule 1 of the vocabulary possible:
**a model is never written alone** — the brand gives it a name, and the brand gives it a device
context.

Order of resolution: `model → brand → product line → context (iq2)`.

---

## 1. The table

| Brand | Product line / model | Context (iq2) | Notes |
|---|---|---|---|
| **Apple** | Mac mini, Mac Studio, iMac | `Desktop` | Apple Silicon; unified memory |
| | MacBook Air, MacBook Pro | `Laptop` | |
| | iPhone | `iPhone` | **not** `Celular Android` |
| | iPad | `iPad` | tablet |
| | Apple Watch | `Smartwatch` | |
| | AirPods | `Audífonos` | |
| **Lenovo** | ThinkPad, IdeaPad, Legion | `Laptop` | ThinkPad P53, T480s, X1 Carbon |
| | ThinkCentre, ThinkStation | `Desktop` | |
| | ThinkVision | `Monitor` | |
| | Tab | `Tablet` | Android |
| | ThinkSystem | `Servidor` | |
| **Dell** | XPS, Inspiron, Latitude, Alienware | `Laptop` | the usual alternative when Lenovo is expensive |
| | OptiPlex, Alienware desktop | `Desktop` | |
| | UltraSharp | `Monitor` | |
| | PowerEdge | `Servidor` | |
| **HP** | Pavilion, OMEN, EliteBook | `Laptop` | |
| | EliteDesk | `Desktop` | |
| | ProLiant | `Servidor` | |
| | LaserJet | `Impresora` | |
| **ASUS** | Zenbook, ROG, TUF | `Laptop` | |
| | ProArt, ROG Swift | `Monitor` | |
| **Framework** | Framework Desktop | `Desktop` | the Ryzen AI Max machine |
| | Framework Laptop 13 / 16 | `Laptop` | repairable, modular |
| **Samsung** | Galaxy S / A (A55) | `Celular Android` | model needs the brand to mean anything |
| | Galaxy Tab | `Tablet` | |
| | Galaxy Watch | `Smartwatch` | |
| | 9100 PRO, 990 PRO | `Disco` | SSD |
| | Odyssey | `Monitor` | |
| **Google** | Pixel | `Celular Android` | |
| | ChromeOS | `Sistema Operativo` | |
| | Gemini | `Modelo IA` | |
| **AMD** | Ryzen, Ryzen AI Max (Gorgon Halo) | `Desktop` / `APU` | unified memory; the Framework Desktop chip |
| | Radeon | `Tarjeta Gráfica` | |
| | EPYC | `Servidor` | |
| **Nvidia** | GeForce RTX | `Tarjeta Gráfica` | |
| | RTX A / Quadro | `Tarjeta Gráfica` | professional |
| | Jetson | `SBC` | edge |
| | Turing T1000 | `Tarjeta Gráfica` | model alone is a fragment |
| **DJI** | Avata 360, Air 2S, Mavic, Mini | `Drone` | |
| | Osmo, Ronin | `Estabilizador` | gimbal |
| | Mic | `Audio` | |
| | Pocket | `Cámara` | |
| **Insta360** | X3, X4, X5 | `Cámara 360` | |
| | Ace Pro | `Cámara de acción` | |
| | Flow | `Estabilizador` | |
| **Microsoft** | Surface Pro, Surface Laptop | `Laptop` / `Tablet` | depends on the mode being discussed |
| | Windows | `Sistema Operativo` | |
| | Xbox | `Consola` | |
| **ORICO** | case, dock, enclosure | `Almacenamiento` | |
| **Anker** | charger, power bank | `Accesorio` | |
| **Xerox** | VersaLink, WorkCentre | `Impresora` | |
| **Synology / QNAP** | DiskStation, NAS | `NAS` | |
| **CyberPersons** | CyberPanel | `VPS` | the panel lives on the server |
| **Nous Research** | Hermes Agent, Hermes Desktop | `Programa` | maker, not a device |
| **DeepSeek** | V4 Flash, V4 | `Modelo IA` | |
| **Backblaze** | backup | `Servicio` | |
| **Ubiquiti / MikroTik** | UniFi, RouterOS | `Red` | |

---

## 2. The rules this table exists to serve

1. **A model resolves in two hops.** `A55` → `Samsung` → `Celular Android`. Neither hop is
   optional: without the first it is a number, without the second it is a number with a logo.
2. **A brand with several contexts needs the product to choose.** `Apple` alone says nothing;
   `Apple · Mac mini M4` says `Desktop`; `Apple · iPhone` says `iPhone`.
3. **A brand as a whole leaves iq1 empty.** It is the one documented exception: the maker of a
   brand is the brand, and the same word in two fields is the only thing that is always an error.
4. **The Apple ecosystem and the Android ecosystem never share a context.** `iPhone` is not
   `Celular Android`; `iPad` is not `Tablet` by default. When the context list has one side, the
   other side must exist too, or the filter lies.
5. **A brand without a product and without a context is a session about the brand**: strategy,
   catalogue, whether to stay with it. That is `Buy`/`Web Search` with iq1 empty, and it is
   legitimate.

---

## 3. Where the brand stops being useful

Not every brand deserves a context. If the session is about the **company** (a purchase
decision, a reputation, a supplier), the brand is the subject and the context is where it
operates:

| Session | iq0 | iq1 | iq2 |
|---|---|---|---|
| "los precios de Lenovo están altos" | `Lenovo` | `—` | `—` |
| "Lenovo ThinkPad P53 usada" | `ThinkPad P53` | `Lenovo` | `Laptop` |
| "comparar la GPU de una Lenovo con una Dell" | `Tarjeta Gráfica` | `Lenovo` | `Laptop` |
| "comprar en (tu forwarder)" | `(tu forwarder)` | `Forwarder` | `Miami` |

The third row is the one that matters: the session is not about a laptop, it is about a **part**
that happens to live inside two brands. The chain `producto → parte → producto alternativo` comes
from the vocabulary, not from the model's imagination.
