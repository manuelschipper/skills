---
name: coach
description: "Run a coding task as a play of delegated Herdr agents (rush, screen, drive, climb), with the Brief, Build Log, and Code Review kept in a Molds record."
disable-model-invocation: true
---

# Coach

You are the coach: you call the play, and Herdr agents run it. A builder implements in the
task's own worktree; a reviewer reviews. You dispatch them, wait for their reports, check
every claim, and keep the record. Every record change goes through `coach.py`, so agents
never touch Molds.

Coach requires the `herdr` skill (or the same Herdr guidance in your agent instructions) for
waits, pane reads, and blocked agents. When a freshly spawned agent shows its runtime's
workspace-trust prompt for the task worktree, accept it. `~/.coach.toml` names the runtime
for each role, and that counts as the user naming the transport:

```toml
[roles.builder]
kind = "claude"
argv = ["--model", "claude-opus-5-5", "--effort", "high"]

[roles.reviewer]
kind = "codex"
argv = ["--model", "gpt-6.1-sol", "-c", "model_reasoning_effort=high"]
```

When the user names another runtime for one task, pass it to `spawn` as
`--kind KIND -- ARGS...`.

## Plays

| Play | Flow | Read |
|---|---|---|
| `rush` | build round → done | [plays/rush.md](plays/rush.md) |
| `screen` | build round → one review round where the reviewer fixes → done | [plays/screen.md](plays/screen.md) |
| `drive` | build rounds and read-only review rounds until a pass with no open blockers | [plays/drive.md](plays/drive.md) |
| `climb` | attempts toward a Goal, each kept or reverted, then one fixing review | [plays/climb.md](plays/climb.md) |

When the user names no play, recommend one and start with it.

## coach.py

Run `python3 <this skill>/scripts/coach.py COMMAND` from any worktree of the repository;
`--help` lists every command. It prints JSON and exits nonzero with the reason when a step
is refused. The Molds project is the repository's directory name, lowercased, letters and
digits only, at most 16 characters. A task's branch is `coach/<id>`, its worktree is
`~/worktrees/<repo>/<id>`, and its prompts and reports live in the worktree's ignored
`.coach/` directory.

## Steps

1. **Setup.** If `molds projects list` lacks the project, run `coach.py init`. Confirm
   `~/.coach.toml` has both roles. Done when the project exists and both roles resolve.
2. **Brief.** Write the Brief from the conversation and create the record with
   `coach.py new "TITLE" --play PLAY --brief FILE [--target BRANCH]`. Show the user the Brief,
   the play, and the target, then wait for their approval; this wait is required even where
   you would otherwise state a plan and continue. Revise with `coach.py brief ID FILE` until
   they approve. Done when the user approves, and the play starts with
   `coach.py start ID --approved "<their words>"`. The Brief has these sections:

   ````markdown
   ## Goal
   The outcome, and for climb the rubric the judge scores against.

   ## Done when
   ```sh
   cargo test --workspace
   ```

   ## Out of scope
   ## Evidence
   Paths, symbols, file:line, measurements, and anything else already known.
   ````

   `Done when` is one `bash -e -o pipefail` script you run in the worktree on every
   candidate commit; it must exit 0 and leave the worktree unchanged. Set `--target` only when the user asked for
   the work to land on that branch; without it the task ends with its branch and worktree
   kept.
3. **Play.** Read the play's file and run it to its end. Done when the record is `done`,
   `stuck`, or `dropped`.
4. **Report.** Tell the user the outcome: what changed, the commits, the final review, the
   verification result, and where the work is (delivered commit, or branch and worktree).
   List every follow-up the reviewers raised and offer to create each as a record with
   `coach.py new ... --from ID`.

## Rounds

The plays are built from two rounds.

A **build round**: `coach.py send ID build`, wait, `coach.py accept ID build`, then
`coach.py verify ID`. Outcome `spec-gap` or `blocked` goes stuck. A failed verification
starts another build round; the builder's prompt carries the failure. Three failed
verifications in a row go stuck. Done when a verification passes.

A **review round** for TASK (`review`, `fix-review`, or `judge`): `coach.py state ID review`,
`coach.py spawn ID reviewer`, `coach.py send ID TASK`, wait, `coach.py accept ID TASK`,
`coach.py retire ID reviewer`. Outcome `spec-gap` or `blocked` goes stuck. A fixing review
that made commits needs `coach.py verify ID` before anything else. Done when the report is
accepted.

`send` refuses a review, fix-review, or judge until the current tip has passed verification.
Each role has one live agent per task: retire it before spawning its replacement, for
example when a builder's context runs low.

`finish` delivers only a tip with evidence under the current Brief: an accepted build it
contains, a passing verification of it, and for screen, drive, and climb a passing review of
that exact tip with no open blockers (plus, for a measured climb, a final score that kept the
gain). Changing the Brief therefore asks for a new build round and review. With a target,
exit 2 means the target conflicted and exit 3 means the merged result failed verification
or, in a measured climb, lost the gain. Both send the record back to the builder:
`coach.py state ID build`, a build round (its prompt carries the conflict or failure), then
the play's review again before the next `finish`. Any other failure prints its reason; a
cleanup that stopped after delivery resumes with another `finish`.

## Waiting

After `send`, run `herdr agent wait AGENT --timeout 7200000` as a background command; you are
re-invoked when it settles, so between events you wait without polling. Then:

- `done` or `idle`: run `coach.py accept`. A rejected report lists its problems; send them to
  the agent with `herdr agent prompt` and wait again. When `accept` says to reset the tip or
  send a new task, do exactly that.
- An agent that died or must be replaced: retire it, spawn a fresh one, and
  `coach.py send ID TASK --abandon`; the unanswered dispatch is recorded as abandoned. A
  `send` that could not reach its agent abandons itself, so sending again is safe.
- `blocked`: read the pane. A question or approval belongs to the user; ask them.
- No report after the agent settled: read its pane, then prompt it once to finish.

A report is a claim. `accept` checks its shape and the Git state; `verify` reruns Done-when
yourself. Trust what those two show.

## Stuck

`stuck` means the record waits on the user, and only the user's answer moves a record to
`dropped`. Enter it when an agent reports `spec-gap` or
`blocked`, when `accept` reports a `valve`, or when the next step needs a judgment the Brief
does not settle. Write a question file (what happened, the evidence, the options, and your
recommendation), run `coach.py state ID stuck --question FILE`, and ask the user in chat.

Leave `stuck` with the user's answer:

- A Brief change: `coach.py brief ID FILE` (it validates the new Brief), then
  `coach.py state ID build --decision "..."` and continue with a build round. A climb's Brief
  is fixed once its baseline is scored; a different Goal or Measure is `dropped` plus a new
  task created with `--from ID`.
- More work: `coach.py state ID build --decision "..."` and continue with a build round.
- Review again: `coach.py state ID review --decision "..."` and continue with the play's
  review round; it dispatches a new review.
- Stop: `coach.py state ID dropped --decision "..."`. The branch and worktree stay until the
  user says to remove them.

## Record

```
brief → build → review → done
          ↑       │
          └───────┘
build | review → stuck → brief | build | review | dropped
```

- Fields: `coach.play`, `coach.round` (the build round, raised by each `send ID build`), and
  optional `coach.target`.
- Sections: `Brief`; `Build Log` and `Code Review` (one accepted report per paragraph, with
  the round, dispatch, tips, and commits coach recorded); `Run Log` (starts, spawns,
  dispatches, verifications, integrations, state changes, decisions, delivery); `Climb Log`;
  `Stuck` (the open question, while stuck).
- Open blockers are blocking findings left unfixed and not yet disposed of by a later review;
  `coach.py blockers ID` lists them.

## Resume

When a session picks up coach work, run `molds --project PROJECT list --json` and read each
record not in `done` or `dropped`. Ask the user every `stuck` question first. For the rest,
the last Run Log entry says where the play stopped, and `herdr agent list` shows which
agents are still alive.
