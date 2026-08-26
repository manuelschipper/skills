# Change-range audit

What differs when `--base BASE` is set. The whole-repository steps in `SKILL.md` still apply; the
shard prompt and the artifact contracts are shared, and every difference below is enforced by the
script, so an artifact that ignores it is dropped or reported as a problem.

## The audited delta

`inventory --base BASE` resolves `BASE` to a commit, takes `merge-base(BASE, HEAD)`, and audits
`merge-base..HEAD` at the checked-out HEAD: the same delta a pull request shows against its base
branch. It records `base_input`, `base`, `merge_base`, `head`, and every change with its status
(`A`, `M`, `D`, `R`, `C`, `T`) and, for renames and copies, `old_path` under `range` in
`inventory.json`, and exits without writing anything when:

- `--scope` is also given: the audited delta is every changed path, never a subset of it;
- `BASE` does not resolve to a commit, or shares no merge base with HEAD;
- the range changes no files;
- a surviving changed path is not a regular file (a submodule gitlink, any symlink): it cannot be
  inventoried as itself, and omitting it or reading a symlink's target in its place would falsify
  the coverage claim;
- a tracked file differs from HEAD, staged or not. Evidence is verified against the working tree,
  so the tree must be HEAD. Untracked files are ignored and left out of the inventory.

Fix the cause and rerun. Do not pick another base to make the command succeed: the user or the host
names the base, and the report names exactly what was resolved. `verify` later reports a problem,
which withholds the score, when HEAD moves or a tracked file changes during the audit.

## Changed files and context

Changed maintained files are sharded and read in full; changed generated and vendored files are
boundary-checked; changed data and binary files are listed; deleted files appear in the range
inventory by path. Every other file is `context`: present for `grep_hits`, `trial`, blast radii,
`traces_to`, finding paths, and proof paths, but never sharded, never pending or uncovered, and
never counted as read coverage. Read a context file when a search leads you there; a context file
you never open is not a coverage gap.

## Cross-file pass into context

The shards see HEAD only, so the range's former names are yours to recover. Before searching,
inspect the merge-base diff (`git diff <merge_base> <head>`, the SHAs `inventory.json` records) and
read every deleted maintained file's merge-base version in full with `git show <merge_base>:<path>`;
do the same for a rename's `old_path` and for the removed side of each modified file when the diff
drops an export. From that, seed the old and new spellings of every exported or domain symbol,
import path, and vocabulary concept the range removed, renamed, or introduced into
`vocabulary.json`, then search HEAD for each of them.

For each changed symbol, path, and vocabulary concept, search the unchanged context and file a
`main.json` finding where the change leaves a search unable to reach what it should:

- reach and blast radius: callers, re-exports, and registrations of a renamed or new symbol;
- duplicate owners: the same definition surviving in an unchanged file;
- stale paths: references to a rename's `old_path` or to a deleted path;
- surviving former symbols: imports, calls, re-exports, registrations, and documentation that still
  name an export or domain term the range deleted or renamed;
- contracts: schemas, configuration, and documentation that name the changed concept;
- wiring: composition sites and entry points that should invoke the changed code;
- tests: the test or fixture that mirrors each changed file, and its feature terms.

A finding cites only what survives at HEAD: its `path`, `line`, and `evidence` come from a file in
the inventory, never from a deleted file's merge-base version, which `verify` cannot check. The
deleted or renamed path goes in `traces_to`.

Each changed generated or vendored file needs a `cross_shard_leads` entry in `main.json` whose
`paths` name that file and at least one other inventory path of a maintained class (`source`,
`test`, `config`, `script`, `schema`, `docs`): the source or generator you verified it against. An
unchanged context path qualifies and naming it does not count as reading it. `measure` reports a
changed boundary file whose leads name only the boundary file, a path outside the inventory, or
another generated, vendored, data, or binary path.

## Finding scope

Every finding states `scope` and `traces_to` explicitly; `verify` drops a finding that omits either.
There is no default on a changed file: a finding on an untouched pre-existing line of a modified
file is a causality judgment the reader has to make, not one the script infers from the path.

| Finding | `scope` | `traces_to` |
| --- | --- | --- |
| On a changed file, caused by the change | `change` | its own path |
| On an unchanged file, needed because of the change | `change` | a changed, `old_path`, or deleted path |
| Pre-existing debt beside the change, any file | `follow-up` | a changed, `old_path`, or deleted path |

A `change` finding on an unchanged file expands the pull request and counts like any other.
A `follow-up` is non-blocking: it is reported in its own section with its trace, and it is excluded
from the score, from packets, and from themes; `measure` reports a packet that lists one. File a
follow-up only where a changed path pulled the debt into the reading set. The rest of the
repository is out of scope; a whole-repository audit is a separate run.

## Applicable properties and the score

Record every property the change cannot exercise under `properties_not_applicable` with the
reason. Every remaining clean property still needs a `property_checks` entry naming the search or
count over the changed files and their context reach. The score uses the shared formula over the
applicable properties and `change` findings only; `audit.json` records `score.scope` as `change`.

## The narrower claim

The report title, coverage line, and field table state change scope, the base input and its SHA,
the merge-base and HEAD SHAs, changed-file coverage, the deleted count, and the searched-context
count; the card header and score read `CHANGE SCOPE` and `CHANGE SCORE`, and its receipt states the
changed-file, deleted, and context counts. Deliver it as a change-scope audit; the number says
nothing about the repository as a whole.
