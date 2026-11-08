# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **MVP implementation in `src/stageforge/`**, replacing the stubs while
  keeping every existing interface and test intact:
  - `capture`: `UsbCameraSource` (UVC + cached pillarbox autocrop),
    `SyntheticCameraSource` (hardware-free dry runs), `MultiCameraSource`
    (frame-id alignment + desync counter), `crop.py` bar detection.
  - `reconstruction`: `MonocularDepthProvider` (Depth Anything V2 Small
    via `transformers`, relative depth in `[0, 1]`),
    `SyntheticDepthProvider` radial ramp.
  - `segmentation`: `DepthAlphaSegmenter` (percentile stretch + optional
    morphology), `metric.py` for the future depth-sensor pilot.
  - `compositing`: `Simple2DCompositor` + `assets.py` loader/placeholders
    (no external render bridge required).
  - `output`: `FileOutputSink`, `NDIOutputSink` (degrades to a counted
    no-op when `ndi-python` is absent), `NullOutputSink`.
  - `storylink`: `YamlStoryLink` resolving `configs/storylink.yaml`.
  - `orchestrator`: `builder.py` layer factory, `StageForgePipeline`
    with per-frame latency and run summary, `--frames` / `--dry-run`
    CLI flags. The scaffold `Pipeline` class is kept untouched so
    `tests/test_pipeline.py` still passes.
- Optional extras in `pyproject.toml`: `ml` (torch, torchvision,
  transformers, timm) and `ndi` (ndi-python).
- **Godot render layer** (ADR-0004, replaces the UE5 concept):
  `godot/` scaffold — 1920x1080 transparent SubViewport, vendored
  `godot-ndi` addon (NDI source `StageForge_Godot`), `receiver.gd`
  consuming the stream, headless smoke asserts (fps ≥ 25);
  `blender/` — `export_for_godot.py` glTF 2.0 export + MCP bridge;
  `output.GodotOutputSink` (`output.mode: "godot"`, file-backed RGBA
  buffer with seqlock); OpenCode MCP servers `godot` and `blender`.
  Headless smoke measured 30.6 fps on an *empty* scene (1920x1080,
  transparent_bg) — real scenes with AR models and lighting need a
  separate measurement at pilot stage.
- **ColorChecker calibration package** (ADR-0005): `src/stageforge/calibration/`
  — reference values for the 24-patch chart + synthetic generator,
  Canny/quad patch detection with a manual `--rect` fallback,
  least-squares **3x3 CCM** (numpy only, no scipy), `.ccm`/`.cube`
  writers, frame application (CCM / trilinear cube / EV offset) and a
  config-gated calibrator compiled by `builder.py` and applied in the
  run loop before depth estimation. `scripts/calibrate.py` CLI
  (`--capture` / `--build` / `--test-frame` / `--grey`), two empty
  per-lens profile templates (50 mm, 40 mm) and `calibration/README.md`
  one-time procedure. `calibration.enabled: false` by default (identity);
  captures, `*.ccm` and `*.cube` are gitignored.
- ADR 0002 (`monocular-depth-contract`) and ADR 0003
  (`pull-based-capture-contract`), both indexed in `docs/adr/README.md`
  and `mkdocs.yml`.
- Tests: `test_capture_autocrop`, `test_reconstruction_monocular`
  (skips without the `[ml]` extra), `test_segmentation_depth_alpha`,
  `test_pipeline_e2e_synthetic`.
- `stageforge.core.log` — prefers `loguru`, falls back to stdlib
  `logging`, so the package imports in a bare environment.
- `RelativeDepthFrame` in `core/types.py` and `SyntheticDepthProvider`
  in `reconstruction/synthetic.py`.
- **ONNX depth backend (scenario D of the incremental perf pass)**:
  `MonocularDepthProvider(backend=...)` accepts `"transformers"`
  (default, previous behaviour) or `"onnx"`, wired through `builder.py`
  as `reconstruction.monocular.backend` (optional `onnx_path` too);
  `scripts/export_depth_onnx.py` exports the checkpoint (opset 17,
  dynamic batch/H/W axes, `model.eval()` **before** export, values
  normalised through `processor()` exactly as inference does);
  `scripts/measure_depth_backends.py` benchmarks every backend the
  current machine can run (backend runners split into the sibling
  `scripts/_depth_backends.py` so both files stay < 200 lines). New
  extras `onnx` / `onnx-gpu` and a mypy override for `onnxruntime`
  (no stubs).
- `reconstruction/onnx_support.py` — `open_onnx_session()`, the single
  place a session is created (provider and benchmark share it), plus
  `enable_bundled_cuda_dlls` (why that exists: see Fixed).
- `reconstruction/depth_norm.py` — `normalise_depth`, moved out of
  `monocular.py`; still re-exported from `monocular` and the package
  root, so no import site changed.
- `configs/dev_single.yaml` — single-camera variant of `dev.yaml` for
  benches where only the index-1 UVC device delivers frames (the
  two-camera wrapper ends the run on the silent one).
- Tests: `test_calibration_reference`, `test_calibration_apply`,
  `test_calibration_build_lut`, `test_calibration_detect`,
  `test_calibration_profiles` (all on synthetic chart data — no
  physical ColorChecker needed in CI).
- Tests: `test_onnx_output_shape`, `test_onnx_backend_matches_transformers`
  (≤ 5 % of range), `test_onnx_missing_model_points_at_export_script`,
  `test_unknown_backend_is_rejected`.
- **Level A — 3D studio import pipeline** (ADR-0009, supersedes ADR-0006
  for occlusion): `scripts/import_studio_reconstruction.py` converts an
  offline Blender reconstruction (mesh + `cameras.json`) into
  `godot/assets/studio/` (`studio_mesh.glb` + per-camera
  position/quaternion/FOV), with `--scale-ref` for scene scale and
  Blender→Godot Z-up→Y-up conversion; `godot/studio_3d_loader.gd` a
  `Node3D` loader that instantiates the mesh and spawns `Marker3D`/`Camera3D`
  per camera. New `reconstruction` extra (`trimesh` only — no `scipy`,
  no `pygltflib`); tests `test_import_reconstruction` (4).
- **Raw-frame recording for offline debugging**: new `debug` config
  section (`record_raw`, `raw_dir`, `raw_format`, `raw_every_n`) plus a
  `--record-raw` CLI flag — every Nth *pre-crop* frame is written to
  `out/raw_frames/cam{index}_frame{ID}.{png|jpg}` next to a merged
  `manifest.json` (per camera `name`/`fps_reported`/`fps_actual`, per
  frame `timestamp_us`/`frame_id`/`resolution`/`file`). Implemented in
  the new `capture/record.py` (`RawFrameRecorder`), wired through
  `build_capture(..., debug_cfg)` into both `UsbCameraSource` and
  `SyntheticCameraSource`; off by default, best-effort writes that never
  stop the pipeline. Tests: `test_capture_record_raw` (5).
- **Extended camera diagnostics for test day**: new `capture/diag.py`
  with `probe_modes()` (candidate-mode table: negotiated geometry +
  read latency per mode, where an unsupported mode blocking for seconds
  *is* the finding), `measure()` (streaming window with **measured**
  fps, drop counting vs the stream's own cadence, Canny-based
  live/frozen verdict, sample PNG in `out/diag/`, rig identity
  heuristic) and `identify()` (`5D II detected (pillarbox …)` /
  `5D IV detected (clean 1920×1080)` / black-frame guard).
  `scripts/diagnose_camera.py` rewritten as a thin CLI over it
  (`--seconds`, `--stress` for a 30 s window) printing a per-camera
  mode table, stream report and a closing summary. Read-only: the
  pipeline request is unchanged and the capture layer is untouched.
  Tests: `test_capture_diag` (12).

### Changed

- `CaptureSource` contract: added abstract `read()`; `frames()` remains
  the iterator form (ADR 0003).
- `DepthProvider.depth_for()` now returns `DepthMap | RelativeDepthFrame`
  (ADR 0002).
- `Segmenter.segment()` accepts `DepthMap | RelativeDepthFrame | None`
  so the alpha layer can consume monocular depth.
- `configs/dev.yaml` extended with the MVP keys (`mode`, `camera`,
  `reconstruction`, `segmentation`, `compositing`, `output.mode`,
  `storylink`, `calibration`); the original scaffold keys are retained
  below a separator for reference.
- `docs/03-capture.md`, `04-reconstruction-tracking.md`,
  `05-segmentation-alpha.md`, `07-output-delivery.md`,
  `11-roadmap.md`, `prototypes/p01-depth-mvp/README.md` updated to the
  real rig (Canon 5D IV + 5D II with Magic Lantern, two USB FHD cards,
  monocular depth); `docs/09-configuration.md` now documents the full
  MVP schema.
- `mypy` overrides added for the optional extras (`torch`,
  `transformers`, `timm`, `NDIlib`) and `loguru`, all of which may be
  absent from CI.

### Fixed

- **`pip install -e ".[ml]"` resolved `torch>=2.0` to the CPU wheel
  from PyPI and would have silently replaced the existing CUDA build**
  (`2.6.0+cu124`, `cuda_available=True`). The running install was
  aborted mid-download (nothing installed yet) and redone in the
  README's order: torch/torchvision from
  `download.pytorch.org/whl/cu124` first (`torchvision-0.21.0+cu124`
  matches torch 2.6 — the latest PyPI torchvision pins `torch==2.15`
  and would flip CUDA off), then `transformers timm`, then
  `pip install -e ".[ml]" --no-deps`. Documented in README "ML extras
  on a CUDA machine"; moving torch out of the `[ml]` extra entirely is
  deferred (it would break the bare `pip install -e ".[ml]"` path on
  CPU-only machines).
- **onnxruntime's CUDA provider registered itself but failed every
  Conv: `cuDNN is unavailable ... LoadLibrary failed for
  cudnn64_9.dll, error 2`.** On Windows those DLLs ship inside
  `torch/lib` and are not on the process DLL search path — the failure
  only stayed hidden in the first benchmark because torch had already
  been imported in the same process. `enable_bundled_cuda_dlls()` now
  prepends `torch/lib` to `PATH` before the session is created, which
  the isolated benchmark confirmed (crash → GPU inference).
- **Camera conversion used `T · M · Tᵀ`, which points every imported
  camera the wrong way** (pre-flight on a real Blender export caught it:
  an identity Blender camera looking straight down ended up looking
  horizontally in Godot). Conjugation re-expresses the node's *local*
  coordinates, but a camera's local convention (−Z forward, +Y up) is
  identical in both engines — only the world side changes, so the
  conversion is `M_godot = T · M_blender` (left-multiply only).
  Verified against Blender's own glTF exporter (`export_cameras=True`):
  output quaternions now match Blender's camera nodes to 8 decimals
  (4/4 cameras, incl. non-unit scale via SVD orthonormalization).
  Regression test: `test_camera_look_direction_converts`.
- **`godot/studio_3d_loader.gd` did not parse in Godot 4.5** (`var x :=
  … if … else null` cannot infer a type with this project's
  warnings-as-errors) and then referenced `cast_geometry_into_occlusion_buffer`,
  a property that does not exist in 4.5 (occlusion culling is done via
  `OccluderInstance3D` + an `Occluder3D` resource). AR depth-occlusion
  itself needs neither — the studio mesh renders in the same 3D scene,
  so nodes behind it fail the depth test; the `OccluderInstance3D`
  wiring stays with the follow-up ADR. Headless pre-flight
  (`godot/preflight_check.tscn`) now loads the real import and asserts
  mesh AABB, marker positions, look directions and FOV.

### Performance

Second implementation pass: the pipeline was profiled per stage with
`scripts/profile_pipeline.py` (new) and cut to the 33 ms / 1080p30
frame budget. Measured on the full 1920x1080 raster, synthetic mode:

| stage | before | after |
| --- | ---: | ---: |
| `capture.read` (2 cams) | 10.2 ms | 3.8 ms |
| `depth.predict` | 46.8 ms | 0.01 ms |
| `segment` | 37.3 ms | 11.2 ms |
| `composite` | 49.3 ms | 11.1 ms |
| **TOTAL** | **~132 ms** | **26.2 ms** |

- **Autocrop is now a real cache** (`capture/source.py`,
  `capture/synthetic.py`): a `_detected_once` flag plus a
  `_since_detect` counter replaced `frame_id % refresh == 0`, which on
  a bar-free camera (the 5D Mark IV — the main scenario) left
  `_rect is None` and re-ran `detect_bars` on **every** frame
  (45.8 ms/frame of wasted CPU).
- **`detect_bars` computes both brightness profiles once**
  (`capture/crop.py`): `detect_pillarbox`/`detect_letterbox` still
  compute their own profiles for direct callers, but the combined
  detector feeds one `_profiles()` pass into both bounds checks —
  two `np.mean` sweeps instead of four.
- **Percentiles run on a downscaled copy** (`segmentation/depth_alpha.py`):
  new `percentile_scale` (default `0.25`, wired through
  `builder.py` and configurable under `segmentation.depth_alpha`)
  samples 480x270 instead of 1920x1080 for `np.percentile`; normalise
  and round are now in-place single-pass (`cv2.convertScaleAbs`).
- **Background dimming uses saturating uint8 OpenCV ops**
  (`compositing/simple2d.py::dim_background`): the task proposed int16
  arithmetic, but measuring both showed int16 at 31 ms vs uint8 at
  6.6 ms, and `diff * alpha` overflows int16 for `shade < 0.5`.
  Kept `_dim_background_reference` (float32) for the equivalence test —
  max deviation 1/255 at 1080p.
- **Synthetic depth ramp is cached per raster**
  (`reconstruction/synthetic.py`), and `radial_depth` builds from 1-D
  coordinate vectors instead of `np.mgrid` (which allocated two int64
  index grids, 23 MB, per frame).
- **AR placeholder composites only its box**
  (`compositing/assets.py`): the full-frame `copy` + `addWeighted`
  (~9 ms) became a region-sized blend.
- New `tests/test_compositing_simple2d.py`; autocrop cache and
  single-pass profiles covered in `tests/test_capture_autocrop.py`;
  percentile downsampling covered in `tests/test_segmentation_depth_alpha.py`.
  The commit message says "int16 composite"; the shipped
  implementation is the faster uint8 path described above.
- Third pass — **real monocular-depth inference**, measured with
  `scripts/measure_depth_backends.py` (20 iters after 3 warm-up, full
  1920x1080 synthetic frame, the same pre/infer/post steps as
  `MonocularDepthProvider._infer`, each backend's GPU memory released
  before the next row):

  | backend | avg ms | min | max | p95 |
  | --- | ---: | ---: | ---: | ---: |
  | transformers fp32 (device=auto) | 52.07 | 50.36 | 54.11 | 53.33 |
  | transformers fp16 (cuda) | 34.37 | 33.44 | 36.25 | 35.35 |
  | torch.compile fp32 | n/a | n/a | n/a | n/a |
  | onnx (cuda) | **47.29** | 45.52 | 49.07 | 48.60 |

  Run-to-run spread across four executions: fp32 52–53, fp16 34–37,
  onnx 46–48 ms.

  - Scenario selection: fp32 measured **> 40 ms → scenario D (ONNX
    backend)**; `torch.compile` dies on this Windows machine
    (`InternalTorchDynamoError`), so scenario C was untestable.
  - Measured facts that were previously assumed: the processor uses
    **ImageNet** normalisation — `image_mean=(0.485, 0.456, 0.406)`,
    `image_std=(0.229, 0.224, 0.225)`, *not* `[0.5, 0.5, 0.5]` — and
    `predicted_depth.shape == (1, 518, 924)`, **no extra singleton
    axis**, so `result[0]` (the batch index) is the 2-D map.
  - ONNX export round-trips against torch at
    `max |onnx − torch| = 0.000056` (fp32, opset 17, 99.1 MB model in
    gitignored `models/`).
  - The released transformer path (fp32) goes **52.07 → 47.29 ms** on
    the ONNX backend. Best available remains transformers fp16 at
    34.4 ms — budget 33 ms is still **FAIL by ~1.4 ms**; fp16 has since
    become the shipped default (next bullet), ONNX stays opt-in.
    Proposed next steps (not implemented): fp16 ONNX export, moving the
    bicubic upsample onto the GPU path.
  - The first onnx run printed avg 119.6 / max 1367.6 ms: the
    benchmark's local `model` variable held a second reference, so the
    "free between rows" cleanup did not actually release the torch
    models. The script now keeps exactly one reference per backend —
    47.29 ms is the same-process number after that fix.
  - Real-camera run (`configs/dev_single.yaml`, 30 frames, 1920x1080
    from the index-1 device): `avg_latency_ms=1303.3`. Layer probe —
    `capture.read` **1000 ms** (this bench device delivers ~1 fps;
    the code blocks in `capture.read()` with no sleeps of its own),
    `depth_for` **66 ms** steady on real frames after warm-up, the
    ~237 ms residual is file-sink PNG encoding + debug logging (both
    outside `profile_pipeline.py`'s stage table). No `autocrop updated:`
    line is correct here — detection runs once, `None -> None` does not
    log (`capture/source.py`). Next steps proposed, not implemented:
    async capture queue to hide the device pacing, `logging.level: info`
    for runs, PNG → lossless-but-cheaper encode or file sink behind a
    `--frames` dry profile.
- **Default backend switched to fp16 (35.5 ms vs ONNX 47.3 ms).**
  `MonocularDepthProvider` gained `precision` (default `"fp16"`),
  wired through `builder.py` and `reconstruction.monocular.precision`
  in `configs/dev.yaml` / `configs/dev_single.yaml`; the transformers
  path loads weights and inputs as half. No CUDA (or an explicit
  `device: "cpu"`) raises `RuntimeError("fp16 requires CUDA; use fp32
  on CPU")` instead of failing inside `half()`; unknown precision
  values raise `ValueError` at the constructor like unknown backends.
  ONNX remains an opt-in via `backend="onnx"` — its graph precision is
  fixed at export, so `precision` applies to the transformers path
  only. Both existing CPU tests pin `precision="fp32"` explicitly.

### Measured (ML backends, 2026-11-06)

Canonical table for the pitch deck (accepted rounded numbers; per-run
min/max/p95 detail is in the table above):

| backend           | avg ms | budget 33 ms |
| ----------------- | -----: | ------------ |
| transformers fp32 |   52.5 | FAIL         |
| transformers fp16 |   35.5 | FAIL (best)  |
| onnx CUDA         |   47.3 | FAIL         |
| torch.compile     |    n/a | Windows fail |

Facts verified by measurement (not hypotheses):

- `processor.image_mean = (0.485, 0.456, 0.406)` — ImageNet, not
  `[0.5, 0.5, 0.5]`.
- `predicted_depth.shape = (1, 518, 924)` — no extra singleton axis.
- fp16 is 12 ms faster than ONNX at the same budget.

Decision: default backend = fp16 (fastest available). ONNX stays an
opt-in via `backend="onnx"` in config.

### Camera bench diagnosis (2026-11-06)

Measured with `scripts/diagnose_camera.py` (two phases per index: the
device's default negotiated mode, then the pipeline's
1920x1080/fps30/MJPG request from `capture/source.py:87-92`), plus
`ffmpeg -f dshow -list_devices/-list_options` and a PnP device query:

| idx | device present today | default mode | pipeline 1080p request |
| --- | --- | --- | --- |
| 0 | Logitech QuickCam Pro 9000 (USB 2.0, behind a Genesys hub) | 640x480@30, **live** (reads 25-62 ms, frame diff 2.9) | **unsupported** — dshow lists no 1920x1080 mode (max 1600x1200@5); read blocks ~10 s with 0 frames or raises `cv2.error: _step >= minstep` |
| 1 | NVIDIA Broadcast virtual camera (VCAMDS) | 640x480 at ~1 fps, near-black (consumer `Init Failed Err -610`, Broadcast app closed) | 1920x1080 at exactly ~1005 ms (**1 fps**), bit-identical all-black frames (`std=0`, `diff=0`) |

Facts (each measured, not assumed):

- The FHD HDMI capture dongle (`VID_345F PID_2131`) is a PnP **phantom —
  physically absent**; no Canon body is enumerated anywhere. The config
  labels "5D Mark IV" / "5D Mark II (ML)" do not correspond to present
  hardware; the earlier "camera 1: 1920x1080 @ 1 fps" was the virtual
  Broadcast camera, not a Canon.
- Camera index order was re-verified in-process via the VCAMDS driver
  log timestamps against the script's wall-clock markers — indices are
  0 = Logitech, 1 = Broadcast cam on this bench.
- Refuted hypotheses: *camera in Photo mode* (no Canon attached to
  inspect), *USB 2.0 bandwidth* (the dongle chained directly to a
  USB 3.0 root hub while present; the Logitech's own modes are USB 2.0
  by design), *YUY2 uncompressed overload* (dshow reports `bgr24` /
  `yuv420p` formats only).
- Conclusion: the ~1000 ms `capture.read` is an **external
  device-cause, not a pipeline defect** — per the no-guessing rule no
  code was changed; the camera path is re-verified when the dongle and
  Canon bodies are re-attached (pilot).
- Artifacts: `out/diag_cam_*.png` (phase-B frames),
  `out/diag_err*.log` (VCAMDS driver log), both under gitignored `out/`.

### Decisions taken while scaffolding (MVP)

- **MVP keys mirror the plan's schema instead of reusing the scaffold
  keys.** The plan specified top-level `segmentation:` and
  `compositing:`, while the scaffold already had `segmenter:` and
  `compositor:` for the abstract contracts. Both are kept: the MVP keys
  are read by `builder.py`, the scaffold keys document the layer
  contracts and are marked as such in the file and in
  `docs/09-configuration.md`. Folding them together would have silently
  renamed the specified schema.
- **`Pipeline` (scaffold) and `StageForgePipeline` (MVP) coexist.**
  Rewriting `Pipeline.run()` to do real work would have broken
  `tests/test_pipeline.py`, which the plan forbids; the plan itself
  allows adding a `StageForgePipeline` class instead.
- **`MultiCameraSource.read()` returns a single `Frame`.** The plan
  asked for `list[Frame]`, which would violate the `CaptureSource`
  contract mypy enforces; the aligned batch is `read_round()`.
- **`assets_for_topic(topic)` added next to `assets_for(cue)`.** Same
  reason: overriding the base signature with a different parameter type
  would break the `StoryLink` contract; the cue-based API stays intact.
- **Detector polarity** — `depth_rel` is normalised so 0 = near,
  1 = far (`near_is_high: true` records Depth Anything's native
  polarity and flips it), because `DepthAlphaSegmenter` inverts on that
  assumption.
- **`--dry-run` with no config** falls back to
  `mode=synthetic, output.mode=null` so the flag works on a bare clone.

- Initial repository scaffold (see `[0.1.0]`).

## [0.1.0] - 2026-11-06

### Added

- Initial repository scaffold: five-layer package layout
  (`capture`, `reconstruction`, `tracking`, `segmentation`,
  `compositing`, `storylink`, `output`, `orchestrator`), shared data
  contracts in `core/types.py`, abstract interfaces in `base.py` and
  raising stubs in `stub.py`.
- Documentation set under `docs/` with index, layer pages,
  configuration and development guides, roadmap and the ADR process
  (ADR 0001).
- GitHub infrastructure: CI (Python 3.11/3.12 matrix), docs build,
  issue templates and pull request checklist.
- Prototypes P01–P03, MVP bill of materials, Docker image and compose
  file, dev/prod configs, bootstrap scripts.

### Decisions taken while scaffolding

- `mkdocs.yml` added at the repository root because `make docs` and the
  docs workflow call `mkdocs build --strict`; without it the target
  would fail. `mkdocs-material` is not pinned as a dependency yet — it
  is expected from the environment.
- `tests/` added with three suites (`test_core_types`,
  `test_interfaces`, `test_pipeline`) because the CI workflow runs
  `pytest`; they assert only scaffold invariants so they stay green as
  real implementations land.
- `configs/storylink.yaml` added as the example rule table referenced
  by `docs/06-compositing-ar.md` and `prod.example.yaml`.
- `assets/sample-data/.gitkeep` added because `.gitignore` excludes
  the sample data directory.
- The CI line-ending check only fails on `crlf`/`mixed` index states so
  that intentionally binary files are not flagged.

[Unreleased]: https://github.com/stageforge/stageforge/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/stageforge/stageforge/releases/tag/v0.1.0
