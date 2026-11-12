"""Evaluation harness.

Reads the labelled set, re-classifies every session with the current prompt,
and reports per-field accuracy plus every regression.

The session text never lives in this repository. `labels.json` is local only
(gitignored): it holds session ids and the labels a human approved. The text is
read from the local Hermes databases at run time, so the repo stays free of
personal content — and the harness still tests the real thing.

Usage
-----
    python3 tests/eval/run_eval.py --labels tests/eval/labels.json
    python3 tests/eval/run_eval.py --labels tests/eval/labels.json --save baseline.json
    python3 tests/eval/run_eval.py --labels tests/eval/labels.json --baseline baseline.json

Exit code is 1 when a case that used to pass now fails: a prompt change that
breaks an owned correction is a failed build, not a judgement call.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adapters.hermes import attach_messages, discover_databases, read_sessions  # noqa: E402
from core.classify import ClassifyConfig, classify_one  # noqa: E402
from core.prompt import prompt_fingerprint  # noqa: E402
from core.taxonomy import normalize_family, normalize_platform, normalize_verb  # noqa: E402

FIELDS = ("subject", "iq1", "iq2", "pillar", "verb")
STRICT_FIELDS = ("subject", "iq1", "iq2")

# Exact match is only meaningful on closed vocabularies. `subject` is free text
# and the model is NOT deterministic even at temperature 0 (measured: the same
# session gave "Consumo API" and "Saldo API" on consecutive runs). So subject is
# scored by shared significant tokens, not by string equality.
STOP = frozenset(
    "de del la el los las un una unos unas y o en con por para que al a su sus "
    "mi mis tu tus lo le les es son fue era como cual".split()
)


def subject_matches(want: str, got: str) -> bool:
    """Do these two subjects say the same thing?

    Jaccard over significant tokens, plus a contains-check so that a shorter
    correct subject ("Case USB") matches a longer one ("Case USB 4TB").
    """
    def toks(s: str) -> set[str]:
        return {w for w in re.findall(r"[\wáéíóúñü]+", (s or "").lower()) if w not in STOP}

    a, b = toks(want), toks(got)
    if not a or not b:
        return not a and not b
    inter = len(a & b)
    if not inter:
        return False
    if a <= b or b <= a:
        return True
    return inter / len(a | b) >= 0.5


def load_index() -> dict[str, tuple[str, Path]]:
    """session id -> (profile, db path), so a label can find its own text."""
    index: dict[str, tuple[str, Path]] = {}
    for profile, path in discover_databases():
        for rec in read_sessions(profile, path):
            index[rec.id] = (profile, path)
    return index


def norm(field: str, value: str | None) -> str:
    v = (value or "").strip()
    if field == "iq1":
        return normalize_platform(v).lower()
    if field == "iq2":
        return normalize_family(v).lower()
    if field == "verb":
        return normalize_verb(v).lower()
    return " ".join(v.lower().split())


def get_key() -> str:
    auth = Path(os.path.expanduser("~/.hermes/auth.json"))
    data = json.loads(auth.read_text(encoding="utf-8"))
    return data["credential_pool"]["deepseek"][0]["access_token"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True, help="labelled set (local, not committed)")
    ap.add_argument("--model", default="deepseek-flash")
    ap.add_argument("--baseline", help="previous report; regressions fail the run")
    ap.add_argument("--save", help="write this run's report here")
    ap.add_argument("--only", type=int, help="run a single case number")
    args = ap.parse_args()

    labels = json.loads(Path(args.labels).read_text(encoding="utf-8"))
    index = load_index()
    cfg = ClassifyConfig(api_key=get_key(), model=args.model)

    per_field_ok: dict[str, int] = defaultdict(int)
    per_field_total: dict[str, int] = defaultdict(int)
    misses: list[dict] = []
    results: dict[str, dict] = {}
    exact = 0
    considered = 0

    for case in labels:
        if case.get("status") != "ok" and case.get("label") is None:
            continue  # not reviewed yet
        if args.only and case["n"] != args.only:
            continue
        where = index.get(case["id"])
        if not where:
            print(f"  skip {case['n']}: session not found", file=sys.stderr)
            continue
        profile, path = where
        recs = {r.id: r for r in read_sessions(profile, path)}
        rec = attach_messages(recs[case["id"]], path)

        res = classify_one(
            messages=rec.messages,
            date=rec.created_at,
            current_title=rec.title or "",
            channel=rec.source or "",
            config=cfg,
        )
        if not res.facets:
            continue
        got = {
            "subject": res.facets.subject,
            "iq1": res.facets.iq1,
            "iq2": res.facets.iq2,
            "pillar": res.facets.pillar,
            "verb": res.facets.verb,
        }
        want = case["label"] or {}

        considered += 1
        case_ok = True
        for f in FIELDS:
            if want.get(f) is None:
                continue
            per_field_total[f] += 1
            same = (
                subject_matches(str(want.get(f) or ""), got[f])
                if f == "subject"
                else norm(f, got[f]) == norm(f, want.get(f))
            )
            if same:
                per_field_ok[f] += 1
            else:
                case_ok = False
                if f in STRICT_FIELDS:
                    misses.append(
                        {
                            "n": case["n"],
                            "field": f,
                            "want": want.get(f),
                            "got": got[f],
                            "msgs": (rec.messages[0][:90] if rec.messages else ""),
                            "notes": case.get("notes"),
                        }
                    )
        if case_ok:
            exact += 1
        results[str(case["n"])] = {"ok": case_ok, "got": got, "want": want}

    print("=" * 66)
    print(f"prompt fingerprint : {prompt_fingerprint()}")
    print(f"model              : {args.model}")
    noted = sum(1 for c in labels if (c.get("notes") or "").strip())
    print(f"cases evaluated    : {considered}")
    print(f"reviewer notes     : {noted}")
    print(f"exact matches      : {exact}/{considered}  "
          f"({exact / considered * 100:.1f}%)" if considered else "no cases")
    print("-" * 66)
    for f in FIELDS:
        t = per_field_total[f]
        if t:
            print(f"  {f:<12} {per_field_ok[f]:>3}/{t:<3}  {per_field_ok[f] / t * 100:5.1f}%")
    print("=" * 66)

    if misses:
        print(f"\n{len(misses)} miss(es) on subject/iq1/iq2:\n")
        for m in misses:
            print(f"  #{m['n']:>2} {m['field']:<8} want={m['want']!r} got={m['got']!r}")
            if m["msgs"]:
                print(f"        msgs: {m['msgs']}")
            if m.get("notes"):
                print(f"        NOTE: {m['notes']}")

    regressions: list[dict] = []
    if args.baseline and Path(args.baseline).exists():
        base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        for n, was in (base.get("results") or {}).items():
            now = results.get(n)
            if was.get("ok") and now and not now.get("ok"):
                regressions.append({"n": int(n), "want": was.get("want"), "got": now.get("got")})
        print(f"\nregressions vs baseline: {len(regressions)}")
        for r in regressions:
            print(f"  #{r['n']:>2} was passing, now {r['got']}")
        if regressions:
            print("\nFAILED: a prompt change broke previously correct cases.")
            return 1

    if args.save:
        Path(args.save).write_text(
            json.dumps(
                {
                    "fingerprint": prompt_fingerprint(),
                    "model": args.model,
                    "exact": exact,
                    "considered": considered,
                    "per_field": {f: [per_field_ok[f], per_field_total[f]] for f in FIELDS},
                    "results": results,
                },
                indent=1,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"\nsaved -> {args.save}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
