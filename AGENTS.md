# StageForge — agent notes

StageForge is an automatic virtual studio with real-time AR compositing:
capture → reconstruction/tracking → segmentation/alpha → compositing/AR →
output (SDI Key/Fill, NDI). Pre-MVP scaffold; every milestone must show
something observable on a real monitor.

## Local image generation (connector)

`tools/image_mcp.py` is an MCP server that gives any agent these tools:

- `generate_image(prompt, size?, n?, seed?, steps?, out_dir?, filename?)`
- `image_server_status()`

It calls the local Strata image API (Qwen-Image-2.1-Turbo) at
`http://127.0.0.1:8081/v1/images/generations` and writes PNGs plus a JSON
sidecar (prompt, seed, seconds) into `assets/generated/`.

Start the image server once — image-only, no text model, about 0.7 GB VRAM:

```powershell
D:\STRATA\.venv\Scripts\python.exe D:\STRATA\serve\server.py --engine strata --config D:\STRATA\strata-iq3_s.json --lazy --port 8081
```

How to use it well:

- English prompts read best; there is **no negative prompt and no img2img** —
  describe what you want, not what to avoid.
- `1024x1024` is the default; `1792x1024` suits a README hero. Each side is a
  multiple of 32, from 256 to 2048.
- `n` is 1–4 images (image *i* uses `seed + i`); a fixed seed repeats a result.
- One image job at a time, about 10–20 s each on an RTX 3080 Ti.
- Keep text, logos and watermarks out of the image; Cyrillic rendering is
  unreliable.
- Images come from a model under the **Qwen Research License** — check it
  before shipping anything commercial.

### Media style guide

Photoreal broadcast / virtual-production look: dark studio, soft key light,
cool teal shadows with warm practicals, cinematic depth of field. Subjects
that fit this project: a multi-camera stage, an LED wall showing a virtual
set, a presenter, broadcast cameras on tripods, AR overlays (charts,
lower-thirds, holograms), depth-map and alpha visualisations.

Generated files are not committed by default (`assets/generated/` is
untracked); add the ones you want to keep.
