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
godot studio: environment + floor/walls + 3 lights + plate built
godot ar: 4 topic(s) loaded from res://ar_config.json
godot hud: ready (topic, fps, key map)
StageForge Godot ready, NDI output: StageForge_Godot
godot smoke: viewport contract PASS (1920x1080, studio opaque)
godot ndi: SKIP (NDI Runtime / addon unavailable)
godot receiver: frame #1 1620x911 seq=20 (30 fps)
godot fps: avg=30.x over 120 frames (target >= 25)
```

## Virtual studio demo

Keys (US or RU layout — the handler reads `physical_keycode`):

| Key | Action |
|---|---|
| `1` `2` `3` `4` | switch topic: finance, sports, weather, breaking |
| `Space` | hide / show the AR group |
| `Esc` | quit |

Two environment-gated switches exist for repeatable verification, both
no-ops when unset:

| Variable | Effect |
|---|---|
| `STAGEFORGE_GODOT_SHOT=<path.png>` | render one frame to PNG and quit — deterministic screenshot |
| `STAGEFORGE_GODOT_KEYS=1` | inject `2,3,4,1,Space,Space` through `Input.parse_input_event()` at startup, so `_input()` is exercised end-to-end and every transition lands in the log |

```powershell
$env:STAGEFORGE_GODOT_SHOT = 'G:\stageforge\out\godot_shot.png'
$env:STAGEFORGE_GODOT_KEYS = '1'
& 'D:\AstraForge\runtime\godot\Godot_v4.5.1-stable_win64_console.exe' --path godot
```

## Scene

```
Main (main.gd)
└─ ViewportHost      SubViewportContainer, stretch=false — the SubViewport
   │                 stays pinned at 1920x1080 (broadcast contract), the
   │                 window is only a debug view
   └─ SubViewport    1920x1080, transparent_bg=false, UPDATE_ALWAYS
      ├─ NDIOutput   added by main.gd at runtime when the addon loads
      └─ Scene3D
         ├─ Camera3D        aims at CAMERA_TARGET in main.gd
         ├─ VirtualStudio   studio_builder.gd — environment, floor, walls,
         │                  3 lights, PresenterPlate (bezel + stand)
         └─ ARGroup         ar_loader.gd — topic holograms from ar_config.json
      └─ Receiver           receiver.gd — Python RGBA stream → PresenterPlate
└─ DebugUI (CanvasLayer)    debug_ui.gd — topic, fps, key map; window only,
                            deliberately outside the SubViewport so it never
                            reaches the broadcast output
```

`main.gd` validates the contract on every start (`assert`) and measures
average fps over 120 frames (`fps >= 25` required by the plan).

`transparent_bg=false` since the studio demo: the studio fills the frame,
so an opaque viewport is the honest contract. The alpha/Key-Fill check
returns when the AR-over-live-feed mode comes back — see the limitation
note below.

## Check the NDI source in OBS

1. Install the NDI Runtime (link above) — without it the project logs
   `godot ndi: SKIP` and no source appears.
2. Start the project (editor F5 or CLI).
3. OBS Studio → *Tools → NDI Source* (obs-ndi plugin) →
   **Source name: `StageForge_Godot`**.
   Alternative: NDI Studio Monitor (Part of NDI Tools) — same name.
4. **Alpha check:** not applicable while the studio demo renders an
   opaque frame (`transparent_bg=false`). Re-enable it — a solid-colour
   source underneath must show through the empty areas — once the
   AR-over-live-feed mode restores `transparent_bg=true`.

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
- **The godot-ndi addon crashes Godot on exit when the NDI Runtime is
  absent** (signal 11 in `load_runtime`'s teardown, after `godot ndi:
  SKIP` has already printed). Bisected: with `godot-ndi.gdextension`
  renamed away the same run exits 0, so the fault is entirely in the
  vendored addon, not in this project's scripts. Everything — startup,
  all frames, the fps assert, `Esc`, the screenshot — completes before
  the crash, so the demo itself is unaffected; only the exit code is
  non-zero. Installing the Runtime fixes it; the addon is vendored and
  deliberately left unmodified.
- No NDI/Spout verification was possible without the Runtime — the OBS
  steps above are the manual acceptance test for the machine that has it.
  Alternative if NDI is unwanted: [spout-gd](https://github.com/you-win/spout-gd)
  (Windows shared-texture output, same pattern: add the node inside the
  SubViewport).
- fps measured with the full studio scene (walls, lights, plate, AR
  quad, HUD): **30.0–30.3 avg** (capped at `run/max_fps=30`, broadcast
  cadence). Scenes with heavier AR geometry must be re-measured in the
  pilot — optimisation is explicitly out of scope (plan rule: 30-minute
  cap, document, don't tune).

## Layout

| Path | Purpose |
|---|---|
| `project.godot` | gl_compatibility renderer, 1920x1080, `max_fps=30` |
| `main.tscn` / `main.gd` | scene contract + camera + NDI wiring + keys + smoke asserts |
| `studio_builder.gd` | environment, floor/walls, lights, `PresenterPlate` |
| `ar_loader.gd` / `ar_config.json` | topic holograms, blend + float + billboard |
| `debug_ui.gd` | window-only HUD (topic, fps, key map) |
| `receiver.gd` | reads the Python RGBA stream (`GodotOutputSink`, seqlock) |
| `assets/` | `.glb` exports from `blender/`; `assets/ar/` holds the copied AR PNGs (**gitignored**) |
| `addons/godot-ndi/` | vendored NDI output addon (MPL-2.0) |
| `tests/` | smoke scene for Phase 5 |

## Licenses

- Godot Engine: MIT.
- `addons/godot-ndi/`: MPL-2.0 (file-level copyleft; kept unmodified
  with its `LICENSE` and `NOTICE.md` — NDI is a registered trademark of
  Vizrt). The NDI Runtime itself is a separate proprietary download.
- StageForge code in this folder: Apache-2.0 with the rest of the repo.
