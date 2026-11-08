# Architecture Decision Records (ADR)

An ADR captures **one** significant decision, its context and its
consequences. ADRs are immutable once merged: if a decision changes,
add a new ADR that supersedes the old one and mark the old file with a
link.

We follow [MADR](https://adr.github.io/madr/) 2.1 — the same shape used
by the original example: **Context / Decision / Consequences**.

## When you need an ADR

Write one when you change:

- a layer contract or the data types in `core/types.py`;
- a dependency that becomes part of the public surface;
- a protocol (Free-D, NDI, MOS) or a vendor integration strategy;
- the latency, colour or frame-rate budget;
- repository layout or the release process.

Skip ADRs for bug fixes, refactors that preserve behaviour, docs and
tooling tweaks.

## File naming

```
docs/adr/NNNN-short-kebab-title.md
```

`NNNN` is a zero-padded, ever-increasing counter. Example:
`0002-use-ndi-for-the-first-capture-source.md`.

## Template

```markdown
# NNNN. Title

Date: YYYY-MM-DD

## Status

Proposed | Accepted | Superseded by NNNN | Deprecated

## Context

What is the issue that motivates this decision? What forces are at
play (technical, broadcast, commercial)?

## Decision

What was decided, stated as "We will …".

## Consequences

### Positive
- …

### Negative / risks
- …
```

## Workflow

1. Open a pull request that adds only the ADR (plus a link from
   `docs/index.md` if it deserves visibility).
2. Review focuses on whether the *context* is honest, not on whether we
   like the decision.
3. Merge together with the code that implements it.

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-monocular-depth-contract.md) | Monocular depth is relative, not metric | Accepted |
| [0003](0003-pull-based-capture-contract.md) | Pull-based capture contract | Accepted |
| [0004](0004-godot-blender-instead-of-ue5.md) | Godot + Blender instead of Unreal Engine 5 | Accepted |
| [0005](0005-calibration-ccm-vs-grid.md) | ColorChecker to CCM 3x3, manual 125-point grid dropped | Accepted |
| [0006](0006-backplate-occlusion.md) | Backplate + depth-quad occlusion for MVP | Superseded by 0009 |
| [0009](0009-3d-studio-occlusion.md) | 3D studio occlusion (mesh + cameras) | Accepted |
