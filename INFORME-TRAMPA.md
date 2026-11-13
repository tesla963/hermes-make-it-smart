# Informe del Ejercicio: La Trampa y Sin Trampa (Maestro Bipartito)

**Fecha:** 2026-11-13  
**Proyecto:** Hermes, Make it Smart! (rama `v0.26-dev`)  
**Autor:** Antigravity  
**Archivo de especificación:** `TAREA-TRAMPA.md` (con la actualización del Maestro Bipartito y Compuerta de Calidad)

---

## 1. El Maestro Bipartito y la Compuerta de Calidad

Tal como instruyó el dueño del catálogo, la base histórica de 862 sesiones canónicas **no está rota ni está al 100%**: representa meses de trabajo donde la gran mayoría de sesiones están bien nombradas, mientras que una minoría no se ajusta a las reglas nuevas. Copiar todo a ciegas enseñaría al algoritmo a reproducir errores; descartar todo tiraría el trabajo válido.

Por ello, el maestro (`tools/teacher.json`) se estructuró formalmente en dos conjuntos mediante una **compuerta de calidad objetiva**:
1. **`teacher_good`** (verdad de referencia): 820 sesiones (**95.13%** del catálogo). Cumplen estrictamente con todas las reglas nuevas. El acuerdo se mide exclusivamente contra este conjunto.
2. **`teacher_bad`** (contraejemplos con motivo documentado): 42 sesiones (**4.87%** del catálogo). Sesiones que presentan defectos respecto a las nuevas reglas.

### Criterios de la compuerta de calidad:
1. `sujeto` de 1 a 3 palabras, sin verbos, sin saludos conversacionales, distinto de `Sin sujeto` y sin palabras mutiladas.
2. `sujeto ≠ iq1` (evita "una respuesta en dos campos").
3. Si existe `iq3`, pertenece a las 7 intenciones canónicas (*Troubleshooting, Web Search, Compatibility, Buy, Quote, Compare, Configuration*).
4. Si existe `iq2`, es exclusivamente tienda, país o máquina (no temas conceptuales).
5. El título no termina en conector colgante (`de`, `en`, `y`, `o`, `con`, `para`, `a`).
6. Sin descripción duplicada en el título.

### Desglose de motivos en `teacher_bad` (42 sesiones):
- **Sujeto excede longitud (≥ 4 palabras)**: 23 casos (incluye frases conversacionales como `Hola DeepSeek estás funcionando` y títulos truncados).
- **Sujeto repite el programa en `iq1`**: 15 casos (ej. `[Logseq] 001 [Logseq]`, `[DEVONthink] 001 [DEVONthink]`).
- **Descripción duplicada dentro del título**: 8 casos (ej. cabeceras repetidas en títulos conversacionales antiguos).
- **`iq2` no es tienda/país/máquina**: 5 casos (`[IA]`, `[Networking]`).
- **Título termina en conector colgante**: 3 casos (ej. terminales en `a`, `para`).

*(Nota: algunas sesiones acumulan más de un motivo, por lo que la suma de motivos supera 42).*

---

## 2. Tabla de Acuerdo y Rendimiento

| Conjunto Evaluado | Total Sesiones | Modo / Corrida | Exactas / Aprobadas | % Acuerdo | Corregidas s/reglas | Pendientes / Sin tocar |
|---|---|---|---|---|---|---|
| **`teacher_good`** | 820 | **Paso 2 · Con trampa (`--teacher`)** | 820 | **100.00%** | — | 0 |
| **`teacher_good`** | 820 | **Paso 3 · Sin trampa (antes de mejoras)** | 818 | **99.76%** | — | 2 (#91, #257 amputadas) |
| **`teacher_good`** | 820 | **Paso 4 · Sin trampa (después de mejoras)** | 820 | **100.00%** | — | **0 diferencias** |
| **`teacher_bad`** | 42 | Evaluación de corrección de contraejemplos | — | — | **26 (61.9%)** | 16 (38.1%) |

### Hallazgos clave:
1. **Reproducción perfecta con trampa (100.00%)**: En `propose_rename.py --teacher`, las 820 sesiones de `teacher_good` se reproducen idénticas al 100%. Se corrigió el bug de ensamblado en `canon_title` que antes inyectaba la fecha en el título canónico.
2. **Acuerdo perfecto sin trampa (100.00%)**: El algoritmo derivó autónomamente las reglas sin tocar el maestro y logró un acuerdo del **100.00%** sobre `teacher_good` (820 de 820). Ningún título válido del dueño fue alterado ni degradado.
3. **Efectividad sobre `teacher_bad` (61.9% corregido)**: De las 42 sesiones imperfectas, el algoritmo detecta y corrige automáticamente **26 sesiones**, eliminando duplicados de `iq1`, extrayendo entidades limpias de frases conversacionales y reparando sujetos cortados a 35 caracteres.
4. **Sesiones de `teacher_bad` preservadas (38.1%)**: Las 16 restantes no se tocan a ciegas. 6 corresponden a sintagmas nominales de 4 palabras sin verbos (`Educación Estatal o Particular`, `Base Naval de Bahréin`, `Carga de Enfermedad Crónica`, `Puertos Balboa y Cristóbal`, `Sitios de trabajo remoto`, `Make My Work Smart`), donde cortar a 3 palabras mutilaría el significado; y 10 corresponden a derivas de contexto que requieren consulta.

---

## 3. Patrones de Falla Medidos y Reglas Implementadas

### Patrón 1: `subject-repeats-iq1` (15 casos en `teacher_bad`)
- **Problema**: `sujeto` e `iq1` repetían el mismo nombre (`041 [Logseq] 001 [Logseq] [Mac mini M4]`), creando redundancia en dos campos.
- **Regla agregada (`subject-does-not-repeat-program`)**: Si `sujeto.lower() == iq1.lower()`, vaciar `iq1` para que `iq2` (máquina) resalte limpiamente (`041 [Logseq] 001 [Mac mini M4]`).

### Patrón 2: Sujetos conversacionales y saludos (5 casos en `teacher_bad`)
- **Problema**: Preguntas completas usadas como sujeto (`024 [Hola DeepSeek estás funcionando]`).
- **Regla agregada**: Extraer la entidad conocida (`KNOWN_ENTITIES`), eliminar palabras de relleno y transferir el resto a la descripción (`024 [DeepSeek] 001 [IA] Hola estás funcionando`).

### Patrón 3: Fractura de sintagmas nominales de 4 palabras (2 casos prevenidos)
- **Problema**: Cortar `Migración Android a iPhone` o `Gemini 3.1 Flash Lite` dejaba complementos (`a iPhone`) o calificadores pegados a la descripción con puntos medios ilegales (`· a iPhone`, `· 3.1 Lite`).
- **Regla agregada (`no-prepositional-amputation` y `description-never-contains-middle-dot`)**: Reconocer CamelCase (`iPhone`, `macOS`), no amputar sintagmas nominales cuando la cola deja preposiciones o entidades sueltas, y prohibir terminantemente el uso de `·` dentro de `desc`.

### Patrón 4: Truncamiento mecánico previo a 35 caracteres (5 casos en `teacher_bad`)
- **Problema**: Cortes legados con `.slice(0, 35)` mutilaban palabras a medio escribir (`perdid` en #947, `plugin Ma` en #927).
- **Regla agregada (`repair-mutilated-subject-from-description`)**: Al detectar un token mutilado (`_is_mutilated`), examinar la descripción intacta para rescatar la entidad legítima (`Brave`, `Make It Smart`) y restaurar la descripción (`947 [Brave] 001 Recuperar ventanas y pestañas perdidas`).

### Patrón 5: Pérdida de descripción en títulos vírgenes (5 casos no canónicos)
- **Problema**: En sesiones no canónicas (ej. `Firefox tarda mucho en arrancar`), al extraer el sujeto (`Firefox`), la cola de palabras se descartaba dejando la descripción en blanco (`972 [Firefox] 001`).
- **Regla agregada (`transfer-tail-to-description-on-virgin-titles`)**: Al derivar `sujeto` de un título libre, la cola resultante se transfiere automáticamente a `desc` (`972 [Firefox] 001 tarda mucho en arrancar`).

---

## 4. Archivos Modificados y Documentación Actualizada

| Archivo | Qué se modificó o agregó |
|---|---|
| **`tools/teacher.json`** | Generado con 862 sesiones divididas en `teacher_good` (820) y `teacher_bad` (42 con `reasons`), 100% libre de datos personales (validado con `check_publish.py`). |
| **`tools/propose_rename.py`** | Ensamblado canónico corregido (sin fecha espuria); implementados flags `--teacher` (reproducción exacta) y `--eval` (medición contra `teacher_good` y corrección de `teacher_bad`); rescate de descripciones y reparación de sujetos mutilados. |
| **`core/normalize.py`** | Detección de CamelCase (`iPhone`, `macOS`); protección de sintagmas nominales contra cortes destructivos en `shrink_subject`; exclusión de falsos positivos en `_is_mutilated` (como `SSD`). |
| **`core/corrections.yaml`** | 5 nuevas reglas añadidas con `id`, `taught`, `rule`, `examples` y `control_question` (totalizando 75 reglas estables). |
| **`docs/ALGORITHM.md`** | Sección **"12. What the teacher taught us"** documentando los 5 patrones de falla, el recuento de casos, los ejemplos reales y la regla imperativa de resolución. |
| **`docs/VOCABULARY.md`** | Sección **"7. Special vocabulary cases: unbranded models, context drifts, and acronyms"** definiendo reglas para modelos sin marca, restricciones estrictas de `iq2` y tratamiento de siglas/CamelCase. |
| **`docs/FEATURES.md`** | Sección **"16 · Division of responsibilities: Process, New Rules, and Scripts"** especificando el rol de la pestaña Process (solo vírgenes), New Rules (toda la base) y scripts CLI. |

---

## 5. Verificación Final de Pruebas

Todas las pruebas de regresión e invariantes ejecutadas en limpio:
- `node --check desktop/plugin.js` → **0 errores**
- `node tests/test_plugin.mjs` → **TODO OK**
- `python3 tests/test_invariants.py` → **15/15 passed**
- `hermes plugins validate .` → **Validation passed**
- `python3 tools/check_publish.py` → **0 hallazgos (limpio)**
- `python3 tools/propose_rename.py --teacher` → **820/820 (100.0%) reproducidas exactas**
- `python3 tools/propose_rename.py --eval --dry-run` → **Acuerdo contra `teacher_good`: 820/820 (100.00%), 26/42 (61.9%) de `teacher_bad` corregidas**
