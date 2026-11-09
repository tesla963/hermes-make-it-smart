"""Build the review sheet for the evaluation set.

Samples 50 sessions stratified by month, classifies them with the current
prompt, and writes a self-contained HTML page a human can approve or correct.

The page is the ground truth generator: approve/correct, export `labels.json`,
then run `tests/eval/run_eval.py`.

Usage
-----
    python3 tools/make_review.py                     # 50 sessions, seeded
    python3 tools/make_review.py --n 30 --out /tmp/review.html
    python3 tools/make_review.py --no-classify       # reuse cached proposals
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.hermes import attach_messages, discover_databases, read_sessions  # noqa: E402
from core.classify import ClassifyConfig, classify_one  # noqa: E402
from core.normalize import Facets, render, short_date  # noqa: E402
from core.prompt import prompt_fingerprint  # noqa: E402

TEMPLATE = Path(__file__).with_name("review_template.html")
SEED = 20261109


def build_universe() -> list[dict]:
    universe: list[dict] = []
    for profile, path in discover_databases():
        for rec in read_sessions(profile, path):
            full = attach_messages(rec, path)
            universe.append(
                {
                    "id": full.id,
                    "fecha": full.created_at,
                    "titulo": full.title or "",
                    "msgs": full.messages,
                    "hidden": full.hidden,
                    "source": full.source or "",
                }
            )
    universe.sort(key=lambda u: (u["fecha"], u["id"]))
    return universe


def sample(universe: list[dict], n: int) -> list[dict]:
    """Stratified by month, plus the no-message cases (the hard ones)."""
    random.seed(SEED)
    with_msgs = [u for u in universe if u["msgs"]]
    without = [u for u in universe if not u["msgs"]]

    by_month: dict[str, list[dict]] = defaultdict(list)
    for u in with_msgs:
        by_month[u["fecha"][:7]].append(u)

    hard = min(5, len(without), max(0, n // 10))
    quota = n - hard
    months = sorted(by_month)
    total = sum(len(by_month[m]) for m in months) or 1

    picked: list[dict] = []
    for m in months:
        k = max(1, round(len(by_month[m]) / total * quota))
        picked += random.sample(by_month[m], min(k, len(by_month[m])))
    picked = picked[:quota]
    if hard and len(without) >= hard:
        picked += random.sample(without, hard)

    picked.sort(key=lambda u: (u["fecha"], u["id"]))
    return picked


def get_key() -> str:
    data = json.loads(Path(os.path.expanduser("~/.hermes/auth.json")).read_text(encoding="utf-8"))
    return data["credential_pool"]["deepseek"][0]["access_token"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--out", default=str(Path.home() / "Desktop" / "review_eval.html"))
    ap.add_argument("--model", default="deepseek-flash")
    ap.add_argument("--no-classify", action="store_true")
    ap.add_argument("--cache", default="/tmp/make_review_cache.json")
    args = ap.parse_args()

    print("reading sessions…", file=sys.stderr)
    universe = build_universe()
    picked = sample(universe, args.n)
    print(f"universe {len(universe)} → sampled {len(picked)}", file=sys.stderr)

    cache: dict = {}
    cached_sample: list[str] | None = None
    if args.no_classify and Path(args.cache).exists():
        blob = json.loads(Path(args.cache).read_text(encoding="utf-8"))
        if isinstance(blob, dict) and "sample" in blob:
            cached_sample = blob["sample"]
            cache = blob.get("rows") or {}
        else:
            cache = blob  # legacy: flat map of id -> row
        print(f"reusing {len(cache)} cached proposals", file=sys.stderr)

    rows = []
    if cache:
        # Rebuild from the cache but re-render the title: the date is recomputed
        # every run, so a cached row must not freeze an old one.
        # Prefer the sample the cache was built from: the stratification moves
        # when a session's date changes, and a re-render must not lose cases.
        chosen = [u for u in universe if u["id"] in set(cached_sample)] if cached_sample else picked
        chosen.sort(key=lambda u: (u["fecha"], u["id"]))
        for s in chosen:
            if s["id"] not in cache:
                continue
            row = dict(cache[s["id"]])
            row["fecha"] = s["fecha"]
            p = row["propuesta"]
            facets = Facets(
                subject=p["subject"], subject_ordinal=len(rows) + 1,
                tag1=p["tag1"], tag2=p["tag2"], pillar=p["pillar"],
                description=p["description"], verb=p["verb"],
            )
            row["titulo"] = render(len(rows) + 1, facets, short_date(s["fecha"]))
            rows.append(row)
    else:
        cfg = ClassifyConfig(api_key=get_key(), model=args.model)
        for i, s in enumerate(picked, 1):
            res = classify_one(
                messages=s["msgs"],
                date=s["fecha"],
                current_title=s["titulo"],
                channel=s["source"],
                config=cfg,
            )
            f = res.facets
            if f is None:  # classify_one always returns one; keep the type honest
                continue
            rows.append(
                {
                    "id": s["id"],
                    "fecha": s["fecha"],
                    "titulo_viejo": s["titulo"],
                    "msgs": s["msgs"],
                    "hidden": s["hidden"],
                    "source": s["source"],
                    "propuesta": {
                        "subject": f.subject,
                        "tag1": f.tag1,
                        "tag2": f.tag2,
                        "pillar": f.pillar,
                        "description": f.description,
                        "verb": f.verb,
                    },
                    "titulo": render(i, f, short_date(s["fecha"])),
                    "ok": res.ok,
                    "fallback": res.used_fallback,
                }
            )
            print(f"  {i}/{len(picked)} {f.subject[:38]!r}", file=sys.stderr)
        Path(args.cache).write_text(
            json.dumps({"sample": [r["id"] for r in rows], "rows": {r["id"]: r for r in rows}},
                       ensure_ascii=False),
            encoding="utf-8",
        )

    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("__DATA__", json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("__N__", str(len(rows)))
    html = html.replace("__FP__", prompt_fingerprint())

    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"\nwrote {out}  ({out.stat().st_size / 1024:.0f} KB, {len(rows)} sessions)")
    print("Review it, export labels.json, then:")
    print("  python3 tests/eval/run_eval.py --labels <labels.json> --save baseline.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
