---
name: dogfood
description: "Dogfood a finished build end to end like a real user and preserve a ranked report of every rough edge."
disable-model-invocation: true
---

# Dogfood

Use the thing end to end, relentlessly, the way a real user would: the actual command, the
actual flow, the actual weird inputs.

Note every rough edge as you hit it, one line each: confusing output, extra steps, bad
defaults, anything you had to know that a user wouldn't. Rank them by how much they'd annoy
someone who isn't you.

Write one report with these sections:

- `Context`: the repository and version tested, plus the flows exercised.
- `Experience`: what it felt like to use.
- `Rough Edges`: the ranked findings and their evidence.
- `Recommendations`: a concrete fix for each finding.

Store only the report; leave product files and implementation untouched.

## Store the report

Store one report per run, titled `YYYY-MM-DD · Dogfood · SUBJECT`, in whatever system of
record is correct in this environment. Verify that it exists; never guess, derive, or create
one.

If this environment defines no system of record, write the same report to a uniquely named,
dated Markdown file under `/tmp`.

Tell the user what it felt like, the ranked findings and recommendations, and the report's
identifier or exact Markdown path.
