"""Write PREREG.sha256: the sha256 of every file in this folder (sha256sum format, so
`sha256sum -c PREREG.sha256` checks it). Run once, by the owner, at the freeze commit.

  python freeze.py            # writes PREREG.sha256 next to this file
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


def write_manifest(base: Path) -> Path:
    base = Path(base)
    names = C.frozen_listing(base)
    missing = [n for n in C.FREEZE_REQUIRED if n not in names]
    if missing:
        raise SystemExit(f"cannot freeze: {missing} missing")
    lines = [f"{C.sha256_file(base / n)}  {n}" for n in names]
    out = base / C.FREEZE_FILE
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return out


if __name__ == "__main__":
    path = write_manifest(Path(__file__).resolve().parent)
    print(f"wrote {path}")
