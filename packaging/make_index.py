#!/usr/bin/env python3
"""Generate a local APT Packages index from the verified bundle debs."""

import gzip
import hashlib
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(sys.argv[1])
    packages = sorted((root / "packages").glob("*.deb"))
    if not packages:
        raise ValueError("No packages to index")
    entries = []
    for package in packages:
        control = subprocess.check_output(["dpkg-deb", "--field", str(package)], text=True).rstrip()
        payload = package.read_bytes()
        entries.append(
            f"{control}\nFilename: ./packages/{package.name}\n"
            f"Size: {len(payload)}\nSHA256: {hashlib.sha256(payload).hexdigest()}\n"
        )
    index = "\n".join(entries).encode()
    (root / "Packages").write_bytes(index)
    with (root / "Packages.gz").open("wb") as output:
        with gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0) as compressed:
            compressed.write(index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
