# Security Policy

## Supported versions

StageForge is pre-release. Security fixes are applied to the latest
commit on `main` and, once releases exist, to the latest minor line.

| Version | Supported          |
| ------- | ------------------ |
| `main`  | :white_check_mark: |
| `< 0.1` | :x:                |

## Reporting a vulnerability

Please do **not** open a public issue for security vulnerabilities.

Email **security@stageforge.studio** with:

- a description of the issue and its impact;
- steps to reproduce or a proof of concept;
- affected version / commit hash;
- any suggested mitigation, if you have one.

You will get an acknowledgement within 3 working days. We will work
with you on coordinated disclosure and credit you in the advisory
unless you prefer to remain anonymous.

## Scope notes

StageForge handles live broadcast feeds and third-party integrations
(Godot Engine, DeckLink, NDI). Vulnerabilities in those upstream
projects should be reported to their vendors; we will help relay them
if needed.
