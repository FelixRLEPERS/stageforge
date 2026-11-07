# StageForge Godot render layer

Real-time AR rendering for StageForge (ADR-0004: Godot + Blender instead
of Unreal Engine 5). This folder is **self-contained** — the Python
pipeline (`src/stageforge/`) does not depend on it; the two sides talk
through the RGBA stream described in `docs/06-compositing-ar.md`.

## Requirements

| | |
|---|---|
| Godot | **4.4+** (addon `compatibility_minimum=4.4`); tested on portable 4.5.1 at `D:\AstraForge\runtime\godot\Godot_v4.5.1-stable_win64.exe` |
| NDI Runtime | **installed on this machine** at `C:\Program Files\NDI\NDI 6 Runtime\v6` (v6.3.2, downloaded from <https://ndi.video/tools/>). **Not used by the local demo** — the GDExtension is renamed to `.disabled` (see Known limitations); the shared-memory stream (`GodotOutputSink` → `receiver.gd`) carries the plate |
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
StageForge Godot ready
godot smoke: viewport contract PASS (1920x1080, studio opaque)
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
      └─ Scene3D
         ├─ Camera3D        aims at CAMERA_TARGET in main.gd
         ├─ VirtualStudio   studio_builder.gd — environment, floor, walls,
         │                  3 lights, PresenterPlate (bezel + stand)
         └─ ARGroup         ar_loader.gd — topic holograms from ar_config.json
      └─ Receiver           receiver.gd — Python RGBA stream → PresenterPlate
└─ DebugUI (CanvasLayer)    debug_ui.gd — topic, fps, key map; window only,
                            deliberately outside the SubViewport so it never
                            reaches the broadcast output
└─ NDISetup (Node)          ndi_setup.gd — optional NDI output, DISABLED for the
                            local demo (GDExtension renamed to `.disabled`, call
                            in main.gd `_ready()` commented out; see NDI section)
```

`main.gd` validates the contract on every start (`assert`) and measures
average fps over 120 frames (`fps >= 25` required by the plan).

`transparent_bg=false` since the studio demo: the studio fills the frame,
so an opaque viewport is the honest contract. The alpha/Key-Fill check
returns when the AR-over-live-feed mode comes back — see the limitation
note below.

## NDI output — disabled for the local demo

**The local demo uses Shared Memory (mmap) only**, through `receiver.gd`
(`GodotOutputSink` → plate). NDI is deferred to the pilot: the vendored
`godot-ndi` GDExtension is **renamed to `.disabled`** because its teardown
code crashes Godot (signal 11) *even with the NDI Runtime installed* —
a bug inside the addon, off-limits to edit (see Known limitations).

To bring NDI back on the pilot:

1. Rename `addons/godot-ndi/godot-ndi.gdextension.disabled` →
   `godot-ndi.gdextension` (re-enables the extension scan).
2. Add `C:\Program Files\NDI\NDI 6 Runtime\v6` to `PATH` (the Runtime
   installer does not do this on its own).
3. Uncomment `$NDISetup.attach($ViewportHost/SubViewport)` in `main.gd`
   `_ready()`.
4. Start the project, then OBS Studio → *Tools → NDI Source* (obs-ndi
   plugin) → **Source name: `StageForge_Godot`** (alternative: NDI Studio
   Monitor, part of NDI Tools).
5. **Alpha check:** not applicable while the studio demo renders an
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

- **The `godot-ndi` GDExtension is renamed to `.disabled`.** Its teardown
  code crashes Godot (signal 11) at shutdown — **even with the NDI
  Runtime installed** (tested 2026-11-07: Runtime v6.3.2 loaded the DLL
  without error, `NDIOutput` created OK, but the exit still segfaults).
  Bisected to the extension itself: with the file renamed away every run
  (import, headless, windowed) exits 0. The addon source is off-limits to
  edit, so the durable fix is the rename — reversible, see the NDI section
  above for re-enabling. Also observed with the extension active:
  `Couldn't get viewport texture's RID on the RenderingDevice` floods
  every frame (the addon uses RenderingDevice APIs, the project renders
  `gl_compatibility`).
- **NDI Runtime is installed but not on `PATH`.** The installer puts the
  DLLs at `C:\Program Files\NDI\NDI 6 Runtime\v6` without adding the
  directory to `PATH`; godot-ndi loads by bare filename, so the directory
  must be on `PATH` manually (needs admin for machine-level `setx`).
- No NDI/Spout verification was possible (the extension is disabled) —
  the NDI steps above are the manual acceptance test for the pilot.
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
| `main.tscn` / `main.gd` | scene contract + camera + keys + smoke asserts |
| `ndi_setup.gd` | optional NDI output — **disabled** for the local demo (extension renamed `.disabled`; see NDI section) |
| `studio_builder.gd` | environment, floor/walls, lights, `PresenterPlate` |
| `ar_loader.gd` / `ar_config.json` | topic holograms, blend + float + billboard |
| `debug_ui.gd` | window-only HUD (topic, fps, key map) |
| `receiver.gd` | reads the Python RGBA stream (`GodotOutputSink`, seqlock) |
| `assets/` | `.glb` exports from `blender/`; `assets/ar/` holds the copied AR PNGs (**gitignored**) |
| `addons/godot-ndi/` | vendored NDI output addon (MPL-2.0); `.gdextension` renamed to `.disabled` — see NDI section |
| `tests/` | smoke scene for Phase 5 |

## Licenses

- Godot Engine: MIT.
- `addons/godot-ndi/`: MPL-2.0 (file-level copyleft; kept unmodified
  with its `LICENSE` and `NOTICE.md` — NDI is a registered trademark of
  Vizrt). The NDI Runtime itself is a separate proprietary download.
- StageForge code in this folder: Apache-2.0 with the rest of the repo.
