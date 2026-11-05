#!/usr/bin/env python3
"""Applies the Nebula layer onto a Bubble Night checkout.

This repository is an *overlay*: the 600-level campaign, the solver, the
certificates and the Compose UI are all upstream, and re-uploading 2,600 files
would only make them drift. So the layer ships as:

  overlay/<path>     files that are simply copied in (new files, whole-file rewrites)
  overlay/edits.py   exact old->new text pairs for the handful of upstream files
                     that only need a few lines changed

Every edit anchor is checked to occur exactly once. If upstream moves, this
script fails loudly instead of silently producing a half-wired build.

Usage:
    git clone https://github.com/SyscallBrain/bubble-night target
    python3 apply_overlay.py target
    cd target && python3 tools/gen_audio.py && python3 tools/gen_sprites.py
    python3 tools/verify_build.py
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OVERLAY = HERE / "overlay"


def load_edits():
    spec = importlib.util.spec_from_file_location("nebula_edits", OVERLAY / "edits.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="path to a Bubble Night checkout")
    ap.add_argument("--check", action="store_true", help="verify the anchors without writing anything")
    args = ap.parse_args()

    target = Path(args.target).resolve()
    if not (target / "settings.gradle.kts").is_file():
        print(f"error: {target} does not look like a Bubble Night checkout")
        return 2

    plan = load_edits()

    # 1. Anchor check first, so a partial apply can never happen.
    problems = []
    for edit in plan.EDITS:
        path = target / edit["path"]
        if not path.is_file():
            problems.append(f"missing file: {edit['path']}")
            continue
        text = path.read_text(encoding="utf-8")
        count = text.count(edit["old"])
        if count != 1:
            problems.append(f"{edit['path']}: anchor occurs {count} times, expected 1 -> {edit['old'][:60]!r}")
    if problems:
        print("anchor check failed; nothing was written:")
        for p in problems:
            print("  \u2717", p)
        return 1
    if args.check:
        print(f"anchors ok: {len(plan.EDITS)} edits across "
              f"{len({e['path'] for e in plan.EDITS})} files, {len(plan.NEW_FILES)} files to copy")
        return 0

    # 2. Copy new files.
    copied = 0
    for rel in plan.NEW_FILES:
        src = OVERLAY / rel
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1

    # 3. Apply edits.
    applied = 0
    for edit in plan.EDITS:
        path = target / edit["path"]
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace(edit["old"], edit["new"], 1), encoding="utf-8")
        applied += 1

    print(f"applied {applied} edits, copied {copied} files into {target}")
    print("next: python3 tools/gen_audio.py && python3 tools/gen_sprites.py && python3 tools/verify_build.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
