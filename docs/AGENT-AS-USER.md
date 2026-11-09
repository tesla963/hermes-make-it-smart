# The agent as a user of its own plugin

The plugin is not only a window for the owner. It is also a **tool for the
agent**, and that is the capability that turns a session browser into a
research instrument.

## Is it allowed?

Yes. A plugin is code running on the host, and Hermes plugins are allowed to
expose a CLI. There is nothing in the catalog rules against the agent invoking
its own plugin — the rule that matters is the opposite one: a plugin must not
write into a core module's tables behind the host's back. Reading is free;
writing goes through `SessionDB.set_session_title`.

So the shape is:

```
plugin/
  desktop/plugin.js          the window the owner uses
  tools/report_subject.py    the CLI the agent uses
  adapters/hermes.py         one SessionDB per profile, read-only
```

The same index answers both: the owner filters chips, the agent writes a file.

## The workflow that matters

A topic is spread over many sessions. The owner does not want to re-read them;
he wants their **history collapsed into one document** he can hand back.

```
# what subjects exist, and which ones have depth
python3 tools/report_subject.py --list --min-sessions 4

# the consolidated, dated report for one subject
python3 tools/report_subject.py "Flight Path" --out ~/Desktop/flight_path.md

# the term may live under another subject: search the whole title
python3 tools/report_subject.py "read aloud" --like --out ~/Desktop/read_aloud.md

# every subject with 3+ sessions, one file each
python3 tools/report_subject.py --all --min-sessions 3 --out-dir ~/Desktop/reportes
```

The output is a Markdown file: a header with the span of dates, totals, the
platforms and families involved, then one section per session in date order,
each with the title it carries, what was actually asked in the owner's own
words, and its cost. A new session can start by uploading that file, and the
agent begins with the whole prior context already on the table.

## Design notes

- **The body is the owner's words, not the summary.** The cleaned user turns
  are what survives a new session reading the file. A summary drifts; the
  original request does not.
- **Cron preambles are noise.** A scheduled session opens with
  `## Script Output` and `You are running as a scheduled cron job`. Those
  lines are filtered out before they can masquerade as something the owner
  said. When nothing human is left, the report falls back to the description.
- **Order is by date, tie-broken by ordinal.** The whole point is the
  chronology: what was decided first, what came after.
- **Reads only.** Every database opens `mode=ro`. The report tool never writes.

## Why this beats asking again

Asked in a fresh session, the agent reconstructs a topic from scratch, spends
tokens, and forgets what was already settled. Handed the consolidated report,
it starts from where the work stopped. The plugin does the remembering; the
agent does the thinking.
