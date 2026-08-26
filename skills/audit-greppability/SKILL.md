---
name: audit-greppability
description: "Exhaustive whole-repository greppability audit against the greppable rubric: every hand-written file enumerated, read in full, and reconciled; a 7-bit ASCII evidence report plus same-ID JSON another agent can fix from."
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

## Before reading any code

1. Load the rubric in full: `greppable/SKILL.md` beside this skill's directory
   (`${CLAUDE_SKILL_DIR}/../greppable/SKILL.md` in Claude Code; `$greppable` in Codex). The
   property ledger is built from its `###` headings, so without that text there is no audit;
   stop and say so if it is missing.
2. Settle storage, in this precedence:
   - Any applicable instruction, from the user, the environment, or the runtime, says not to
     store: the report goes in the reply only.
   - The user named a destination, or the environment instructions name a system of record for
     reports (a known notes molds project, for instance): use it with its own conventions.
   - Otherwise ask where the report should live and wait for the answer. Never guess, derive,
     or create a store.
   In every case nothing is written into the audited repository.
3. Choose the work directory `W`: the host's scratch directory, outside the repository. All
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
audit.py render --work W --out W/audit.txt --json W/audit.json
```

`measure` counts every symbol's blast radius and every concept's hits with `git grep`, checks
proposed names for collisions, validates packets (unique IDs, argv accept checks), checks the
property evidence, and orders the packets; it recomputes its problems on every run. `render`
writes the 7-bit ASCII report (map, coverage bars, heat grid, property ledger, search reach,
evidence cards, packets, handoff, ledger appendix) and the same-ID JSON. Zero problems, zero
uncovered, zero pending, and zero unassigned findings in its output, or fix the artifacts and
rerun.

## 6. Redact, then deliver

Before anything leaves `W`, inspect both outputs for secrets:

```
grep -nEi '(api[_-]?key|secret|token|passw(or)?d|authorization|private key|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{20,})' W/audit.txt W/audit.json
```

Read every hit. For a real credential or personal datum, trim the evidence in the originating
shard artifact or narrative to the fragment before the secret (`verify` matches a substring, so a
shortened quote still verifies), rerun `verify`, `measure`, and `render`, and inspect again. Never
edit `audit.txt` or `audit.json` by hand; they must stay derivable from the artifacts.

Store `audit.txt` and `audit.json` per the settled precedence; in a Markdown store, fence the
report so alignment survives. Reply with the verdict, the final `coverage:` line, the HIGH count,
the packet list, and where the files went.

## Progress updates

One line each: the class table and shard count after the inventory, the `coverage:` line after
every `verify`, and the `report:` line after `render`. Nothing else interrupts the audit.
