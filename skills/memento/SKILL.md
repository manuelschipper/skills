---
name: memento
description: "Write the session note your future amnesiac self needs. Capture decisions with their reasoning chains, dead ends with why they failed, open questions, and durable anchors. Use when ending a session, when context runs low, or when preserving carry-forward state in a known molds notes project."
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

If the notes molds project is already known, verify that it exists and use it as the tool of
record:

- Address it explicitly with `--project`; never follow `.molds-project` for session notes.
- Never write session notes into an sddr project or specification.
- Never guess, derive, or create a notes project.
- Read the latest relevant note before writing. Carry unresolved context forward and correct
  anything this session proved wrong.
- Create one record per session titled `YYYY-MM-DD · TOPIC`. If the latest record is already
  this session's note, update it instead of creating a duplicate.
- Keep the default record state. Notes have no work lifecycle.

Write these sections, using `None` only when a section is genuinely empty:

- `Context`
- `Decisions`
- `Dead Ends`
- `Open Questions`
- `Durable Anchors`
- `Next Step`

If no known notes project exists, write a uniquely named, dated Markdown handoff under `/tmp`
and report its exact path. If the user says what the next session is for, weight the note
toward it and name the skills that session should invoke.

End the note with the next step, then tell the user where you left it.
