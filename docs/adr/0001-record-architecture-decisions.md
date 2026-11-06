# 0001. Record architecture decisions

Date: 2026-11-06

## Status

Accepted

## Context

StageForge sits between broadcast hardware and machine-learning
components. Decisions in this space — which tracking protocol, which
AI keyer, which latency budget — are expensive to reverse: they are
embedded in show setups, vendor contracts and calibration routines.

The team needs a way to record *why* a choice was made so that a
newcomer six months later can tell the difference between a constraint
we accepted and an accident we inherited. Discussion lives in pull
requests, which are hard to discover and easy to lose.

Alternatives considered:

- **Wiki pages** — easy to edit, easy to lose, no review gate.
- **Commit messages** — chronological but not navigable by topic.
- **Nothing** — cheap now, expensive later.

## Decision

We will record significant architectural decisions as Architecture
Decision Records, one file per decision, stored in `docs/adr/` in this
repository, using the MADR 2.1 shape (Context / Decision /
Consequences).

Concretely:

1. File name `NNNN-short-kebab-title.md`, `NNNN` monotonically
   increasing, no reuse of numbers.
2. ADRs are markdown, live next to the code they affect's
   documentation, and are reviewed in the same pull request as the
   change that they describe.
3. ADRs are immutable after merge. Changing a decision means writing a
   new ADR and pointing the old one's status at it.
4. The process itself is described in
   [README.md](README.md) so it is discoverable.

## Consequences

### Positive

- Rationale travels with the code and survives the people who made the
  decision.
- Reviewers can challenge assumptions before they harden.
- Superseded decisions stay visible instead of silently disappearing,
  which prevents re-litigating settled questions.
- The docs build (`mkdocs`) publishes ADRs alongside user docs, so
  integrators see the constraints too.

### Negative / risks

- Small overhead per significant change; authors may skip it under
  deadline pressure.
- ADR sprawl if trivial decisions are recorded — the "when you need an
  ADR" list in `docs/adr/README.md` exists to bound this.
- Files are never rewritten, so the repo accumulates stale documents
  unless status lines are maintained honestly.

### Neutral

- Tooling: none required beyond markdown and the pull request flow.
  Any MADR-compatible tool can be adopted later without migration.
