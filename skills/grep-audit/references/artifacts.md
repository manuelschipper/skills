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
dropped as a duplicate.

## `vocabulary.json`

Canonical concepts and their spellings. Written after the inventory so every shard uses the same
terms; `reach` is filled after the search trials and each value is a repository-relative path (or
`path:line`) that proves the search reached that surface, `null` when it did not, `"n/a"` when the
surface does not apply (an absence record for a concept that exists).

```json
{
  "concepts": [
    {
      "concept": "organization",
      "spellings": ["organization", "org", "tenant"],
      "reach": {
        "owner": "src/organization/organization-repository.ts",
        "wiring": "src/api/routes/organization.ts:14",
        "contract": null,
        "tests": "tests/organization-access.test.ts",
        "absence": "n/a"
      }
    }
  ]
}
```

`measure` counts `git grep -nw` hits per spelling and lists files whose path contains a spelling;
the report's reach matrix shows `[x]` for a path that exists, `[ ]` for `null`, `[-]` for `"n/a"`,
and `[?]` for a path not in the inventory (also listed under problems). The Markdown prints each
recorded proof path beneath the matrix.

## `packets.json`

Dependency-ordered work units over accepted finding IDs from `ledger.json`. Group findings that
share files or symbols; keep each packet the size of one bounded change. `after` lists packet IDs
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
      "note": "canonical term recorded in AGENTS.md:14",
      "accept": [{"argv": ["git", "grep", "-nwE", "org|tenant", "--", "src"], "expect": "0 hits outside quoted strings"}]
    }
  ]
}
```

Every accepted finding belongs to exactly one packet; `measure` reports the unassigned and the
duplicated. Make `title` an imperative recommendation. Do not use titles such as "Choose the
owner" or "Decide the boundary"; put alternatives and the recommended option on the design
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
entries, in recommended execution order, and partitions every accepted finding exactly once.
`title` is the recommended action in plain language. `explanation` uses two or three short
sentences to combine the current friction, its consequence, and why the action helps. `findings`
and `packets` provide traceability to the detailed Markdown; each named packet must contain the
theme's findings. Keep IDs, paths, and severity codes out of both prose fields.

`measure` recomputes its own problems (vocabulary paths, packets, property checks) on every run,
so fixing an artifact and rerunning `measure` clears them; `verify` problems clear on rerunning
`verify`.
