"""Print the repository tree, ignoring files git does not track.

Usage::

    python scripts/gen_tree.py            # full tree
    python scripts/gen_tree.py --max 3    # limit depth
    python scripts/gen_tree.py --markdown # fenced block for README

The output is deterministic so it can be pasted into the README and
diffed in review.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "site"}


def tracked_paths(root: Path) -> list[str]:
    """Return repo-relative paths of tracked files, falling back to a walk."""
    try:
        out = subprocess.run(
            ["git", "ls-files"],
            cwd=root,
            capture_output=True,
            check=True,
            text=True,
        ).stdout
        paths = [line for line in out.splitlines() if line.strip()]
        if paths:
            return sorted(paths)
    except (OSError, subprocess.CalledProcessError):
        pass
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def _configure_stdout() -> None:
    """Emit UTF-8 even on Windows consoles that default to cp1251."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:  # pragma: no cover - depends on runtime
        reconfigure(encoding="utf-8", errors="replace")


def render(paths: list[str], max_depth: int) -> str:
    """Render ``paths`` as an ASCII tree with ``max_depth`` levels."""
    tree: dict[str, dict] = {}
    for path in paths:
        node = tree
        for part in Path(path).parts:
            node = node.setdefault(part, {})

    lines: list[str] = ["."]

    def walk(node: dict, prefix: str, depth: int) -> None:
        if max_depth and depth >= max_depth:
            return
        entries = sorted(node.items(), key=lambda kv: (not kv[1], kv[0].lower()))
        for index, (name, child) in enumerate(entries):
            last = index == len(entries) - 1
            connector = "`-- " if last else "|-- "
            suffix = "/" if child else ""
            lines.append(f"{prefix}{connector}{name}{suffix}")
            if child:
                walk(child, prefix + ("    " if last else "|   "), depth + 1)

    walk(tree, "", 0)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and print the tree."""
    _configure_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max", type=int, default=0, help="max depth (0 = all)")
    parser.add_argument("--markdown", action="store_true", help="wrap in ```")
    parser.add_argument("--root", default=".", help="repository root")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    tree = render(tracked_paths(root), args.max)
    if args.markdown:
        print("```")
        print(tree)
        print("```")
    else:
        print(tree)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
