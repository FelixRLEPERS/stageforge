# StageForge Godot render layer

Real-time AR rendering for StageForge (ADR-0004: Godot + Blender instead
of Unreal Engine 5). This folder is **self-contained** — the Python
pipeline (`src/stageforge/`) does not depend on it; the two sides talk
through the RGBA stream described in `docs/06-compositing-ar.md`.

## Requirements

| | |
|---|---|
| Godot | **4.4+** (addon `compatibility_minimum=4.4`); tested on portable 4.5.1 at `D:\AstraForge\runtime\godot\Godot_v4.5.1-stable_win64.exe` |
| NDI Runtime | **required for `NDIOutput`** — free from <https://ndi.video/tools/ndi-core-suite/>; the godot-ndi addon auto-detects the installer. Without it the NDI leg logs `godot ndi: SKIP`, while the shared-memory stream (`GodotOutputSink` → `receiver.gd`) works independently |
| godot-ndi addon | vendored at `addons/godot-ndi/` (MPL-2.0, Windows binaries; see `LICENSE` + `NOTICE.md`) |

Godot is portable — no installer, no pip, nothing to add to PATH.

## Run

Editor:

```powershell
& 'D:\AstraForge\runtime\godot\Godot_v4.5.1-stable_win64.exe' --path godot
# or: open godot/project.godot in the Godot Project Manager, then F5
```

Command line:

```powershell
& 'D:\AstraForge\runtime\godot\Godot_v4.5.1-stable_win64_console.exe' --path godot
```

Headless smoke test (CI-friendly; exits after 150 frames):

```powershell
& 'D:\AstraForge\runtime\godot\Godot_v4.5.1-stable_win64_console.exe' `
  --headless --path godot --quit-after 150
```

Expected output:

```
StageForge Godot ready, NDI output: StageForge_Godot
godot smoke: viewport contract PASS (1920x1080, transparent_bg=true)
godot ndi: OK source 'StageForge_Godot'     (or: SKIP, see below)
godot fps: avg=30.x over 120 frames (target >= 25)
```

## Scene

```
Main (main.gd)
└─ ViewportHost      SubViewportContainer, stretch=false — the SubViewport
   │                 stays pinned at 1920x1080 (broadcast contract), the
   │                 window is only a debug view
   └─ SubViewport    1920x1080, transparent_bg=true, UPDATE_ALWAYS
      ├─ NDIOutput   added by main.gd at runtime when the addon loads
      └─ Scene3D
         ├─ Camera3D
         ├─ DirectionalLight3D
         └─ Cube     placeholder AR object (replaced by .glb assets)
```

`main.gd` validates the contract on every start (`assert`) and measures
average fps over 120 frames (`fps >= 25` required by the plan).

## Check the NDI source in OBS

1. Install the NDI Runtime (link above) — without it the project logs
   `godot ndi: SKIP` and no source appears.
2. Start the project (editor F5 or CLI).
3. OBS Studio → *Tools → NDI Source* (obs-ndi plugin) →
   **Source name: `StageForge_Godot`**.
   Alternative: NDI Studio Monitor (Part of NDI Tools) — same name.
4. **Alpha check:** add a solid-colour source *underneath* the NDI
   source — the empty areas of the 1920x1080 frame must show the colour
   through (transparent background), the cube must stay opaque.

## MCP tooling (OpenCode)

`opencode.json` (local config, not committed) wires two local servers —
absolute paths, restart the OpenCode session once after editing:

| server | command | purpose |
|---|---|---|
| `godot` | `node C:\Users\FelixR\tools\godot-mcp\build\index.js` + `GODOT_PATH` | project/scene inspection, debug output (18 tools) |
| `blender` | `uvx mcp-for-blender` | live Blender control — see `blender/README.md` |

Verified live: `godot.get_godot_version` → `4.5.1.stable.official`,
`blender.get_addon_status` → Blender 5.0.1, protocol 15/15.

## Known limitations (measured on this machine)

- **NDI Runtime is not installed** on the StageForge dev machine
  (`HKLM\SOFTWARE\NDI` absent) → `godot ndi: SKIP` is the expected
  line today; install the Runtime and rerun to get the source. The addon
  DLLs are vendored, nothing else to download.
- No NDI/Spout verification was possible without the Runtime — the OBS
  steps above are the manual acceptance test for the machine that has it.
  Alternative if NDI is unwanted: [spout-gd](https://github.com/you-win/spout-gd)
  (Windows shared-texture output, same pattern: add the node inside the
  SubViewport).
- fps measured with the placeholder cube: **30.8 avg** (capped at
  `run/max_fps=30`, broadcast cadence). Scenes with heavy AR geometry
  must be re-measured in the pilot — optimisation is explicitly out of
  scope for this commit (plan rule: 30-minute cap, document, don't tune).

## Layout

| Path | Purpose |
|---|---|
| `project.godot` | gl_compatibility renderer, 1920x1080, `max_fps=30` |
| `main.tscn` / `main.gd` | scene contract + NDI wiring + smoke asserts |
| `receiver.gd` | reads the Python RGBA stream (`GodotOutputSink`, seqlock) |
| `assets/` | `.glb` exports from `blender/` (`test_*.glb` ignored) |
| `addons/godot-ndi/` | vendored NDI output addon (MPL-2.0) |
| `tests/` | smoke scene for Phase 5 |

## Licenses

- Godot Engine: MIT.
- `addons/godot-ndi/`: MPL-2.0 (file-level copyleft; kept unmodified
  with its `LICENSE` and `NOTICE.md` — NDI is a registered trademark of
  Vizrt). The NDI Runtime itself is a separate proprietary download.
- StageForge code in this folder: Apache-2.0 with the rest of the repo.
