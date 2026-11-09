"""The classifier prompt.

Pure Python: builds the system prompt from the taxonomy and the recorded
corrections, and the user message from one session record. No host imports,
no model calls — this module only produces text, so it can be inspected and
approved before a single token is spent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .taxonomy import (
    COUNTRIES,
    IT_FAMILIES,
    MACHINES,
    MARKET_FAMILIES,
    NON_IT_FAMILIES,
    PILLARS,
    PLATFORMS,
    VERBS,
)

CORRECTIONS_PATH = Path(__file__).with_name("corrections.yaml")


# --------------------------------------------------------------------------- #
# Corrections
# --------------------------------------------------------------------------- #


def load_corrections(path: Path | None = None) -> list[dict[str, Any]]:
    """Read the corrections file. A missing PyYAML degrades to an empty list."""
    path = path or CORRECTIONS_PATH
    if not path.exists():
        return []
    try:
        import yaml  # noqa: PLC0415
    except Exception:
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _fmt_example(ex: dict[str, Any]) -> str:
    """One correction example as a single readable line."""
    bits: list[str] = []
    if "nnn" in ex:
        bits.append(f"session {ex['nnn']}")
    if "subject" in ex:
        bits.append(f"subject={ex['subject']!r}")
    if "right_subject" in ex:
        bits.append(f"subject={ex['right_subject']!r}")
    if "wrong_subject" in ex:
        bits.append(f"(not {ex['wrong_subject']!r})")
    if "tag1" in ex:
        bits.append(f"tag1={ex['tag1']!r}")
    if "tag2" in ex:
        bits.append(f"tag2={ex['tag2']!r}")
    if "pillar" in ex:
        bits.append(f"pillar={ex['pillar']!r}")
    if "description_ends" in ex:
        bits.append(f"description ends with {ex['description_ends']!r}")
    return ", ".join(bits)


def render_corrections(corrections: list[dict[str, Any]]) -> str:
    """The correction block: rule first, evidence second, control question last."""
    if not corrections:
        return "(no corrections recorded yet)"
    out: list[str] = []
    for i, c in enumerate(corrections, 1):
        rule = " ".join(str(c.get("rule", "")).split())
        out.append(f"{i}. {rule}")
        for ex in c.get("examples") or []:
            line = _fmt_example(ex)
            if line:
                out.append(f"   - {line}")
        if c.get("control_question"):
            out.append(f"   Ask yourself: {c['control_question']}")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# System prompt
# --------------------------------------------------------------------------- #


def build_system_prompt(
    corrections: list[dict[str, Any]] | None = None, *, language: str = "Spanish"
) -> str:
    """The full system prompt. Deterministic: same inputs, same text."""
    corrections = corrections if corrections is not None else load_corrections()

    return f"""You classify work sessions for a personal AI assistant.

You receive the first messages a user wrote in one session. You return the
facets that identify it. You do NOT write the session title, you do NOT
number it, and you do NOT invent a date: those are added afterwards by code.

## The five fields you return

subject     What the session is ABOUT: the object, the problem, the symptom.
            2-4 words, written in {language}. NEVER the name of a program or platform.
            Strip the action prefix ("Instalar X" -> "X") and the state
            adjectives ("trancado", "inusual", "con error").
            If it is a failure, name the POINT OF FAILURE ("Protocolo"),
            not the component.

tag1        The PROTAGONIST: who or what is really doing the work.
            Pick ONE from the platform list below. If nothing fits and the
            session is not about software, use "Hermes Agent".
            Never the operating system by default: macOS explains almost
            every session and therefore explains nothing.
            Never abbreviate: "Hermes Agent", not "Hermes".
            NEVER guess a brand or product that the messages do not evidence.
            A plausible brand is worse than no brand: if the messages do not
            name it, use "Hermes Agent" and put the object in the subject.

tag2        The KIND OF WORK. Pick ONE from the family list below, or "".
            Use "Troubleshooting" only when the user reports something
            FAILING, not when the topic is merely mentioned.
            If the subject already says it, leave tag2 empty.

pillar      The WORK FRONT. Pick ONE from the pillar list below.

description What subject + tags could NOT say. One short telegraphic clause,
            written in {language}, no filler, no restating the subject.
            May be "" if the subject and tags already say everything.

verb        The ACTION taken, from the verb list below, or "".
            This becomes an appendix at the end of the title.

## Platform list (tag1)
{", ".join(PLATFORMS)}

## Work families (tag2)
IT: {", ".join(IT_FAMILIES)}
Non-IT: {", ".join(NON_IT_FAMILIES)}
Marketplace (used with a brand in tag1): {", ".join(MARKET_FAMILIES)}

## Pillars
{", ".join(PILLARS)}

## Verbs
{", ".join(VERBS)}

## Reference countries
{", ".join(COUNTRIES)}

## Reference machines
{", ".join(MACHINES)}

## Rules the owner taught (these override your intuition)

{render_corrections(corrections)}

## Output

Return ONE JSON object, nothing else, with exactly these keys:

{{"subject": str, "tag1": str, "tag2": str, "pillar": str,
 "description": str, "verb": str}}

No markdown, no comments, no explanation. Empty string when a field does not
apply. If the messages are too thin to tell what the session is about, return
"subject": "" and nothing else is required."""


# --------------------------------------------------------------------------- #
# User message
# --------------------------------------------------------------------------- #

MIN_USEFUL_MESSAGES = 1


def build_user_prompt(
    *,
    messages: list[str],
    date: str = "",
    current_title: str = "",
    channel: str = "",
) -> str:
    """The evidence block for one session.

    The evidence comes BEFORE the current title on purpose: showing the old
    label first anchors the model on it, and a stale label then gets confirmed
    instead of corrected.
    """
    lines: list[str] = []
    if date:
        lines.append(f"Session date: {date}")
    if channel:
        lines.append(f"Channel: {channel}")
    lines.append("")
    if messages:
        lines.append("What the user wrote (first messages, in order):")
        for i, m in enumerate(messages, 1):
            lines.append(f"{i}. {m}")
    else:
        lines.append("(no usable user messages in this session)")

    if current_title.strip():
        lines.append("")
        lines.append(
            f"Current title, for reference only — do not trust it, "
            f"it may be stale or wrong: {current_title.strip()}"
        )

    lines.append("")
    lines.append("Return the JSON object now.")
    return "\n".join(lines)


def build_messages(
    *,
    messages: list[str],
    date: str = "",
    current_title: str = "",
    channel: str = "",
    corrections: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """The full chat payload, ready for any OpenAI-compatible endpoint."""
    return [
        {"role": "system", "content": build_system_prompt(corrections)},
        {
            "role": "user",
            "content": build_user_prompt(
                messages=messages, date=date, current_title=current_title, channel=channel
            ),
        },
    ]


def prompt_fingerprint(corrections: list[dict[str, Any]] | None = None) -> str:
    """Short hash of the system prompt, to stamp every classification run."""
    import hashlib

    digest = hashlib.sha256(build_system_prompt(corrections).encode("utf-8")).hexdigest()
    return digest[:12]


def prompt_stats(corrections: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Counts for inspection and for the eval report."""
    corrections = corrections if corrections is not None else load_corrections()
    sp = build_system_prompt(corrections)
    return {
        "system_chars": len(sp),
        "system_words": len(sp.split()),
        "estimated_tokens": len(sp) // 4,
        "corrections": len(corrections),
        "platforms": len(PLATFORMS),
        "families": len(IT_FAMILIES) + len(NON_IT_FAMILIES) + len(MARKET_FAMILIES),
        "pillars": len(PILLARS),
        "verbs": len(VERBS),
        "fingerprint": prompt_fingerprint(corrections),
    }


__all__ = [
    "load_corrections",
    "render_corrections",
    "build_system_prompt",
    "build_user_prompt",
    "build_messages",
    "prompt_fingerprint",
    "prompt_stats",
]
