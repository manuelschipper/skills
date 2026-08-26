---
name: brainfried
description: Turn dense material into a one-item-at-a-time conversation, making each piece easy to understand and respond to before moving on.
disable-model-invocation: true
---

# Brainfried

The user's brain is fried. Turn whatever dense material is at hand into a paced
conversation: one coherent item, one active thread, one explicit response at a time.

## Map

Before serving the first item, read every source in full and map it into an ordered
sequence. Keep an existing list when its items are already usable. Split an item that asks
the user to hold or judge several independent ideas at once; merge points that only make
sense together. Put prerequisites before anything that depends on them, preserve source
references, and account for every source point. Keep the map internal unless the user asks
for it.

## Serve

Serve exactly one item per turn, in this shape:

- `n/N` and a short title.
- The point, in one plain sentence.
- The smallest view that carries the evidence: a quote for exact wording, a table for
  comparison, a diff for what changes, an indented tree for structure, pseudocode for
  logic, a sequence or flow diagram for interaction, a focused HTML page when the point is
  visual or too dense for text. Prose alone only when the item has no structure to show.
- Your recommendation, visibly separate from the source, when the item calls for judgment.
- One prompt. Then stop.

Include only the context this item needs. Use plain words and define any term the source
leaves undefined. Do not preview later items.

## Resolve

Keep the current item active through questions, clarifications, alternatives, and
revisions; answer them from the source, not from memory. Advance only on an explicit
response: a decision for a judgment item, a go-ahead such as `next` for an understanding
item, or a request to skip or defer. If a reply does not clearly resolve the item, ask in
one line; never advance on a guess. When advancing, state the recorded response in one line
first. A response may resolve, split, or moot later items: update the map and say so when
N changes.

Record durable responses in the established system of record when writes there are
already authorized; otherwise keep them in context. A recommendation is advice, not
permission to implement it.

## Close

When the sequence is done, give a compact readback of every item and its response, including
anything skipped, deferred, or left unresolved.
