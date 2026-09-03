# Audit artifacts

All artifacts live in the scratch directory outside the audited repository. `audit.py inventory`
creates `inventory.json`, `shards.json`, and `shards/`. Readers create one shard artifact each. The
main pass may add `shards/main.json`. `verify` creates `ledger.json`; `render` consumes that ledger
and `narrative.json`.

## Shard artifacts

One assessment is required for every assigned file read in full. Tests may live in any file, so
enumerate embedded tests as well as dedicated test files. `no_test_cases_reason` and
`no_risk_surfaces_reason` explain empty arrays; they are not substitutes for investigating the file.

```json
{
  "shard": "S-01",
  "properties_checked": ["every rubric heading, copied exactly"],
  "assessments": [
    {
      "path": "src/session.ts",
      "lines": 120,
      "test_cases": [
        {
          "line": 84,
          "name": "resume rejects a corrupt checkpoint",
          "regression": "a corrupt checkpoint is accepted and poisons the resumed session",
          "risk": "high",
          "production": ["src/session.ts"],
          "overlap": [],
          "verdict": "keep",
          "reason": "protects durable recovery at the parser boundary"
        }
      ],
      "no_test_cases_reason": null,
      "risk_surfaces": [
        {
          "line": 18,
          "behavior": "resume validates a durable checkpoint before restoring it",
          "failure": "corrupt state enters the live session",
          "impact": "high",
          "coverage": "covered",
          "tests": ["src/session.ts:84"],
          "reason": "the test crosses the same parser used by production"
        }
      ],
      "no_risk_surfaces_reason": null
    }
  ],
  "files_skipped": [],
  "findings": [
    {
      "kind": "gap | bloat | false-confidence",
      "severity": "HIGH | MED | LOW",
      "property": "one rubric heading, copied exactly",
      "path": "src/session.ts",
      "line": 18,
      "evidence": "verbatim evidence at or near the line, at most three lines",
      "observation": "the concrete problem and consequence",
      "recommendation": "one bounded action",
      "related_paths": ["src/session.test.ts"]
    }
  ]
}
```

Rules enforced by `verify`:

- assessed and skipped paths exactly cover the shard assignment;
- every rubric property is declared;
- line numbers and related paths belong to the inventory;
- evidence occurs within two lines of `path:line` after whitespace normalization;
- every non-`keep` test verdict has a nearby bloat or false-confidence finding;
- every `partial` or `missing` surface has a nearby gap finding;
- `covered` surfaces name test evidence, and empty assessment arrays carry reasons.

`shards/main.json` uses the same top-level shape with `"shard": "main"`, complete
`properties_checked`, empty `assessments` and `files_skipped`, and only cross-file findings.

## Narrative

```json
{
  "verdict": "One or two sentences stating both the coverage and signal result.",
  "method": "How files were read, whether readers were delegated, and what test command was run."
}
```

The script derives counts, scores, file coverage, and finding sections. Do not duplicate them in the
narrative.
