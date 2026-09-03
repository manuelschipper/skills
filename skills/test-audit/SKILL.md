---
name: test-audit
description: "Exhaustive repository audit for consequential coverage gaps and low-value test bloat, with every maintained file read and every finding tied to evidence."
disable-model-invocation: true
---

# Test audit

Audit whether a repository tests the failures that matter without making every helper, branch, or
piece of presentation pay a permanent test tax. This is a read-only audit. It produces two separate
judgments: **risk coverage** and **test signal**. Never substitute coverage percentages, test counts,
or source-to-test ratios for either judgment.

`scripts/audit.py` does the mechanical work: inventory, sharding, reconciliation, scoring, rendering,
and the final chat card. The agent does the risk analysis. Read [references/rubric.md](references/rubric.md)
before judging and [references/artifacts.md](references/artifacts.md) before writing shard artifacts.

## Start in chat

Before inspecting the repository, resolve what the request already says:

- Scope is the whole repository or one or more explicit repository-relative paths.
- Report delivery is chat-only when instructions prohibit storage, the named destination when one is
  given, and unresolved otherwise.

Post this card, replacing `{repository}` and any resolved values. If the destination remains
unresolved, wait for one reply.

```text
                              TEST AUDIT

  A read-only audit of whether {repository} tests consequential failures
  without accumulating incidental or redundant tests.

  Scope        {whole repository or explicit paths}
  Report       {destination or: Where should I store the Markdown report?}

  I will read every maintained file in scope, map risky production behavior
  to coverage, and make every existing test name the regression it earns.
```

Do not inspect the repository to invent a report destination, and write no audit artifacts inside
the repository.

## 1. Inventory

Choose a scratch directory `W` outside the repository, then run:

```sh
python3 /absolute/path/to/test-audit/scripts/audit.py inventory --repo . --work W
```

Add `--scope PATH` for each explicitly scoped path. Inspect the exclusion table. If maintained code
was classified as generated, vendored, data, or binary, rerun with `--override PREFIX=CLASS` until
every exclusion is truthful. Copy only the final `inventory:` line into chat.

## 2. Read every maintained file

For each shard, get the exact prompt:

```sh
python3 /absolute/path/to/test-audit/scripts/audit.py prompt --work W --shard S-01
```

When delegation is available and permitted, dispatch shards through the host's normal delegation
mechanism. Otherwise read them sequentially yourself. A shard writes only
`W/shards/S-NN.json`, reads every assigned file in full, inventories tests embedded in production
files as well as dedicated test files, and assesses every rubric property.

Do not run builds or tests in shard readers. Static reading establishes what each test claims to
protect; the main pass checks whether it is wired into the normal suite.

After each batch, run:

```sh
python3 /absolute/path/to/test-audit/scripts/audit.py verify --work W
```

Post its final `coverage:` line. Missing or skipped files leave the audit incomplete. Resume the
same reader when possible; otherwise read those files yourself and complete the artifact. Continue
until verification reports zero problems.

## 3. Cross-file pass

Read `W/ledger.json`, repository test configuration, and the ordinary test commands. Check what
isolated file readers cannot prove:

- every consequential production surface points to a real test, a focused manual check, or a
  defensible `not-warranted` decision;
- every test points back to production behavior and a concrete regression;
- overlapping tests genuinely protect different failures;
- tests are included in the normal suite rather than orphaned behind an unused command;
- mocks, fixtures, snapshots, and helpers do not create false confidence about a boundary they
  bypass.

When this pass changes a test verdict or coverage decision, update its owning shard artifact. Write
additional cross-file findings to `W/shards/main.json` using the same artifact shape, with empty
`assessments` and `files_skipped`. Rerun `verify` until it reports zero problems.

Running the suite is optional evidence, not a coverage measure. Run the documented command only
when it is safe and ordinary for the repository; record what ran in `narrative.json`. Never mutate
external systems merely to complete an audit.

## 4. Render and deliver

Write `W/narrative.json` with `verdict` and `method`, then render the report:

```sh
python3 /absolute/path/to/test-audit/scripts/audit.py render --work W --out /absolute/path/to/audit.md
```

The report contains independent risk-coverage and test-signal scores, all gap and bloat findings,
and the complete file ledger. A high score on one axis never offsets a low score on the other.

Inspect the report for secrets before delivery. For a stored report, print the final briefing:

```sh
python3 /absolute/path/to/test-audit/scripts/audit.py card --work W --report /absolute/path/to/audit.md
```

Reply with the card in one fenced `text` block and nothing after it. For chat-only delivery, return
the rendered Markdown, remove `W`, and leave no durable audit copy.
