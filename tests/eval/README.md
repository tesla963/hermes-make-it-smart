# The evaluation set

Without this, every prompt change is a guess. With it, a prompt change is a
measurable event.

## Method

1. **Sample 50 sessions, stratified.** Proportional by month, plus five with no
   usable user messages (the hard cases: cron jobs, empty sessions) and a few
   hidden ones. Seeded random, so the sample is reproducible.
2. **Classify them** with the current prompt.
3. **A human reviews each one** in the review sheet (`tools/make_review.py`) —
   approve, or correct any of the six fields. Every card also has an
   **Observaciones** box: a free-text note that travels with the label. Notes are
   the most valuable part of a review, because they say *why*, and a reason can
   become a rule while a correction alone cannot. That review is the ground truth.
4. **Export `labels.json`** from the review tool.
5. **Run the harness.** It re-classifies from scratch and compares.

## The privacy rule

**Session text never enters this repository.** `labels.json` holds ids and
labels only, and it is gitignored. The harness reads the text from the local
Hermes databases at run time.

That is not a formality: the repo is meant to become public, and the sessions
are a person's working life.

## Running

```bash
python3 tests/eval/run_eval.py --labels tests/eval/labels.json --save baseline.json
python3 tests/eval/run_eval.py --labels tests/eval/labels.json --baseline baseline.json
```

The second form is the one that matters. It exits **1** when a case that used to
pass now fails:

> A prompt change that breaks an owned correction is a failed build.

## What it reports

| Metric | Meaning |
|---|---|
| exact matches | all fields agreed |
| per-field accuracy | where the misses concentrate |
| misses | case number, field, wanted vs got, first message |
| regressions | cases that passed in the baseline and now fail |

## Reading the numbers

`tag2` will always look worse than the rest: it is the most subjective field,
and "is this Troubleshooting or Productivity?" has genuine disagreement. What
matters is that **the misses stay stable** and that correcting one teaches the
system permanently (see `docs/CORRECTIONS.md`).

`subject` and `tag1` are the fields a user actually navigates by. A regression
there is a release blocker.

## Cost

50 sessions ≈ 1,480 prompt tokens each ≈ **2 cents** per full run at off-peak
rates. The prompt cache makes consecutive runs cheaper still, so there is no
reason to skip the check.
