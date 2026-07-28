# 0001. Firestore Only, No Redis

Date: 2026-07-28
Status: Accepted

## Context

v1 ran Memorystore Redis for vote tallies, with an atomic Lua script doing
validation, dedupe, and tally in one round-trip (v1 ADR 0003). It was fast and
correct, but it cost ~$40-60/month fixed for the instance plus a VPC connector,
and it forced every Cloud Run service onto a VPC.

v2 also needs a guarantee v1 achieved through invalidation: when a generation
finishes, the radio service must see the song as available immediately.

## Decision

Use Firestore for everything.

- Vote dedupe is a document create at `polls/{pollId}/votes/{uid}`. A create
  fails if the document exists, so dedupe is atomic without a transaction and
  without single-document write contention.
- Tallies are computed once at poll close into an immutable `tallySnapshot`,
  because the design hides results until the poll closes. There is no live
  tally read path to make fast.
- Firestore is strongly consistent, so the worker's `status: ready` write is
  visible to the radio service's very next read. "Reflect immediately" is the
  store's own guarantee rather than something the application arranges.

## Consequences

- No VPC, no Redis bill, no second datastore to reason about.
- Vote writes are slower than a Redis round-trip (tens of milliseconds against
  sub-millisecond). Irrelevant at one vote per user per poll.
- Rotation correctness now rests on Firestore transactions plus a monotonic
  `version` field rather than on Lua atomicity. Both the replayed-task and the
  concurrent-instance cases are covered by emulator tests.
- If a live tally is ever wanted during an open poll, this decision must be
  revisited: COUNT aggregations on every listener poll would be the wrong
  shape, and a cache would reintroduce the freshness problem Redis solved.
