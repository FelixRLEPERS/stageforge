#!/usr/bin/env python3
"""StageForge image connector.

An MCP server that gives an AI agent a `generate_image` tool backed by the local
Strata image API (Qwen-Image-2.1-Turbo, `POST /v1/images/generations`).  It runs
on the Python standard library only, speaks MCP (JSON-RPC 2.0, one message per
line) over stdin/stdout, and writes PNGs plus a JSON sidecar inside the
repository.

    python G:\\stageforge\\tools\\image_mcp.py

The Strata server behind it is started once, image-only (no text model):

    D:\\STRATA\\.venv\\Scripts\\python.exe D:\\STRATA\\serve\\server.py \\
        --engine strata --config D:\\STRATA\\strata-iq3_s.json --lazy --port 8081

Environment: STAGEFORGE_IMAGE_URL overrides the API endpoint
(default http://127.0.0.1:8081/v1/images/generations).
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROTOCOL = "2025-06-18"
PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
VERSION = "0.1.0"
REPO = Path(__file__).resolve().parent.parent
DEFAULT_URL = os.environ.get("STAGEFORGE_IMAGE_URL", "http://127.0.0.1:8081/v1/images/generations")
MIN_SIDE, MAX_SIDE, SIDE_STEP = 256, 2048, 32
MAX_PROMPT = 16000
SAFE_STEM = re.compile(r"[^A-Za-z0-9._-]+")

INSTRUCTIONS = (
    "Local image generation for StageForge. Call generate_image with an English "
    "prompt (photoreal broadcast / virtual-production look, no text, no logos in "
    "the image); PNGs land in assets/generated/ with a JSON sidecar recording "
    "prompt, seed and timing. 1024x1024 is the default, 1792x1024 suits a README "
    "hero, n is 1-4 images, seed makes a result repeatable. Call "
    "image_server_status first if a generation fails."
)


class ToolError(Exception):
    pass


def _json(url: str, payload=None, timeout: float = 600.0):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _server_error(exc: Exception, what: str) -> ToolError:
    if isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, ConnectionRefusedError):
        return ToolError(
            f"{what}: the image server is not running on {DEFAULT_URL.rsplit('/v1', 1)[0]}. "
            "Start it once with: D:\\STRATA\\.venv\\Scripts\\python.exe "
            "D:\\STRATA\\serve\\server.py --engine strata "
            "--config D:\\STRATA\\strata-iq3_s.json --lazy --port 8081"
        )
    if isinstance(exc, urllib.error.HTTPError):
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")[:500]
        except Exception:  # noqa: BLE001
            pass
        return ToolError(f"{what}: HTTP {exc.code} {body}")
    return ToolError(f"{what}: {exc}")


# --------------------------------------------------------------------------- arguments
def _size(value) -> str:
    m = re.fullmatch(r"(\d+)x(\d+)", str(value or "1024x1024").strip().lower())
    if not m:
        raise ToolError('size: a string WIDTHxHEIGHT, e.g. "1024x1024"')
    w, h = int(m.group(1)), int(m.group(2))
    if not (MIN_SIDE <= w <= MAX_SIDE and MIN_SIDE <= h <= MAX_SIDE):
        raise ToolError(f"size: each side from {MIN_SIDE} to {MAX_SIDE}, got {w}x{h}")
    if w % SIDE_STEP or h % SIDE_STEP:
        raise ToolError(f"size: each side must be a multiple of {SIDE_STEP}, got {w}x{h}")
    return f"{w}x{h}"


def _count(value, low: int, high: int, what: str) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ToolError(f"{what}: a whole number from {low} to {high}") from None
    if not low <= n <= high:
        raise ToolError(f"{what}: a whole number from {low} to {high}, got {n}")
    return n


def _out_dir(value) -> Path:
    base = REPO
    raw = Path(str(value or "assets/generated"))
    target = Path(os.path.normpath(str(raw if raw.is_absolute() else base / raw)))
    try:
        target.relative_to(base)
    except ValueError:
        raise ToolError("out_dir: must stay inside the StageForge repository") from None
    return target


def _stem(value) -> str:
    s = SAFE_STEM.sub("-", str(value or "stageforge")).strip("-._")
    return (s or "stageforge")[:80]


# --------------------------------------------------------------------------- tools
def generate_image(args: dict) -> dict:
    prompt = str(args.get("prompt") or "").strip()
    if not prompt:
        raise ToolError("prompt: required")
    if len(prompt) > MAX_PROMPT:
        raise ToolError(f"prompt: at most {MAX_PROMPT} characters")
    size = _size(args.get("size"))
    n = _count(args.get("n", 1), 1, 4, "n")
    steps = _count(args.get("steps", 8), 1, 100, "steps")
    seed = (
        None if args.get("seed") in (None, "") else _count(args.get("seed"), 0, 2**32 - 1, "seed")
    )
    out_dir = _out_dir(args.get("out_dir"))
    stem = _stem(args.get("filename"))

    payload = {
        "prompt": prompt,
        "size": size,
        "n": n,
        "steps": steps,
        "response_format": "b64_json",
    }
    if seed is not None:
        payload["seed"] = seed

    started = time.time()
    try:
        resp = _json(DEFAULT_URL, payload)
    except Exception as exc:  # noqa: BLE001
        raise _server_error(exc, "generate_image") from None

    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for i, item in enumerate(resp.get("data") or []):
        b64 = item.get("b64_json")
        if not b64:
            continue
        path = out_dir / f"{stem}-{i}.png"
        path.write_bytes(base64.b64decode(b64))
        files.append({"path": str(path.relative_to(REPO)), "seed": item.get("seed")})
    if not files:
        raise ToolError("generate_image: the server returned no image data")

    meta = {
        "prompt": prompt,
        "size": size,
        "n": len(files),
        "steps": steps,
        "seed": seed,
        "files": [f["path"] for f in files],
        "seconds": round(time.time() - started, 1),
        "server": resp.get("strata"),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (out_dir / f"{stem}.json").write_text(
        json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    return {
        "ok": True,
        "size": size,
        "n": len(files),
        "seconds": meta["seconds"],
        "files": files,
        "server": meta["server"],
        "note": "English prompts read best; no negative prompt or img2img exists.",
    }


def image_server_status(_args: dict) -> dict:
    url = DEFAULT_URL.rsplit("/v1/images/generations", 1)[0] + "/v1/status"
    try:
        resp = _json(url, timeout=10)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": str(exc),
            "hint": "start: D:\\STRATA\\.venv\\Scripts\\python.exe "
            "D:\\STRATA\\serve\\server.py --engine strata "
            "--config D:\\STRATA\\strata-iq3_s.json --lazy --port 8081",
        }
    return {
        "ok": True,
        "endpoint": url,
        "model": resp.get("model"),
        "text_model_loaded": resp.get("loaded"),
        "image_generation": resp.get("image_generation"),
        "context": resp.get("context"),
    }


TOOL_DEFS = [
    {
        "name": "generate_image",
        "description": (
            "Generate PNG images with the local Qwen-Image-2.1-Turbo model and "
            "save them inside the StageForge repository. Returns the saved paths, "
            "per-image seeds and the time taken. English prompts are most "
            "reliable; describe what you want (there is no negative prompt)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "What to draw, in English, up to 16000 characters.",
                },
                "size": {
                    "type": "string",
                    "default": "1024x1024",
                    "description": "WIDTHxHEIGHT, each side a multiple of 32 from 256 to 2048. "
                    "1792x1024 suits a README hero.",
                },
                "n": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 4,
                    "default": 1,
                    "description": "How many images; image i uses seed + i.",
                },
                "seed": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "Repeats a result. Omit for a random seed.",
                },
                "steps": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 8,
                    "description": "8 is the model's Turbo schedule; other counts change the schedule.",
                },
                "out_dir": {
                    "type": "string",
                    "default": "assets/generated",
                    "description": "Folder inside the repository.",
                },
                "filename": {
                    "type": "string",
                    "default": "stageforge",
                    "description": "Base name for the PNGs, e.g. hero-virtual-studio.",
                },
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "image_server_status",
        "description": (
            "Check that the local image server is up and whether images "
            "are enabled. Call this first if generate_image fails."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# --------------------------------------------------------------------------- MCP plumbing
class McpServer:
    def __init__(self, out):
        self.out = out
        self.lock = threading.Lock()
        self.protocol = PROTOCOL

    def send(self, msg: dict) -> None:
        data = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
        with self.lock:
            self.out.write(data)
            self.out.flush()

    @staticmethod
    def result(rid, result):
        return {"jsonrpc": "2.0", "id": rid, "result": result}

    @staticmethod
    def error(rid, code, message):
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}

    def handle(self, msg):
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
            return self.error(
                msg.get("id") if isinstance(msg, dict) else None, -32600, "invalid request"
            )
        if "method" not in msg:
            return None  # a response to us: ignored
        method, rid, params = msg["method"], msg.get("id"), msg.get("params") or {}
        if "id" not in msg:
            return None  # notification (initialized ... )
        if not isinstance(params, dict):
            return self.error(rid, -32602, "params must be an object")
        if method == "initialize":
            asked = str(params.get("protocolVersion") or PROTOCOL)
            self.protocol = asked if asked in PROTOCOLS else PROTOCOL
            return self.result(
                rid,
                {
                    "protocolVersion": self.protocol,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {
                        "name": "stageforge-image",
                        "title": "StageForge image",
                        "version": VERSION,
                    },
                    "instructions": INSTRUCTIONS,
                },
            )
        if method == "ping":
            return self.result(rid, {})
        if method == "tools/list":
            return self.result(rid, {"tools": TOOL_DEFS})
        if method == "tools/call":
            name = params.get("name")
            fn = {"generate_image": generate_image, "image_server_status": image_server_status}.get(
                name
            )
            if fn is None:
                return self.error(rid, -32602, f"unknown tool: {name}")
            try:
                res = fn(params.get("arguments") or {})
                return self.result(rid, self.content(res, error=False))
            except ToolError as exc:
                return self.result(rid, self.content({"ok": False, "error": str(exc)}, error=True))
            except Exception as exc:  # noqa: BLE001 - a bug must not end the server
                return self.result(
                    rid,
                    self.content(
                        {
                            "ok": False,
                            "error": f"internal error in {name}: {exc}",
                            "trace": traceback.format_exc(),
                        },
                        error=True,
                    ),
                )
        if method in ("resources/list", "prompts/list"):
            return self.result(rid, {method.split("/")[0]: []})
        return self.error(rid, -32601, f"method not found: {method}")

    @staticmethod
    def content(res: dict, error: bool) -> dict:
        out = {
            "content": [{"type": "text", "text": json.dumps(res, indent=1, ensure_ascii=False)}],
            "isError": error,
        }
        return out

    def serve(self) -> None:
        threads = []
        for raw in sys.stdin.buffer:
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                self.send(self.error(None, -32700, "parse error"))
                continue
            if isinstance(msg, list) or (
                isinstance(msg, dict) and msg.get("method") == "tools/call"
            ):
                t = threading.Thread(target=self._run, args=(msg,), daemon=True)
                t.start()
                threads.append(t)
                threads = [x for x in threads if x.is_alive()]
            else:
                self._run(msg)
        for t in threads:
            t.join(timeout=5)

    def _run(self, msg) -> None:
        if isinstance(msg, list):
            out = [r for r in (self.handle(m) for m in msg) if r is not None]
            if out:
                self.send(out if isinstance(out, list) else out)
            return
        r = self.handle(msg)
        if r is not None:
            self.send(r)


def main(argv=None) -> int:
    if "--self-test" in (argv or sys.argv):
        print(json.dumps({"ok": True, "repo": str(REPO), "url": DEFAULT_URL}))
        return 0
    McpServer(sys.stdout.buffer).serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
