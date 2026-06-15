#!/usr/bin/env python3
"""Validate that the root Makefile conforms to the standard interface (ADR-007).

Usage:
    python scripts/check_makefile.py [Makefile]

Exit 0 if the Makefile exposes the required standard targets with help text.
Exit 1 and print diagnostics otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED = frozenset({"help", "install", "dev", "test", "lint", "build"})
REQUIRED_MONO = frozenset({"dev-backend", "dev-frontend", "test-backend", "test-frontend"})
FORBIDDEN_ROOT = frozenset({"build-native", "test-native", "sample_model-train", "sample_video-create"})


def parse_targets(makefile: Path) -> dict[str, str | None]:
    """Return {target_name: help_text_or_None} from a Makefile."""
    targets: dict[str, str | None] = {}
    for line in makefile.read_text(encoding="utf-8").splitlines():
        # Match a target definition: `target: ... ## help text`
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_-]*):.*?(## .*)?$", line)
        if not m:
            continue
        name = m.group(1)
        help_text = m.group(2)
        targets[name] = help_text[3:].strip() if help_text else None
    return targets


def is_mono_repo(makefile: Path) -> bool:
    """Heuristic: a mono-repo has both backend and frontend app directories."""
    root = makefile.parent
    layouts = [
        (root / "apps" / "backend", root / "apps" / "frontend"),
        (root / "backend", root / "frontend"),
    ]
    return any(b.exists() and f.exists() for b, f in layouts)


def main() -> int:
    makefile = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("Makefile")
    if not makefile.exists():
        print(f"ERROR: {makefile} not found")
        return 1

    targets = parse_targets(makefile)

    # Per-app Makefiles are not held to the root standard.
    if not is_mono_repo(makefile):
        print(f"OK: {makefile} is a per-app Makefile; skipped strict checks.")
        return 0

    required = set(REQUIRED) | REQUIRED_MONO
    missing = required - set(targets)
    if missing:
        print(f"ERROR: {makefile} missing required targets: {sorted(missing)}")
        return 1

    missing_help = [t for t in required if targets[t] is None]
    if missing_help:
        print(f"ERROR: required targets missing `## help` text: {sorted(missing_help)}")
        return 1

    forbidden = FORBIDDEN_ROOT & set(targets)
    if forbidden:
        print(f"ERROR: root Makefile must not contain specialist targets: {sorted(forbidden)}")
        print("Move them to apps/<app>/Makefile per ADR-007.")
        return 1

    print(f"OK: {makefile} exposes {len(targets)} targets; required targets present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
