#!/usr/bin/env python3
"""Copy only distributable Rime configuration assets from a source snapshot."""

import os
import shutil
import sys
from pathlib import Path


ALLOWED_SUFFIXES = {
    ".yaml", ".yml", ".txt", ".lua", ".json", ".tsv", ".md",
    ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ocd",
    ".ocd2", ".bin", ".theme", ".conf",
}
ALLOWED_NAMES = {"LICENSE", "COPYING", "NOTICE", "AUTHORS", "README"}
SKIP_DIRS = {".git", ".github", "__pycache__", ".pytest_cache", ".mypy_cache", "node_modules", "build", "dist"}


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: copy_data.py SOURCE DESTINATION", file=sys.stderr)
        return 2
    source, destination = (Path(argument) for argument in sys.argv[1:])
    if not source.is_dir():
        print(f"Missing source directory: {source}", file=sys.stderr)
        return 1
    destination.mkdir(parents=True, exist_ok=True)
    for current, directories, files in os.walk(source, followlinks=False):
        base = Path(current)
        directories[:] = sorted(directory for directory in directories if directory not in SKIP_DIRS)
        for directory in directories:
            if (base / directory).is_symlink():
                raise ValueError(f"Symlink not allowed in distributable data: {base / directory}")
        for filename in sorted(files):
            path = base / filename
            if path.is_symlink():
                raise ValueError(f"Symlink not allowed in distributable data: {path}")
            if not path.is_file():
                raise ValueError(f"Non-regular file in distributable data: {path}")
            if filename.endswith((".pyc", ".pyo")) or filename.startswith("."):
                continue
            is_lunar_database = path.relative_to(source) == Path("lua/lunar.db")
            if not is_lunar_database and path.suffix.lower() not in ALLOWED_SUFFIXES and filename not in ALLOWED_NAMES and not filename.startswith(("LICENSE.", "COPYING.", "NOTICE.")):
                raise ValueError(f"Unrecognized distributable file (review before packaging): {path}")
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            target.chmod(0o644)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
