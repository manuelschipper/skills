---
name: audit-greppability
description: "Exhaustive whole-repository greppability audit against the greppable rubric: every hand-written file enumerated, read in full, and reconciled into one evidence-rich Markdown report."
disable-model-invocation: true
---

# Audit greppability

Turn the repository upside down against the greppable rubric. Where `greppable` judges one change
and Gardenr picks one candidate, this audit proves coverage: every hand-written file is
enumerated, assigned, read in full, and reconciled, and every number in the report is a row in a
file on disk. It is deliberately slow.

`scripts/audit.py` (git and Python 3 only) does the mechanical half: enumerate, shard, reconcile,
measure, render. You do the judging. Run it by absolute path from this skill's directory
(`${CLAUDE_SKILL_DIR}/scripts/audit.py` in Claude Code). Artifact contracts are in
[references/artifacts.md](references/artifacts.md).

## Introduce the audit

Before calling any tool, orient the user in plain language. Use one short paragraph that explains:

- Greppability is how easily an agent can find a concept's owner, production wiring, contract,
  tests, and intentional absences by searching the repository's own domain words.
- This is a deep, read-only audit of the whole repository. Every hand-written file is inventoried
  and read, subagents divide the work when the environment supports them, and the audit may take
  a while.
- The result is one detailed Markdown report that humans can audit and agents can execute. Chat
  receives a short guided summary, not the full report. The audit may use JSON internally to
  reconcile evidence, but JSON is not a deliverable or a choice for the user.

Use this shape, adapted to the repository: `I'll run a deep, read-only audit of the whole
repository. Greppability is how reliably an agent can search from a domain term to its owner,
wiring, contract, tests, and intentional absences. I'll read every hand-written file, use
subagents when this environment supports them, and produce one detailed Markdown report; it may
take a while.`

Then settle storage, in this precedence:

- Any applicable instruction, from the user, the environment, or the runtime, says not to store:
  say that the detailed Markdown will be returned in the reply and nothing will be persisted.
- The user named a destination, or the environment instructions name a system of record for
  reports (a known notes molds project, for instance): name that destination and continue.
- Otherwise ask: `Where should I store the detailed Markdown audit, or what is this environment's
  system of record for reports?` Then wait for the answer.

That is the only question. Do not lead with filenames, ask about formats, or ask the user to make
method choices. Never guess, derive, or create a store. Nothing is written into the audited
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
by line count. Read its exclusion table: a hand-written directory caught by a name rule (a domain
called `gen/`, hand-written scripts under `build/`) is a coverage hole, so rerun with
`--override PREFIX=CLASS` until every exclusion is truthful. Post the class table and shard count
as the first progress update.

## 2. Vocabulary

From the README, agent guidance, directory names, and exported type names, write
`W/vocabulary.json` with the canonical concepts and every spelling in use. Shards receive it, so
all readers propose the same names.

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
duplicates of an already-accepted finding, assigns stable finding IDs, and prints one `coverage:`
line: post it as the progress update. Dispatch every `S-NNr` shard it prints; a file that is
skipped twice becomes `uncovered`, a ledger state the report shows in full. Repeat until no shard
is pending. The audit is exhaustive only at zero uncovered files: read each uncovered file
yourself, complete its `S-NNr` artifact as the sequential path would (the file in `files_read`,
every heading in `properties_checked`), and rerun `verify`. A file no context can read in full
leaves the audit incomplete; `render` then stamps `Coverage : INCOMPLETE` in the header, and the
result is reported as an incomplete audit, never as a whole-repository one.

## 4. Cross-file pass

With `W/ledger.json` in hand, resolve every `cross_shard_leads` and `vocabulary_additions` entry
with `git grep`, and check what shards cannot see: the same definition in two files, import
renames, test-to-source mirroring, whether each excluded directory's boundary is recorded in the
agent guidance, and whether the repository records its search conventions at all. Write your own
findings to `W/shards/main.json` in the shard artifact shape.

Then run the search trials: for every concept in the vocabulary, search as a fresh agent would and
record in `vocabulary.json` the path that proves each surface was reached (owner, production
wiring, contract, tests, intentional absence), `null` when it was not, `"n/a"` when it does not
apply. Rerun `audit.py verify --work W` so `main.json` findings get IDs.

## 5. Packets and narrative

Write `W/packets.json`: accepted finding IDs grouped by shared files and symbols into units the
size of one bounded change, with `after` dependencies and argv-shaped accept checks. A recipe is
only ever a mechanical step; a fix that needs a design choice is a decision with options, and new
names come from the vocabulary. Write `W/narrative.json` with the verdict, one method line, a
`property_checks` entry for every property that has no findings (the concrete search or count
that supports "clean"; the ledger prints it), and any property that genuinely does not apply.

```
audit.py measure --work W
audit.py render --work W --out W/audit.md
```

`measure` counts every symbol's blast radius and every concept's hits with `git grep`, checks
proposed names for collisions, validates packets (unique IDs, argv accept checks), checks the
property evidence, and orders the packets; it recomputes its problems on every run. `render`
writes the detailed Markdown report: an opening verdict, 7-bit ASCII maps, full evidence cards for
every severity, packets, handoff, and coverage ledger. It also refreshes an internal `audit.json`
inside `W` for consistency checks; do not deliver or mention that scratch file. Zero problems,
zero uncovered, zero pending, and zero unassigned findings in its output, or fix the artifacts and
rerun.

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

The normal chat handoff is a calm briefing of roughly 120-200 words, in this order:

1. A one- or two-sentence verdict in plain language, including whether any HIGH findings exist.
2. At most three priority themes. For each, state the consequence, cite its finding or packet IDs,
   and include one representative `path:line` from the report. Do not recite every finding.
3. One coverage receipt: files read versus assigned, properties checked, and search reach for each
   applicable vocabulary surface (owner, wiring, contract, tests, absence). Name every miss rather
   than hiding it in a ratio, and include uncovered or pending files.
4. The first work packet to take and why; mention a dependency only when it changes that choice.
   Surface every decision that requires the user before an agent can proceed.
5. The exact record, link, or path containing the detailed Markdown. When verification dropped or
   recovered anything, state the count and reason class here.

Keep maps, heat grids, complete property rows, full evidence, blast paths, every packet, and the
reconciliation ledger in the Markdown. Do not paste them into chat or end with a second TLDR. A
reader should understand the result from chat and verify or execute it from the one report.

Use this shape:

```markdown
[One- or two-sentence verdict, including the HIGH count.]

The three things that matter most:

- **[Theme]** (`F-NNN`, `P-NN`) - [consequence], evidenced at `path:line`.
- **[Theme]** (`F-NNN`) - [consequence], evidenced at `path:line`.
- **[Theme]** (`F-NNN`) - [consequence], evidenced at `path:line`.

Coverage: [read]/[assigned] hand-written files and [checked]/[rubric] properties. Search reaches
owner [n/n], wiring [n/n], contract [n/n], tests [n/n], and absence [n/n]; [name every miss].
[uncovered] files are uncovered and [pending] pending.

Start with `P-NN` because [reason]. Your decisions: [finding IDs and questions, or none]. Detailed
audit: [record, link, or path]. [Dropped/recovered verification note when nonzero.]
```

Use fewer than three themes when fewer are material. Omit the theme list when there are no
findings.

## Progress updates

One line each: the class table and shard count after the inventory, the `coverage:` line after
every `verify`, and the `report:` line after `render`. Nothing else interrupts the audit.
