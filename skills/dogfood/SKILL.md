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

If a notes molds project is already known, verify that it exists and use it as the tool of
record:

- Address it explicitly with `--project`; never follow `.molds-project`.
- Never write the report into an sddr project or specification.
- Never guess, derive, or create a notes project.
- Create one default-state record per run titled `YYYY-MM-DD · Dogfood · SUBJECT`.

If no known notes project exists, write the same report to a uniquely named, dated Markdown
file under `/tmp`.

Tell the user what it felt like, the ranked findings and recommendations, and the record ID
or exact Markdown path.
