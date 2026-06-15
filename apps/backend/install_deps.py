#!/usr/bin/env python3
"""Install the eai-fleet backend dependencies.

Installs this app's Python deps from pyproject.toml (editable): base by default,
base + dev with ``--dev``. The fleet-mgr backend is pure-Python (FastAPI + httpx2);
no native deps.

eai_core is vendored as the ``eai-core`` submodule and pip-installed FIRST so the
``eai_core[base]>=…`` requirement resolves locally — eai_core is published to no
pip index, so a bare ``pip install .`` fails to find it. This is the same
submodule-bootstrap contract eai-nano and eai-catalog use.

Run from the app directory: it installs ``.`` from the cwd and hard-errors if the
cwd is wrong — the same contract every EAI app installer uses.
"""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import logging
import subprocess
import sys
from pathlib import Path

APP = "fleet-mgr"
DIST = "eai-nano-fleet-mgr"
PACKAGE = "app"
EAI_CORE = "eai-core"  # vendored submodule providing eai_core (no pip index hosts it)
log = logging.getLogger("install_deps")


def _assert_cwd() -> None:
    cwd = Path.cwd()
    if not (cwd / "pyproject.toml").exists() or not (cwd / PACKAGE).is_dir():
        raise SystemExit(f"Run install_deps.py from the {APP} app directory.")


def _assert_submodule() -> None:
    if not (Path.cwd() / EAI_CORE / "pyproject.toml").exists():
        raise SystemExit(
            f"Vendored {EAI_CORE} submodule is empty — run: "
            "git submodule update --init apps/backend/eai-core"
        )


def _eai_core_cmd(*, force: bool, quiet: bool, verbose: bool) -> list[str]:
    cmd = [sys.executable, "-m", "pip", "install", "-e", EAI_CORE]
    if force:
        cmd.append("--force-reinstall")
    if quiet:
        cmd.append("-q")
    if verbose:
        cmd.append("-v")
    return cmd


def _pip_cmd(target: str, *, force: bool, quiet: bool, verbose: bool) -> list[str]:
    cmd = [sys.executable, "-m", "pip", "install", "-e", target]
    if force:
        cmd.append("--force-reinstall")
    if quiet:
        cmd.append("-q")
    if verbose:
        cmd.append("-v")
    return cmd


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=f"Install {APP} dependencies.")
    p.add_argument("--dev", action="store_true", help="Also install dev/test dependencies.")
    p.add_argument("--dry-run", action="store_true", help="Print what would be installed.")
    p.add_argument("--check", action="store_true", help="Verify deps; install nothing.")
    p.add_argument("--force", action="store_true", help="Force reinstall.")
    g = p.add_mutually_exclusive_group()
    g.add_argument("-v", "--verbose", action="store_true")
    g.add_argument("-q", "--quiet", action="store_true")
    args = p.parse_args(argv)

    level = logging.WARNING if args.quiet else logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")

    if args.check:
        try:
            log.info("✓ %s %s is installed.", DIST, metadata.version(DIST))
            return 0
        except metadata.PackageNotFoundError:
            log.error("✗ %s is not installed — run: python install_deps.py", DIST)
            return 1

    _assert_cwd()
    _assert_submodule()
    target = ".[dev]" if args.dev else "."
    core_cmd = _eai_core_cmd(force=args.force, quiet=args.quiet, verbose=args.verbose)
    cmd = _pip_cmd(target, force=args.force, quiet=args.quiet, verbose=args.verbose)

    if args.dry_run:
        log.info("=== Installation Plan (DRY RUN) ===")
        log.info("Would run: %s", " ".join(core_cmd))
        log.info("Would run: %s", " ".join(cmd))
        return 0

    log.info("Installing eai_core (vendored %s submodule)...", EAI_CORE)
    if subprocess.run(core_cmd).returncode != 0:
        log.error("✗ pip install failed for eai_core (%s)", EAI_CORE)
        return 1

    log.info("Installing %s...", APP)
    if subprocess.run(cmd).returncode != 0:
        log.error("✗ pip install failed for %s", APP)
        return 1

    log.info("✓ %s dependencies installed%s.", APP, " (with dev)" if args.dev else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
