---
name: grep-audit
description: "Exhaustive whole-repository greppability audit against the greppable rubric: every maintained project file enumerated, read in full, and reconciled into one evidence-rich Markdown report."
disable-model-invocation: true
---

# Grep audit

Turn the repository upside down against the greppable rubric. Where `greppable` judges one change
and Gardenr picks one candidate, this audit proves coverage: every maintained project file is
enumerated, assigned, read in full, and reconciled, and every number in the report is a row in a
file on disk. It is deliberately slow.

`scripts/audit.py` (git and Python 3 only) does the mechanical half: enumerate, shard, reconcile,
measure, render, and format the chat briefing. You do the judging. Run it by absolute path from
this skill's directory (`${CLAUDE_SKILL_DIR}/scripts/audit.py` in Claude Code). Artifact contracts
are in [references/artifacts.md](references/artifacts.md).

## Introduce the audit

Settle the report delivery mode from existing instructions, in this precedence:

- Any applicable instruction, from the user, the environment, or the runtime, says not to store:
  use the chat-only ending below.
- The user named a destination, or the environment instructions name a system of record for
  reports: use the known-destination ending below.
- Otherwise use the question ending below.

Reply with one fenced `text` block containing this introduction and exactly one ending. Substitute
only `{repository}` and, when known, `{destination}`. Preserve the wording, wordmark, spacing, and
rules; do not add prose before or after the block.

```text
                        ██████  ██████  ███████ ██████
                       ██       ██   ██ ██      ██   ██
                       ██  ███  ██████  █████   ██████
                       ██   ██  ██   ██ ██      ██
                        ██████  ██   ██ ███████ ██

                              GREPPABILITY AUDIT

  A read-only audit of how easily coding agents can work in {repository}.

  I will seed the repository's vocabulary from its README, documentation,
  commands, filenames, and public code. As the readers inspect the code, they
  will add internal concepts and alternate spellings those surfaces do not
  reveal. Then I will check whether every term leads clearly to its
  implementation, usage, rules, and tests.

──────────────────────────────────────────────────────────────────────────────
  HOW THE AUDIT WORKS

  I will inspect the source, tests, configuration, scripts, schemas, and
  documentation maintained by the project. Generated and third-party material
  is identified separately.

  Subagents will divide the reading when available. Nothing in the repository
  will be modified. A deep audit may take a while.

──────────────────────────────────────────────────────────────────────────────
  WHAT YOU WILL GET

  A visual health score, the most important improvements in plain language,
  and a detailed Markdown report with the evidence and work packets a coding
  agent needs to implement them.

──────────────────────────────────────────────────────────────────────────────
```

Question ending; wait for the answer:

```text
  ONE QUESTION BEFORE I START

  Where should I store the detailed Markdown audit?
```

Known-destination ending; then continue:

```text
  REPORT DESTINATION

  {destination}
```

Chat-only ending; then continue:

```text
  DELIVERY

  Chat only · nothing will be stored
```

Do not expose how a destination was or was not discovered, ask about formats, or ask the user to
make method choices. Never guess, derive, or create a store. Nothing is written into the audited
repository.

## Before reading any code

1. Load the rubric in full: `greppable/SKILL.md` beside this skill's directory
   (`${CLAUDE_SKILL_DIR}/../greppable/SKILL.md` in Claude Code; `$greppable` in Codex). The
   property ledger is built from its `###` headings, so without that text there is no audit;
   stop and say so if it is missing.
2. Choose the work directory `W`: the host's scratch directory, outside the repository. All
   artifacts live there, so a later session resumes from `W` instead of starting over.

## 1. Inventory

```
audit.py inventory --repo . --work W [--scope PATH] [--override PREFIX=CLASS]
```

This enumerates every tracked and untracked-unignored file, classifies it (`source`, `test`,
`config`, `script`, `schema`, `docs` are read in full; `generated` and `vendored` are
boundary-checked; `data` and `binary` are listed), and plans directory-contiguous shards balanced
by line count. Read its exclusion table: a maintained directory caught by a name rule (a domain
called `gen/`, maintained scripts under `build/`) is a coverage hole, so rerun with
`--override PREFIX=CLASS` until every exclusion is truthful. Post the class table and shard count
as the first progress update.

## 2. Seed vocabulary

From the README, agent guidance, directory names, and exported type names, write
`W/vocabulary.json` with the initial canonical concepts and every spelling already visible. Give
each concept a `documented` proof path when documentation or agent guidance names it, otherwise
`null`; start `rejected` as an empty list. Shards receive this seed, so all readers begin with the
same names. It is a starting population, not the boundary of the audit.

## 3. Read every file

Each shard's instructions are the exact output of `audit.py shard-prompt --work W --shard S-NN`;
pass it verbatim, including the embedded rubric.

- Delegation available and permitted: dispatch shards through the host's subagent facility under
  the host's and the user's standing conventions for transport, model, panes, and worktrees; this
  skill adds none, and whether a read-only shard gets a worktree is those conventions' call. Run
  as many concurrently as the host allows, never re-read a shard's files yourself, and let no
  shard split itself further.
- Delegation unavailable or forbidden: walk the shards in order yourself, following the same
  prompt and writing the same artifact per shard, then continue.

After each batch run `audit.py verify --work W`. It reconciles every artifact against its
assignment, counts a shard that did not declare every rubric heading in `properties_checked` as
having read nothing, drops findings whose evidence is not at `path:line` (two lines of slack) and
exact duplicates with the same property, path, line, and evidence, assigns stable finding IDs, and
prints one `coverage:` line: post it as the progress update. Dispatch every `S-NNr` shard it
prints; a file that is
skipped twice becomes `uncovered`, a ledger state the report shows in full. Repeat until no shard
is pending. The audit is exhaustive only at zero uncovered files: read each uncovered file
yourself, complete its `S-NNr` artifact as the sequential path would (the file in `files_read`,
every heading in `properties_checked`), and rerun `verify`. A file no context can read in full
leaves the audit incomplete; `render` then stamps `Coverage : INCOMPLETE` in the header, and the
result is reported as an incomplete audit, never as a whole-repository one.

## 4. Cross-file pass

With `W/ledger.json` in hand, investigate every `cross_shard_leads` entry and close every
`vocabulary_additions` entry. Each discovered concept and spelling must become a concept or
spelling in `W/vocabulary.json`, or appear under `rejected` with the discovered spellings and a
one-line reason. Nothing readers discover may disappear silently.

Check what shards cannot see: the same definition in two files, import renames, test-to-source
mirroring, whether each excluded directory's boundary is recorded in the agent guidance, and
whether the repository records its search conventions at all. Write your own findings to
`W/shards/main.json` in the shard artifact shape. An undocumented internal concept that a product
term cannot reach is evidence for a repository-memory or naming finding, not a reason to omit the
concept.

Run search trials over the reconciled vocabulary, including internal concepts. Search each spelling
case-insensitively as a fixed substring so `organization` reaches `organizationId` and
`OrganizationRepository`. Record all five `reach` keys: a proof path for a reached owner,
production wiring, contract, tests, or intentional absence; `null` when the trial missed; and
`"n/a"` only when that surface genuinely does not apply. Each proof must contain a spelling in its
path or at the recorded line. File a finding for every `null` result.

Rerun `audit.py verify --work W` so `main.json` findings get stable IDs, then add the relevant
accepted IDs to each concept's `findings` list. `audit.py measure` withholds the score when an
addition is unresolved, a trial is incomplete, a proof does not contain a spelling, or a miss has
no accepted finding.

## 5. Packets and narrative

Write `W/packets.json`: accepted finding IDs grouped by shared files and symbols into units the
size of one bounded change, with `after` dependencies and argv-shaped accept checks. Titles state
the recommended action, not a question such as "choose" or "decide." A recipe is only ever a
mechanical step; a fix that needs a design choice is a decision with options and a recommended
option, and new names come from the vocabulary.

Write `W/narrative.json` with a one- or two-sentence verdict, one method line, a `property_checks`
entry for every property that has no findings (the concrete search or count that supports "clean";
the ledger prints it), and any property that genuinely does not apply. Add one to three ranked
improvements that partition every accepted finding exactly once. Each has an action-oriented title
and a short explanation of the current friction and why the action helps. Finding and packet IDs
link it to the detailed audit but never appear on the chat card.

```
audit.py measure --work W
audit.py render --work W --out W/audit.md
```

`measure` counts every symbol's blast radius and every concept's hits across the inventory, checks
proposed names for collisions, validates packets (unique IDs, argv accept checks), checks the
property evidence and theme coverage, and orders the packets; it recomputes its problems on every
run. `render` writes the detailed Markdown report with the same fixed GREP wordmark, audit title,
and purpose line as the introduction, followed by an opening verdict, a deterministic score,
plain-language severity definitions, ASCII maps, full evidence cards for every severity, packets,
handoff, and coverage ledger.
The score averages the worst accepted severity per applicable rubric property: clean `1.00`, LOW
`0.75`, MED `0.50`, HIGH `0.00`, rounded to the nearest integer. Multiple findings on one property
do not stack; the finding counts show volume. Incomplete coverage, reconciliation problems,
unassigned findings, or an unverified property withhold the score instead of silently discounting
it. The same credits roll up mechanically into five dimensions: Names & vocabulary, Ownership &
layout, Contracts & boundaries, Execution flow, and Tests & repository memory. `render` records each
dimension's property mapping beside the complete property ledger. It also refreshes an internal
`audit.json` inside `W` for consistency checks; do not
deliver or mention that scratch file. Zero problems, zero uncovered, zero pending, and zero
unassigned findings in its output, or fix the artifacts and rerun.

## 6. Redact, then deliver

Before anything leaves `W`, inspect both outputs for secrets:

```
grep -nEi '(api[_-]?key|secret|token|passw(or)?d|authorization|private key|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{20,})' W/audit.md W/audit.json
```

Read every hit. For a real credential or personal datum, trim the evidence in the originating
shard artifact or narrative to the fragment before the secret (`verify` matches a substring, so a
shortened quote still verifies), rerun `verify`, `measure`, and `render`, and inspect again. Never
edit `audit.md` or `audit.json` by hand; they must stay derivable from the artifacts.

Store only `audit.md` per the settled precedence. If storage is prohibited, load the Markdown for
the reply, remove the audit-created `W`, and leave no durable copy.

For a stored report, print the normal chat briefing mechanically:

```
audit.py card --work W --report /absolute/path/to/audit.md
```

Use the actual absolute location of the stored Markdown. Reply with one fenced `text` block
containing the command's output verbatim; at most one short introductory sentence may precede it,
and nothing follows it. The open report has left margins and continuous horizontal rules but no
top line or side frame. Filled and open circles visualize clean versus affected properties, with
adjacent text stating exactly what they measure. The card contains only the score, five inspected
dimension scores, a plain-language verdict, up to three ranked improvements, and a compact audit
receipt. Keep severity codes,
definitions, evidence paths, finding IDs, packet IDs, scoring mechanics, search matrices, and
acceptance checks in the detailed Markdown. The final line is exactly:

```text
Detailed audit   /absolute/path/to/audit.md
```

Keep maps, heat grids, complete property rows, full evidence, blast paths, every packet, and the
reconciliation ledger in the Markdown. Do not paste them into chat or end with a second TLDR. If
storage is prohibited, return the detailed Markdown as already specified instead of running
`card`.

## Progress updates

One line each: the class table and shard count after the inventory, the `coverage:` line after
every `verify`, and the `report:` line after `render`. Nothing else interrupts the audit.
