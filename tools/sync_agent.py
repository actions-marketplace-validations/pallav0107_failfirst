#!/usr/bin/env python3
"""Copy the canonical agent files into each package (python/ and js/).

Canonical: spec/tools.json, schemas/*.json, llms.txt, AGENTS.md. Packages ship their own copy
under <pkg>/agent/ so installs are self-contained. `--check` verifies the copies are current
(used by the tests); without it the copies are rewritten.
"""
import glob
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = [os.path.join(ROOT, "python", "src", "failfirst", "agent"), os.path.join(ROOT, "js", "agent")]


def sources() -> dict:
    out = {"tools.json": os.path.join(ROOT, "spec", "tools.json"),
           "llms.txt": os.path.join(ROOT, "llms.txt"), "AGENTS.md": os.path.join(ROOT, "AGENTS.md")}
    for f in sorted(glob.glob(os.path.join(ROOT, "schemas", "*.json"))):
        out["schemas/" + os.path.basename(f)] = f
    return out


def main() -> int:
    check = "--check" in sys.argv
    stale = []
    for target in TARGETS:
        for rel, src in sources().items():
            dst = os.path.join(target, rel)
            same = os.path.exists(dst) and open(src, "rb").read() == open(dst, "rb").read()
            if not same:
                stale.append(dst)
                if not check:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copyfile(src, dst)
    for path in stale:
        print(("STALE " if check else "wrote ") + os.path.relpath(path, ROOT))
    return 1 if (check and stale) else 0


if __name__ == "__main__":
    sys.exit(main())
