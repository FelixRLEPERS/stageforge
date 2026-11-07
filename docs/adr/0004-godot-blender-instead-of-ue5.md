# 0004. Godot + Blender instead of Unreal Engine 5

Date: 2026-11-07

## Status

Accepted — supersedes the UE5 wording of L4 in
`docs/02-architecture.md`, `docs/06-compositing-ar.md`,
`docs/08-integrations.md` and `docs/11-roadmap.md`.

## Context

The scaffold described L4 (Compositing & AR) as rendering in Unreal
Engine 5 through a vendor bridge (Zero Density / Aximmetry / Mo-Sys).
UE5 in this role has three costs:

- **weight** — a full game-engine install per render station (and a
  licence per seat beyond the free tier), where the actual job is one
  1920x1080 AR layer over a keyed plate;
- **distance from the assets** — UE scenes would be authored in tools
  this project does not use, while the assets needed here are small
  `.glb` props prepared independently of the show;
- **tooling gap** — the repo's automation (MCP servers, headless CI
  runs) can drive Godot and Blender directly and headlessly; UE cannot
  be driven from this toolchain.

The delivery rule for every milestone is *something observable on a
real monitor*. Godot 4.5 (portable build already on this machine)
renders the same scene windowed **and** headless, so smoke tests need
no GPU and no licence. Blender 5.0.1 (also already present) covers
asset prep; its GPL applies to the tool, never to the files it
produces.

## Decision

We will:

1. render the AR layer in **Godot 4.4+** as a separate rendering
   layer in `godot/`, driven by the Python pipeline over a file-backed
   RGBA stream (`output.mode: "godot"` → `GodotOutputSink`, consumed
   by `godot/receiver.gd`; transport details in `docs/06`);
2. prepare assets in **Blender 4.2+** (`blender/`) — offline `.glb`
   export only (`export_for_godot.py` + MCP), never in the real-time
   path;
3. send the composite to air through the vendored `godot-ndi` addon
   (NDI source `StageForge_Godot`, MPL-2.0), with Spout (`spout-gd`)
   as the documented alternative;
4. keep the Python pipeline the single source of truth: Godot never
   captures, segments or keys — it receives frames and renders; the
   protected tests and every existing interface stay untouched.

## Consequences

### Positive

- Renderer is free (MIT), portable, and scriptable headless — smoke
  tests run in CI without a GPU (`godot --headless`).
- Asset path (Blender → glTF 2.0 `.glb`) is the industry default; no
  proprietary scene format, alpha carried through automatically.
- Both tools already exist on the target machine as portable builds —
  nothing to install per seat.
- The Python pipeline remains the testable core; the Godot layer is
  replaceable and the transport decision leaves NDI one config switch
  away (`output.mode: "ndi"`).

### Negative / risks

- NDI Runtime is proprietary and **absent on the dev machine**
  (`HKLM\SOFTWARE\NDI` missing), so the NDI leg is unverifiable here —
  `godot ndi: SKIP` is the expected line until the Runtime is
  installed; documented with the OBS acceptance steps in
  `godot/README.md`.
- Godot's renderer is not UE: no UE lighting/feature parity; an
  eventual UE migration would re-author the scene.
- The vendored `godot-ndi` addon is MPL-2.0 (file-level copyleft) —
  kept unmodified with its `LICENSE` and `NOTICE.md`; the NDI Runtime
  it needs is a separate proprietary download.