# Test-value rubric

The audit asks two different questions. **Risk coverage** asks whether consequential failures are
protected. **Test signal** asks whether each maintained test earns its cost. Neither test quantity
nor line coverage answers either question.

Impact is HIGH when failure can lose data, cross an authority boundary, perform the wrong external
side effect, corrupt durable state, or break a primary workflow. It is MED when a supported workflow
fails recoverably or gives materially wrong results. It is LOW when the failure is contained and
minor but still worth automated protection.

For bloat and false confidence, HIGH means the suite materially misrepresents safety or routinely
blocks important changes, MED means repeated or expensive maintenance without matching confidence,
and LOW means an isolated low-value test.

## Risk coverage

### Cover consequential behavior

Map user-visible contracts and domain invariants to tests. A coverage gap needs a plausible failure,
not merely an untested function, helper, branch, or line. Straight-line glue and compiler-enforced
facts may need no dedicated test.

### Cover irreversible and external boundaries

Give highest scrutiny to destructive filesystem operations, durable writes, authentication and
authority, secrets, network protocols, parsers of untrusted input, subprocess control, and external
side effects. Test the repository-owned decision at the boundary; do not require live third-party
systems when a faithful local boundary suffices.

### Cover state transitions and recovery

Exercise cancellation, retry, timeout, partial failure, restart, persistence, concurrency, and
state-machine transitions when the product implements them. Happy-path coverage does not stand in
for recovery behavior.

### Cover plausible regressions

A regression test earns its place when the failure could recur through an ordinary edit and its
consequence matters. Preserve tests for previously observed failures when they protect a stable
contract; a historical bug alone does not justify pinning an obsolete implementation.

### Keep coverage executable

Verification counts only when the normal repository test command discovers and runs it. Flag
orphaned tests, stale fixtures, skipped cases without a current reason, and mocks that bypass the
behavior they claim to cover as false confidence.

## Test signal

### Make each test earn its maintenance

Every test should name a concrete regression and the consequential behavior or risky boundary it
protects. A test with no such failure is a deletion candidate even when it is short or currently
green.

### Assert behavior rather than implementation

Prefer observable outcomes, state transitions, durable effects, and machine-readable contracts.
Tests coupled to private call order, helper shape, internal fields, or mock choreography should be
rewritten when harmless refactors can fail them without changing behavior.

### Keep presentation checks proportional

Use focused manual verification or existing behavioral coverage for copy, spacing, alignment,
display-only formatting helpers, and static presentation inventories. Exact bytes deserve assertions
when they are the contract, such as protocol tokens, serialized formats, error codes, and CLI flags.

### Remove overlapping coverage

Keep multiple tests only when each protects a distinct failure. Delete a narrow unit test already
subsumed by credible integration coverage, or consolidate nearby cases when separate setup and
assertions add maintenance without new confidence.

### Keep setup and matrices proportional

Test setup, fixtures, mocks, parameter matrices, and helper layers should cost less to understand
than the risk they protect. Keep boundary cases that change behavior; prune permutations that merely
inventory every value, branch, field, or helper.

## Verdicts

- `keep`: the test protects a distinct consequential regression at proportionate cost.
- `delete`: no consequential regression remains, or stronger coverage fully subsumes it.
- `consolidate`: the behavior matters but nearby tests repeat setup or equivalent cases.
- `rewrite`: the behavior matters but the test is brittle, indirect, orphaned, or falsely confident.

For production surfaces use `covered`, `partial`, `missing`, `manual`, or `not-warranted`. Manual and
not-warranted decisions require a concrete reason. Partial and missing coverage require a gap
finding.

## Scoring

Risk coverage weights high-, medium-, and low-impact surfaces 4, 2, and 1. Covered receives full
credit, partial half, and missing none; manual and not-warranted decisions remain visible but are
unscored. Test signal gives full credit to keep, half to consolidate or rewrite, and none to delete.
These are directional summaries of the evidence ledger, not targets. Always read the findings and
counts beside them.
