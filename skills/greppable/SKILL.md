---
name: greppable
description: "The properties that make a codebase greppable: code a grep-first agent can find, understand, and safely change by searching domain terms. Use as context for architecture reviews, refactors, naming, module boundaries, or writing agent-ready code."
disable-model-invocation: true
---

# Greppable

A codebase is greppable when an agent that knows the domain words can find a concept, its
production wiring, its contract, and its verification surface by searching, without
reconstructing the architecture first. Apply these properties to reviews, refactors, and new
code. Use the shortest name and smallest module that remain distinctive and cohesive; more words
and more files are not goals by themselves.

## Search addresses

### Use distinctive domain names

Paths, filenames, exported symbols, methods, constants, and types are search addresses. Methods
especially need distinctive names because no import names them. Give an export enough domain words
to grep uniquely in its effective namespace. Two to four words often work in a flat namespace; a
qualified name such as `stripe.NewClient` already carries its package context. Give generic verbs
their object, then stop when the name is distinctive.

- Bad: `create()`, `process()`, and `validateConfig()` each return many unrelated matches.
- Good: `createStripeClient()` and `validateSmtpConfig()` identify the concept in one search.

### Use one spelling per concept

Repeat the same domain term wherever a concept appears. Reuse the repository's established
vocabulary instead of introducing synonyms that split future searches.

- Bad: the same tenant is called `organization`, `org`, and `customer` across code and tests.
- Good: `organizationId`, `OrganizationRepository`, and `organization-access.test.ts` share one
  search term.

### Keep names true as behavior changes

Rename a symbol when its behavior or audience changes, in the same change. Do not rename on import:
`import { x as y }` gives the concept a second identity that a search for `x` never finds.

- Bad: `_parsePayload()` becomes a public validator but keeps its private, incomplete name, or is
  imported as `check` elsewhere.
- Good: rename it to `validateWebhookPayload()` and use that name at every call site.

### Give each definition one home

Move shared behavior to one concept-named owner and import it. Delete the old definition in the
same change so searches cannot land on competing implementations.

- Bad: `calculateNotificationRetryDelay()` is copied into the API, worker, and test helpers.
- Good: `notification-retry-policy.ts` owns `calculateNotificationRetryDelay()` and every caller
  imports it.

### Make paths and exports say where code lives

Name files and directories after their domain, not only their role. Do not rely on a module path to
rescue a generic exported name: search hits often omit the import that provides that context. A
rigid, repository-wide convention can let the path carry meaning, such as every contract file
exporting `Input` and `Output`. Keep entry-point files thin and list re-exports explicitly.

- Bad: `shared/utils.ts` exports `parse`, while `index.ts` hides it behind `export *`.
- Good: `billing/parse-invoice-currency.ts` exports `parseInvoiceCurrency`, and the entry point uses
  `export { parseInvoiceCurrency } from "./parse-invoice-currency"`.

### Keep operational strings whole

Write event names, flags, and error codes as complete literals, and start diagnostic messages with a
stable literal prefix. A value seen in a log or request should grep back to its definition without
reconstructing interpolation.

- Bad: composing an event from `${provider}`, `${entity}`, and `${action}`, or an error from a
  variable prefix, hides the emitted text.
- Good: `github.pull_request.merged` exists as a complete literal, and
  `Webhook signature mismatch for ${id}` starts with a literal prefix.

## Contracts that stop further reading

### Use precise identity and state types

Make invalid combinations fail at compile or validation time. Prefer branded IDs or newtypes over
interchangeable primitives, discriminated unions over clusters of nullable fields, and descriptive
type names over `Data` or `Ctx2`. Avoid `any`, which removes the contract entirely.

- Bad: `transferOwnership(userId: string, orgId: string)` accepts swapped arguments, while
  `{ sentAt?: Date; error?: string }` permits contradictory states.
- Good: `transferOwnership(userId: UserId, orgId: OrgId)` and
  `{ kind: "sent"; sentAt: Date } | { kind: "failed"; error: DeliveryError }` state the contract.

### Encode authority and validate boundaries

Require the narrow capability an operation needs, and validate untrusted input where it enters the
system. Downstream code should receive a trusted domain value rather than repeat defensive checks.

- Bad: `deleteOrganization(db: Database, input: any)` relies on callers to scope and validate it.
- Good: `deleteOrganization(db: OrganizationScopedDb, input: DeleteOrganizationInput)` accepts a
  parsed input and a capability that cannot access another organization.

### Put the searchable explanation at the definition

Place a short doc comment on each export stating the sharpest constraint the signature cannot show:
units, timezone, ownership, ordering, or source of truth. Include the ordinary spaced phrase a reader
might search, because `RetryDelay` does not match a search for `retry delay`.

- Bad: a wiki says the delay uses milliseconds, while
  `calculateNotificationRetryDelay(value: number)` has no nearby explanation.
- Good: `/** Calculates the notification retry delay in milliseconds. */` sits immediately above
  `calculateNotificationRetryDelay()`.

### Make imports readable as contracts

An orchestrating module should make sense from imported names, signatures, and nearby doc lines.
Readers should not have to open every dependency to discover what a call does.

- Bad: `import { run as handle } from "@shared/core"` followed by `handle(data)`.
- Good: `import { deliverNotificationEmail } from "@notifications/email-delivery"` followed by a
  call whose input and result types explain the boundary.

## Cohesion and ownership

### Give each cohesive concept one boundary

Put the code that answers one domain question in one named home. Avoid both a monolith that hides
unrelated concepts and tiny files that scatter one answer across many reads.

- Bad: one email route function contains SMTP settings, message rendering, folder fallback, and
  delivery history; the retry rule is separately fragmented across eight one-function files.
- Good: each email concept has a module, while private helpers used only by the retry policy remain
  inside `notification-retry-policy.ts`.

### Treat line count as a diagnostic, not a design rule

A hand-written file is too long when a search for one concept lands amid unrelated behavior, or a
reader must load large irrelevant regions to understand a change. Length alone is a prompt to look,
not a reason to split: a file in the high hundreds of lines deserves a check that it still answers
one domain question, and a file in the thousands rarely does. Split by domain question and owner,
not by a quota. Generated code, declarative data, schemas, or one linear algorithm can be longer
when they still answer one question.

- Bad: `email_helpers.py` has 1,800 lines shared by four features, so every email search lands on the
  same wall of code.
- Good: `smtp_settings.py`, `message_rendering.py`, `folder_fallbacks.py`, and
  `delivery_history.py` separate those questions; a cohesive 650-line `mime_parser.py` stays whole.

### Show cross-cutting composition

Give a cross-cutting feature one visible composition site that names its parts and runtime entry
points. Searching the feature should reach both its definitions and where production invokes them.

- Bad: importing modules triggers hidden self-registration into a global callback registry.
- Good: `composeNotificationDelivery({ retryPolicy, payloadSigner, deliveryStore })` is called from
  `startNotificationWorker()`.

### State ownership and dependency direction

Give each package or directory one responsibility. Owners communicate through explicit contracts,
and dependencies point one way toward stable boundaries. Avoid circular imports, hidden callbacks,
and shared mutable state.

- Bad: billing and notifications import each other's internals and coordinate through
  `global.currentCustomer`.
- Good: both depend on an `InvoicePaid` contract owned at their boundary; billing publishes it and
  notifications consumes it.

### Keep orchestration visible and side effects owned

Orchestrators should sequence domain-named operations at one abstraction level. Leaf modules own
their I/O so a reader can identify database, network, filesystem, and clock effects from names and
contracts.

- Bad: a route handler mixes SQL, template rendering, HTTP delivery, retries, and audit logging in
  one control flow.
- Good: it calls `loadPendingNotification()`, `renderNotificationEmail()`,
  `sendNotificationEmail()`, and `recordNotificationDelivery()`; each side effect has one owner.

## Verification and dead ends

### Make tests and fixtures answer to feature terms

Name tests and fixtures after the production concept. Colocate them when project conventions allow;
otherwise mirror the source path so the same search finds behavior and verification.

- Bad: `misc.test.ts` uses `sample.json` to cover notification retry behavior.
- Good: `notification-retry-policy.test.ts` and `notification-retry-policy.fixture.json` sit beside
  or mirror `notification-retry-policy.ts`.

### Record expected absence

Grep cannot find behavior that does not exist. Document deliberately unsupported behavior where a
reader would search for it, using the same domain phrase.

- Bad: received email HTML is intentionally not sanitized, but nothing records that decision, so a
  reviewer searches until its budget expires.
- Good: the email ingestion boundary states `Unsupported: received email HTML sanitization` and
  explains the trust assumption.

### Remove obsolete paths and mark retained dead ends

Delete an obsolete implementation when code moves. If the project explicitly requires a deprecated
API to remain, mark it at the definition and point directly to the current path.

- Bad: `sendEmail()` and `deliverNotificationEmail()` remain live with no indication of which one
  production uses.
- Good: remove `sendEmail()`; if it must remain as a declared deprecated API, annotate it with
  `@deprecated Use deliverNotificationEmail`.

### Record repository-wide search conventions

Put non-obvious vocabulary, source locations, generated-code boundaries, and naming conventions in
the repository's agent guidance. This gives fresh sessions the terms needed for their first search.

- Bad: only the team knows that `organization` is the canonical term and `generated/api` is not
  hand-edited.
- Good: `AGENTS.md` records those facts once and points to the owning modules.

## Completion check

Before completing a review, refactor, or new implementation, account for every applicable property:

- A domain phrase reaches the owner, production wiring, contract, tests, and intentional absences.
- Each new exported name resolves cleanly without relying on its import path.
- Invalid identities, states, inputs, and authority fail at a typed or validated boundary.
- The one constraint a signature cannot express is searchable at the definition.
- Operational strings have a complete literal or stable literal prefix.
- Behavior changes carry matching name changes.
- Moved code is gone from its old home; retained deprecated paths point to the current owner.
- Each changed concept has a bounded reading set, and unusually long files have a cohesive reason.
