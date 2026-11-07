# MVP Bill of Materials

Reference build for a single-camera StageForge MVP. Prices are omitted
on purpose — negotiate with a broadcast reseller. Substitutions in the
"Alternative" column keep the design intact.

## Compute

| # | Item | Qty | Minimum spec | Alternative |
|---|------|-----|--------------|-------------|
| 1 | Workstation / GPU server | 1 | Intel Xeon or Ryzen 7, 64 GB RAM, PCIe 4.0 ×16 free | Dell Precision / HP Z series |
| 2 | GPU | 1 | **RTX A4000 (16 GB) or better** | RTX 4070 Ti, RTX A5000 |
| 3 | NVMe SSD (capture scratch) | 1 | 2 TB PCIe 4.0 | 2 × 1 TB RAID 0 |
| 4 | NIC | 1 | 10 GbE for NDI | On-board 1 GbE (NDI HX only) |

## Video I/O

| # | Item | Qty | Purpose | Alternative |
|---|------|-----|---------|-------------|
| 5 | Blackmagic DeckLink Duo 2 | 1 | multi-channel SDI in/out | DeckLink Mini Monitor 4K (output only) |
| 6 | SDI cable, BNC, 1.5 m | 4 | camera, loop-out, fill, key | — |
| 7 | Genlock source | 1 | blackburst / tri-level sync | DeckLink loop-out as reference |
| 8 | Ultimatte 12 HD or switcher keyer | 1 | downstream key | Switcher with linear key input |

## Vision

| # | Item | Qty | Purpose | Alternative |
|---|------|-----|---------|-------------|
| 9 | Studio camera | 1 | main programme feed | existing camera with SDI out |
| 10 | Lens with known zoom range | 1 | for Free-D zoom calibration | fixed lens (loses zoom tracking) |
| 11 | **ToF / depth sensor** | 1 | depth map for alpha | stereo camera (e.g. ZED 2i) |
| 12 | ChArUco calibration board | 1 | depth ↔ camera extrinsics | printed checkerboard |

## Tracking

| # | Item | Qty | Purpose | Alternative |
|---|------|-----|---------|-------------|
| 13 | Robotic head / pan-tilt unit with Free-D output | 1 | pose streaming | software-only SfM (higher risk) |
| 14 | Free-D receiver host (same as #1) | 1 | UDP listener on port 5600 | — |

## Network

| Item | Note |
|------|------|
| Managed switch, 1 GbE min | IGMP snooping enabled for NDI |
| PTP (IEEE 1588) grandmaster, optional | falls back to genlock-derived time |
| Separate VLAN for video | keeps NDI off the office network |

## Peripherals

- Reference monitor with SDI input (accuracy of the latency claim)
- Scope (waveform/vector) for key level verification
- UPS — a dropped frame is bad, a dropped show is worse

## Software prerequisites (not vendored here)

- Blackmagic DeckLink SDK + drivers
- NDI SDK (redistribution terms differ from Apache-2.0)
- Godot 4.5 portable (MIT) render layer + Blender 5.x asset prep (ADR-0004)

## Budget sanity check

The two items that decide whether the MVP works are **#2 (GPU)** and
**#11 (depth sensor)**. If the budget is tight, buy those first and
borrow the rest.
