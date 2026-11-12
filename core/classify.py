"""The classifier: model proposes, rules dispose.

Pure Python. No host imports. The API key is passed in by the caller, so this
module has no opinion about where credentials live.

Pipeline for one session:

    prompt  →  model  →  JSON  →  validate  →  normalize  →  Facets

If the model fails twice, a deterministic keyword fallback still produces a
usable result. A session is never left without an attempt, and nothing is
invented: an unclassifiable session is marked, not guessed.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from .normalize import Facets, core_subject, strip_spec
from .prompt import build_messages
from .bateria import load_bateria, strip_brand
from .taxonomy import (
    DEFAULT_PLATFORM,
    apply_abbreviation,
    is_redundant_axis,
    normalize_family,
    normalize_intention,
    normalize_context,
    normalize_theme,
    normalize_pillar,
    normalize_platform,
    normalize_verb,
)

DEFAULT_ENDPOINT = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-flash"

REQUIRED_KEYS = ("subject", "iq1", "iq2", "pillar", "description", "verb")


# --------------------------------------------------------------------------- #
# Model call
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ClassifyConfig:
    api_key: str
    endpoint: str = DEFAULT_ENDPOINT
    model: str = DEFAULT_MODEL
    temperature: float = 0.0   # reproducible: the eval set must not move between runs
    max_tokens: int = 1200   # the model spends part of this reasoning; below ~1000 the answer comes back empty
    timeout: int = 60
    retries: int = 1
    agent_name: str = "Lisa"   # what the owner calls the assistant
    language: str = "Spanish"


@dataclass
class ClassifyResult:
    facets: Facets | None
    raw: str = ""
    attempts: int = 0
    ok: bool = False
    error: str = ""
    used_fallback: bool = False
    prompt_fingerprint: str = ""


class ModelError(RuntimeError):
    pass


def _post(config: ClassifyConfig, payload: dict[str, Any]) -> str:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        config.endpoint,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=config.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise ModelError(f"HTTP {exc.code}: {detail}") from exc
    except Exception as exc:  # noqa: BLE001
        raise ModelError(f"{type(exc).__name__}: {exc}") from exc

    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise ModelError(f"unexpected response shape: {str(data)[:200]}") from exc


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def parse_json_object(raw: str) -> dict[str, Any]:
    """Tolerate fences, prose and trailing commas. Raise on genuine garbage."""
    if not raw or not raw.strip():
        raise ValueError("empty response")
    text = raw.strip()
    m = _FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"no JSON object in response: {text[:120]}")
    candidate = text[start : end + 1]
    try:
        obj = json.loads(candidate)
    except json.JSONDecodeError:
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
        obj = json.loads(candidate)
    if not isinstance(obj, dict):
        raise ValueError("response is not an object")
    return obj


# --------------------------------------------------------------------------- #
# Validation & normalization
# --------------------------------------------------------------------------- #


def to_facets(
    obj: dict[str, Any],
    ordinal: int = 1,
    bateria: dict[str, Any] | None = None,
) -> Facets:
    """Fold the model's answer onto the closed vocabularies and the invariants.

    ``bateria`` is the merged sheet (manual + the owner's own). Pass it in when
    one is already loaded; otherwise the merged sheet is read here.
    """
    subject = core_subject(str(obj.get("subject") or "").strip())
    subject = apply_abbreviation(subject)
    subject, spec = strip_spec(subject)
    raw_iq1 = str(obj.get("iq1") or "").strip()
    iq1 = apply_abbreviation(normalize_platform(raw_iq1))
    iq2 = normalize_context(str(obj.get("iq2") or "").strip())
    # The 2026-11-10 schema. iq3 is the verb, iq4 the theme, iq5 the year;
    # the old `pillar` key is still read so an older reply does not break.
    iq3 = normalize_intention(str(obj.get("iq3") or obj.get("verb") or "").strip())
    iq4 = normalize_theme(
        str(obj.get("iq4") or obj.get("pillar") or "").strip()
    )
    iq5 = str(obj.get("iq5") or obj.get("year") or "").strip()
    pillar = normalize_pillar(str(obj.get("pillar") or obj.get("iq4") or "").strip())
    verb = normalize_verb(str(obj.get("verb") or "").strip())
    desc = re.sub(r"\s+", " ", str(obj.get("description") or "")).strip()
    if spec and not desc:
        desc = spec
    country = str(obj.get("country") or "").strip()
    year = str(obj.get("year") or "").strip()
    machine = str(obj.get("machine") or "").strip()

    # A brand the closed list does not know is still a brand. Forcing it to
    # "Hermes Agent" loses the single most identifying word of the session.
    if pillar in ("Productos", "Servicios") and raw_iq1 and iq1 == DEFAULT_PLATFORM:
        if raw_iq1.lower() not in ("hermes", "hermes agent", ""):
            iq1 = raw_iq1.title() if raw_iq1.islower() else raw_iq1

    # "Hermes Agent" is the AUTHOR of every session, never the maker of its
    # subject. The model still reaches for it because 50 rules mention it; here
    # it is turned into an honest empty field.
    if iq1.strip().lower().startswith("hermes") or iq1.strip().lower() in ("", "varios"):
        iq1 = ""

    # The same word cannot fill two fields: if the context repeats the verb or
    # the theme, it says nothing and belongs nowhere.
    if iq2 and iq2.lower() in {iq3.lower(), iq4.lower()}:
        iq2 = ""

    if subject and iq1 and subject.strip().lower() == iq1.strip().lower():
        subject = ""

    # The cheatsheet knows who makes what: it can move a brand into Iq1 and
    # take it out of the subject in one step. The merged sheet wins over the
    # packaged one, so the owner's own brands are recognised here too.
    if subject:
        stripped, brand_tag = strip_brand(subject, bateria)
        if brand_tag:
            subject = stripped
            if brand_tag.lower() != "hermes agent":
                iq1 = brand_tag

    # An axis that only repeats the subject or Iq1 is noise in the filter list.
    if is_redundant_axis(subject, iq2):
        iq2 = ""

    return Facets(
        subject=subject,
        subject_ordinal=ordinal,
        iq1=iq1 or DEFAULT_PLATFORM,
        iq2=iq2,
        iq3=iq3,
        iq4=iq4 or pillar,
        iq5=iq5 or year,
        pillar=pillar,
        country=country,
        year=year,
        machine=machine,
        description=desc,
        verb=verb,
    )


def problems_with(facets: Facets) -> list[str]:
    out: list[str] = []
    if not facets.subject:
        out.append("empty subject")
    if len(facets.subject) > 40:
        out.append("subject too long")
    if facets.iq2 and facets.iq2 == facets.iq1:
        out.append("iq2 repeats iq1")
    if facets.iq2 and is_redundant_axis(facets.subject, facets.iq2):
        out.append("iq2 repeats the subject")
    if facets.subject and facets.verb and facets.verb.lower() in facets.subject.lower():
        out.append("verb repeated inside the subject")
    return out


# --------------------------------------------------------------------------- #
# Deterministic fallback
# --------------------------------------------------------------------------- #

# Filler that must not survive in a fallback subject.
_LEAD_WORDS = frozenset(
    "lisa hermes por favor necesito quiero puedes podrias revisa revisar mira a ver "
    "el la los las un una unos unas de del al a en con por para que y o".split()
)
_TAIL_WORDS = frozenset(
    "de del al a en con por para que y o el la los las un una unos unas".split()
)

_KEYWORDS: tuple[tuple[str, str, str], ...] = (
    ("cyberpanel", "CyberPanel", "WebHosting"),
    ("wordpress", "WordPress", "WebHosting"),
    ("whatsapp", "WhatsApp", "Automation"),
    ("telegram", "Telegram", "Automation"),
    ("youtube", "YouTube", "Multimedia"),
    ("logseq", "Logseq", "Productivity"),
    ("dji", "DJI", "Multimedia"),
    ("brave", "Brave", "Networking"),
    ("deepseek", "DeepSeek", "IA"),
    ("gemini", "Gemini", "IA"),
    ("ollama", "Ollama", "IA"),
    ("dns", "CyberPanel", "Networking"),
    ("correo", "CyberPanel", "WebHosting"),
    ("backup", "Hermes Agent", "Data Backup"),
    ("respaldo", "Hermes Agent", "Data Backup"),
    ("error", "Hermes Agent", "Troubleshooting"),
    ("falla", "Hermes Agent", "Troubleshooting"),
    ("no funciona", "Hermes Agent", "Troubleshooting"),
)


def fallback_facets(messages: Sequence[str], ordinal: int = 1) -> Facets:
    """Last-resort classification. Never invents: it reads the first message."""
    blob = " ".join(messages).lower()
    iq1, iq2 = DEFAULT_PLATFORM, ""
    for needle, plat, fam in _KEYWORDS:
        if needle in blob:
            iq1, iq2 = plat, fam
            break
    first = (messages[0] if messages else "").strip()
    subject = core_subject(re.sub(r"[^\w\sáéíóúñÁÉÍÓÚÑ-]", " ", first))[:60].strip()
    words = [w for w in subject.split() if w.lower() not in _LEAD_WORDS]
    while words and words[-1].lower() in _TAIL_WORDS:
        words.pop()
    subject = " ".join(words[:4])
    return Facets(
        subject=subject,
        subject_ordinal=ordinal,
        iq1=iq1,
        iq2=iq2,
        pillar="Temas Varios",
        description="",
        verb="",
    )


# --------------------------------------------------------------------------- #
# One session
# --------------------------------------------------------------------------- #


def classify_one(
    *,
    messages: list[str],
    config: ClassifyConfig,
    date: str = "",
    current_title: str = "",
    channel: str = "",
    ordinal: int = 1,
    corrections: list[dict[str, Any]] | None = None,
    call_model: Callable[[ClassifyConfig, dict[str, Any]], str] | None = None,
    bateria: dict[str, Any] | None = None,
) -> ClassifyResult:
    """Classify one session. Retries once, then falls back deterministically."""
    caller = call_model or _post
    sheet = bateria if bateria is not None else load_bateria()
    payload_messages = build_messages(
        messages=messages,
        date=date,
        current_title=current_title,
        channel=channel,
        corrections=corrections,
        agent_name=config.agent_name,
        language=config.language,
    )
    conversation: list[dict[str, Any]] = list(payload_messages)
    base_payload: dict[str, Any] = {
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "response_format": {"type": "json_object"},
        "messages": conversation,
    }

    attempts = 0
    last_error = ""
    for attempt in range(config.retries + 1):
        attempts = attempt + 1
        base_payload["messages"] = conversation
        try:
            raw = caller(config, base_payload)
            obj = parse_json_object(raw)
            facets = to_facets(obj, ordinal, bateria=sheet)
            bad = problems_with(facets)
            if bad:
                last_error = "; ".join(bad)
                conversation = conversation + [
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": f"That answer was rejected: {last_error}. Return corrected JSON.",
                    },
                ]
                continue
            return ClassifyResult(facets=facets, raw=raw, attempts=attempts, ok=True)
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
            conversation = conversation + [
                {
                    "role": "user",
                    "content": f"Your previous reply was invalid ({last_error}). Return ONLY the JSON object.",
                }
            ]

    return ClassifyResult(
        facets=fallback_facets(messages, ordinal),
        raw="",
        attempts=attempts,
        ok=False,
        error=last_error,
        used_fallback=True,
    )


# --------------------------------------------------------------------------- #
# Batch
# --------------------------------------------------------------------------- #


@dataclass
class BatchReport:
    total: int = 0
    ok: int = 0
    fallback: int = 0
    failed: int = 0
    results: list[ClassifyResult] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.ok / self.total if self.total else 0.0

    def summary(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "ok": self.ok,
            "fallback": self.fallback,
            "failed": self.failed,
            "model_accuracy": round(self.accuracy, 4),
        }


def classify_batch(
    items: Iterable[dict[str, Any]],
    *,
    config: ClassifyConfig,
    corrections: list[dict[str, Any]] | None = None,
    call_model: Callable[[ClassifyConfig, dict[str, Any]], str] | None = None,
    on_progress: Callable[[int, int, ClassifyResult], None] | None = None,
) -> BatchReport:
    """Classify a sequence of {messages, date, current_title, channel, ordinal}."""
    report = BatchReport()
    items = list(items)
    report.total = len(items)
    for i, item in enumerate(items, 1):
        res = classify_one(
            messages=item.get("messages") or [],
            date=item.get("date", ""),
            current_title=item.get("current_title", ""),
            channel=item.get("channel", ""),
            ordinal=item.get("ordinal", 1),
            config=config,
            corrections=corrections,
            call_model=call_model,
        )
        report.results.append(res)
        if res.ok:
            report.ok += 1
        elif res.used_fallback:
            report.fallback += 1
        else:
            report.failed += 1
        if on_progress:
            on_progress(i, report.total, res)
    return report


__all__ = [
    "ClassifyConfig",
    "ClassifyResult",
    "BatchReport",
    "ModelError",
    "parse_json_object",
    "to_facets",
    "problems_with",
    "fallback_facets",
    "classify_one",
    "classify_batch",
]
