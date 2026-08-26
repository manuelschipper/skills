# Work-directory artifacts

Everything the audit produces lives in one work directory outside the audited repository. The
script owns `inventory.json`, `shards.json`, `ledger.json`, `audit.md`, and the internal
`audit.json`. Shards own `shards/S-*.json` (contract in [shard-prompt.md](shard-prompt.md)). You
author the three files below; `audit.py measure` validates them and `audit.py render` prints the
durable Markdown from them. `audit.json` is scratch state, not a deliverable.

## `shards/main.json`

Your own findings from the cross-file pass, in the shard artifact shape with `"shard": "main"`.
`files_read`, `files_skipped`, and `properties_checked` may be empty; findings are verified exactly
like shard findings, and a finding identical to a shard's (property, path, line, evidence) is
dropped as a duplicate. In a change-range audit every finding also carries `scope` and
`traces_to`, and each changed generated or vendored file needs a `cross_shard_leads` entry here
naming it beside the maintained source or generator path it was verified against;
[change-range.md](change-range.md) defines both.

## `vocabulary.json`

Canonical concepts and their spellings. The initial file is a seed; after shard reading, every
`vocabulary_additions` entry must overlap a canonical concept by its concept name or any spelling,
or be recorded under `rejected`. Unadopted spellings are informational and appear in the
reconciliation ledger. `documented` is a proof path where documentation or agent guidance names the concept,
otherwise `null`. `reach` is filled after the search trials: a repository-relative proof path (or
`path:line`) when reached, `null` when tried and missed, and `"n/a"` when the surface does not
apply. A concept with any `null` reach value lists the accepted findings that explain the misses.

```json
{
  "concepts": [
    {
      "concept": "organization",
      "spellings": ["organization", "org", "tenant"],
      "documented": "AGENTS.md:18",
      "reach": {
        "owner": "src/organization/organization-repository.ts",
        "wiring": "src/api/routes/organization.ts:14",
        "contract": null,
        "tests": "tests/organization-access.test.ts",
        "absence": "n/a"
      },
      "findings": ["F-003"]
    }
  ],
  "rejected": [
    {
      "concept": "runner",
      "spellings": ["runner"],
      "reason": "Generic role word shared by unrelated subsystems."
    }
  ]
}
```

Run `audit.py trial --work W` after reconciliation to draft the documentation and five reach proofs;
confirm or replace every draft. `measure` counts case-insensitive hits per spelling, using
whole-word matching for spellings shorter than four characters or written in all capitals and
fixed-substring matching otherwise, so distinctive domain terms inside compound identifiers count.
Pure punctuation and single-character spellings are rejected. It verifies closure of additions,
all five reach keys, finding IDs for misses, and that each documented or reach proof contains a
spelling in its path or near its recorded line.
The report's reach matrix shows `[x]` for verified proof, `[ ]` for a tried miss, `[-]` for
`"n/a"`, `[!]` for an untried surface, and `[?]` for invalid proof. The Markdown prints each proof
path and the rejected candidates in its reconciliation ledger.

## `packets.json`

Dependency-ordered work units over accepted finding IDs from `ledger.json`. Finding IDs persist in
`ledger.json` across verification runs; editing a finding's identity fields creates a new ID. Group
findings that share files or symbols; keep each packet the size of one bounded change. `after` lists packet IDs
that must land first (cycles abort `measure`). Packet IDs are unique. `accept` is required: argv
arrays with the expected outcome in words; `measure` derives each packet's file and test lists
from its findings and their blast radii, and reports a missing or malformed `accept` as a problem.

```json
{
  "packets": [
    {
      "id": "P-01",
      "title": "Standardize organization vocabulary",
      "findings": ["F-003", "F-007"],
      "after": [],
      "creates": ["AGENTS.md"],
      "note": "canonical term recorded in AGENTS.md:14",
      "accept": [{"argv": ["git", "grep", "-nwE", "org|tenant", "--", "src"], "expect": "0 hits outside quoted strings"}]
    }
  ]
}
```

`creates` is optional and lists repository-relative files the packet will add; each path must be
absent from the inventory. Every accepted finding belongs to exactly one packet, except a
change-range `follow-up`, which belongs to none; `measure` reports
the unassigned and the duplicated. Make `title` an imperative recommendation. Do not use titles
such as "Choose the owner" or "Decide the boundary"; put alternatives and the recommended option on the design
finding, then title the packet with that recommendation.

## `narrative.json`

The prose the script cannot derive.

```json
{
  "verdict": "One or two sentences on the repository's greppability and its main weakness.",
  "method": "4 shards via the host's subagent tool, 1 re-dispatched; cross-file pass in the main session.",
  "themes": [
    {
      "title": "Give global and local owners explicit names",
      "explanation": "Names such as Project and Runtime only become meaningful after reading their surrounding modules. Name each type for the domain it owns.",
      "findings": ["F-001", "F-002"],
      "packets": ["P-01", "P-02"]
    }
  ],
  "property_checks": {
    "Keep names true as behavior changes": "74 renames in git log -p --diff-filter=M compared with call sites; import renames: git grep -n ' as ' -- '*.ts' = 0"
  },
  "properties_not_applicable": {"Record expected absence": "single-binary CLI with no external boundary"}
}
```

Keys in both maps are rubric headings copied exactly. `property_checks` is required for every
property with zero findings: the concrete check that supports "clean" (the search run, the count
seen), shown verbatim in the property ledger; `measure` reports a clean property without one as a
problem. Use `properties_not_applicable` rarely and say why.

`themes` is empty only when there are no accepted findings. Otherwise it contains at most three
entries, in recommended execution order, and partitions every accepted finding exactly once
(change-range follow-ups excluded).
`title` is the recommended action in plain language. `explanation` uses two or three short
sentences to combine the current friction, its consequence, and why the action helps. `findings`
and `packets` provide traceability to the detailed Markdown; each named packet must contain the
theme's findings. Keep IDs, paths, and severity codes out of both prose fields.

`measure` recomputes its own problems (vocabulary paths, packets, property checks) on every run,
so fixing an artifact and rerunning `measure` clears them; `verify` problems clear on rerunning
`verify`. Both commands exit nonzero while their output reports blocking problems.
