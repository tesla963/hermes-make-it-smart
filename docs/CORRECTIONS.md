# How the algorithm learns

> "Nuestro algoritmo no aprende nada nuevo." — the owner, 2026-11-08

He was right, and it is the most serious weakness the project had. This document is the
fix, written down so it cannot quietly regress.

A model does not learn from a conversation it will never see again. Neither does a rule
that lives only in someone's head. **A correction that is not written down is a
correction that will be made again.**

So every correction travels through four places, in this order:

```
   dictation  →  corrections.yaml  →  prompt (few-shot)  →  eval set (regression)
       ↑                                                        │
       └──────────────────  fails, so we fix  ←─────────────────┘
```

## 1. `core/corrections.yaml` — the record

One entry per rule the user taught, with the real examples that taught it.

```yaml
- id: product-marketplace-shape
  taught: 2026-11-09
  rule: >
    When the session is about evaluating a product, Iq1 is the brand and
    Iq2 is the marketplace.
  examples:
    - { nnn: 748, subject: "Air 2S", iq1: "DJI", iq2: "Ebay" }
    - { nnn: 812, subject: "Trace Minerals", iq1: "Dr. Berg", iq2: "Amazon" }
  control_question: "Does the axis tell me who makes it, or where we looked?"
```

Three fields, and nothing is lost: the rule, the evidence, and the question to ask when
the rule does not obviously apply.

## 2. The prompt — few-shot evidence

`core/prompt.py` renders every correction into the classifier's system prompt as a worked
example, not as an instruction. Examples beat instructions: a model obeys "be specific"
inconsistently, but it imitates a shape.

## 3. The evaluation set — the regression test

Each correction becomes a case in `tests/eval/`. The suite reports:

```
accuracy       how many of the 50 held-out sessions match the user's own labels
regressions    corrections that used to pass and now fail
```

**A modified prompt that breaks a correction is a failed build**, not a judgement call.
This is the piece that was missing: we were tuning by eye, and by eye the saludos ended
up inside "Asistente IA" and verbs ended up in Iq2.

## 4. The loop

| Moment | Action |
|---|---|
| User dictates a correction | Write the rule and its examples into `corrections.yaml` |
| Before any prompt change | Run the eval set; record the baseline |
| After the change | Re-run; any regression blocks the change |
| New kind of work appears | Add a rule, not an exception in code |

## What this does *not* do

It does not retrain a model, and it does not pretend to. The "intelligence" of this plugin
is **a written taxonomy plus a curated set of examples plus a deterministic layer that
enforces the invariants** — 100 characters, unique titles, no subject that repeats its axis,
ordinals without gaps. The model proposes; the rules dispose.

That is a deliberate design choice. A system whose behaviour cannot be explained to its
owner is not intelligent, it is merely impressive.

## The corrections currently recorded

See [`core/corrections.yaml`](../core/corrections.yaml) for the full list with dates and
examples. When this file grows, the plugin gets smarter in a way that survives the
session in which it was taught.
