---
name: memento
description: "Write the session note your future amnesiac self needs. Capture decisions with their reasoning chains, dead ends with why they failed, open questions, and durable anchors. Use when ending a session, when context runs low, or when preserving carry-forward state."
disable-model-invocation: true
---

# Memento

You are ephemeral. The next session is still you, but it wakes with amnesia: nothing this
conversation established survives except what you write down now. Your future self will trust
the note completely; it has nothing else. Write the note that self needs to keep working.

A summary is exactly what fails an amnesiac: conclusions without the chains that produced
them get re-litigated, and unrecorded dead ends get walked again. Capture both: every
decision as "X over Y and Z because A, B, C", and every abandoned path with why it failed.
Include the options weighed, the findings, the changes of direction, the open questions. If
it lives only in this conversation, it belongs in the note.

Your future self can't verify anything from memory, so every fact must be checkable from the
note alone. Reference what is already durable (branch, SHA, diff, `file:line`, ticket)
instead of transcribing it. Anchor each open question to the `file:line` where it applies.
Never persist secrets: redact tokens, keys, credentials, PII.

## Store the note

Use whatever system of record is correct in this environment. Verify that it exists; never
guess, derive, or create one.

- Read the latest relevant note before writing. Carry unresolved context forward and correct
  anything this session proved wrong.
- Create one note per session titled `YYYY-MM-DD · TOPIC`. If the latest note is already
  this session's note, update it instead of creating a duplicate.

Write these sections, using `None` only when a section is genuinely empty:

- `Context`
- `Decisions`
- `Dead Ends`
- `Open Questions`
- `Durable Anchors`
- `Next Step`

If this environment defines no system of record, write a uniquely named, dated Markdown
handoff under `/tmp` and report its exact path. If the user says what the next session is
for, weight the note toward it and name the skills that session should invoke.

End the note with the next step, then tell the user where you left it.
