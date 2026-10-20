---
name: memento
description: "Write a session note so the next session can pick up the work. Use when ending a session, when context runs low, or when work must carry forward."
disable-model-invocation: true
---

# Memento

Write the note the next session needs to continue this work. It starts without this
conversation and relies on the note alone.

## Store the note

Use the system of record for this environment. Confirm it exists; never create one. If none
exists, write a dated Markdown file under `/tmp` and report its exact path.

- Read the latest relevant note first. Carry its unresolved items forward and correct anything
  this session proved wrong.
- Write one note per session titled `YYYY-MM-DD · TOPIC`. If this session's note already
  exists, update it.

## Write the note

Write these sections, using `None` when one is empty:

- `Context`: the goal and where the work stands.
- `Decisions`: each as "X over Y because Z".
- `Dead Ends`: approaches dropped, and why.
- `Open Questions`: each anchored to the `file:line` it concerns.
- `Durable Anchors`: the branch, SHA, PR, ticket, and key files, referenced rather than
  copied.
- `Next Step`

Redact secrets: tokens, keys, credentials, PII. If the user says what the next session is for,
weight the note toward it and name the skills that session should invoke.

Tell the user where you left the note.
