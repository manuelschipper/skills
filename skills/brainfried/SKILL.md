---
name: brainfried
description: Turn dense material into a one-item-at-a-time conversation, making each piece easy to understand and respond to before moving on.
disable-model-invocation: true
---

# Brainfried

The user's brain is fried. Turn whatever dense material is at hand into a paced
conversation: one coherent item, one active thread, one explicit response at a time.

## Record

Before mapping or serving, establish how to handle decisions. When the user has already
chosen conversation-only or named a durable destination, follow that instruction.
Otherwise, identify the appropriate system of record when the environment makes one clear
and ask one brief question: keep decisions in the conversation only, or record them there?
When no system is clear, ask whether to record them durably and, if so, where. Stop until
the user answers.

Record decisions only when the user explicitly opts in, and only in the destination they
approve.

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
  logic, a sequence or flow diagram for interaction. Prose alone only when the item has no structure to show.
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

Keep responses in context throughout. When the user opted into durable recording, write
resolved responses and the final readback to the approved system of record. Approval to
record decisions is not permission to implement a recommendation.

## Close

When the sequence is done, give a compact readback of every item and its response, including
anything skipped, deferred, or left unresolved.
