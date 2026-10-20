#!/usr/bin/env python3
"""Resume and verify Ubuntu source downloads for an offline binary bundle."""

import concurrent.futures
import email.parser
import hashlib
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ALLOWED_SOURCE_SUFFIXES = (".dsc", ".diff.gz", ".asc")
MAX_WORKERS = 4


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def source_file(name: str) -> bool:
    return name.endswith(ALLOWED_SOURCE_SUFFIXES) or ".tar." in name


def parse_dsc(path: Path) -> tuple[str, str, list[tuple[str, int, str]]]:
    text = path.read_text(encoding="utf-8")
    if text.startswith("-----BEGIN PGP SIGNED MESSAGE-----"):
        lines = text.splitlines()
        try:
            text = "\n".join(lines[lines.index("") + 1 :]).split(
                "-----BEGIN PGP SIGNATURE-----", 1
            )[0]
        except ValueError as error:
            raise ValueError(f"Malformed clearsigned dsc: {path}") from error
    message = email.parser.Parser().parsestr(text)
    name = message.get("Source")
    version = message.get("Version")
    checksums = message.get("Checksums-Sha256")
    if not name or not version or not checksums:
        raise ValueError(f"Missing Source, Version or Checksums-Sha256 in {path}")
    references = []
    for line in checksums.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 3:
            raise ValueError(f"Malformed Checksums-Sha256 entry in {path}: {line}")
        sha256, size_text, filename = parts
        if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
            raise ValueError(f"Invalid SHA256 in {path}: {line}")
        if not size_text.isdecimal() or Path(filename).name != filename or filename in ("", ".", ".."):
            raise ValueError(f"Invalid source filename/size in {path}: {line}")
        if not source_file(filename):
            raise ValueError(f"Unexpected source file type in {path}: {filename}")
        references.append((filename, int(size_text), sha256))
    if not references:
        raise ValueError(f"No referenced source files in {path}")
    return name, version, references


def verify_dsc(path: Path, expected_spec: str) -> list[Path]:
    name, version, references = parse_dsc(path)
    if f"{name}={version}" != expected_spec:
        raise ValueError(f"{path} describes {name}={version}, expected {expected_spec}")
    files = [path]
    for filename, size, sha256 in references:
        item = path.parent / filename
        if not item.is_file() or item.stat().st_size != size or digest(item) != sha256:
            raise ValueError(f"Missing or corrupt source file: {item}")
        files.append(item)
    return files


def worker(spec: str, base_config: str, cache: Path) -> tuple[str, list[Path]]:
    key = hashlib.sha256(spec.encode("utf-8")).hexdigest()
    directory = cache / key
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "archives" / "partial").mkdir(parents=True, exist_ok=True)
    (directory / "log").mkdir(exist_ok=True)
    config = directory / "apt.conf"
    config.write_text(
        base_config
        + f'\nDir::Cache::archives "{directory / "archives"}";'
        + f'\nDir::Cache::pkgcache "{directory / "pkgcache.bin"}";'
        + f'\nDir::Cache::srcpkgcache "{directory / "srcpkgcache.bin"}";'
        + f'\nDir::State::extended_states "{directory / "extended_states"}";'
        + f'\nDir::Log "{directory / "log"}";\n',
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["APT_CONFIG"] = str(config)
    log_path = directory / "worker.log"
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n=== {datetime.now(timezone.utc).isoformat()} {spec} ===\n")
        log.flush()
        result = subprocess.run(
            ["apt-get", "--download-only", "source", spec],
            cwd=directory,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
        log.write(f"exit={result.returncode}\n")
    if result.returncode:
        raise RuntimeError(f"{spec}: apt-get exit {result.returncode}; see {log_path}")
    dscs = sorted(directory.glob("*.dsc"))
    if len(dscs) != 1:
        raise ValueError(f"{spec}: expected one .dsc, found {len(dscs)}; see {directory}")
    return spec, verify_dsc(dscs[0], spec)


def main() -> int:
    if len(sys.argv) != 6:
        print("usage: collect_sources.py SPECS BINARY_TSV BASE_APT_CONFIG CACHE OUTPUT", file=sys.stderr)
        return 2
    specs_path, binary_tsv, config_path, cache, output = map(Path, sys.argv[1:])
    specs = specs_path.read_text(encoding="utf-8").splitlines()
    expected_specs = len(specs)
    if not specs or len(set(specs)) != expected_specs:
        raise ValueError("Source specs must be nonempty and unique")
    jobs = int(os.environ.get("RIME_ICE_SOURCE_JOBS", str(MAX_WORKERS)))
    if not 1 <= jobs <= MAX_WORKERS:
        raise ValueError("RIME_ICE_SOURCE_JOBS must be between 1 and 4")
    base_config = config_path.read_text(encoding="utf-8")
    cache.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    completed = []
    errors = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = {executor.submit(worker, spec, base_config, cache): spec for spec in specs}
        for future in concurrent.futures.as_completed(futures):
            spec = futures[future]
            try:
                completed.append(future.result())
                print(f"[{len(completed)}/{len(specs)}] verified {spec}", flush=True)
            except Exception as error:
                errors.append(f"{spec}: {error}")
                print(f"FAILED {spec}: {error}", file=sys.stderr, flush=True)
    if errors:
        raise RuntimeError(f"{len(errors)} source specs failed; downloaded files remain in {cache}")
    if len(completed) != expected_specs:
        raise ValueError(f"Only {len(completed)} of {expected_specs} specs completed")

    for spec, files in sorted(completed):
        for item in files:
            if not source_file(item.name):
                raise ValueError(f"Unexpected source file: {item}")
            target = output / item.name
            if target.exists():
                if target.stat().st_size != item.stat().st_size or digest(target) != digest(item):
                    raise ValueError(f"Different contents share filename {item.name}: {target} and {item}")
            else:
                shutil.copyfile(item, target)

    dscs = sorted(output.glob("*.dsc"))
    if len(dscs) != expected_specs:
        raise ValueError(f"Expected {expected_specs} .dsc files after merging, got {len(dscs)}")
    observed = set()
    for dsc in dscs:
        name, version, _ = parse_dsc(dsc)
        spec = f"{name}={version}"
        if spec in observed:
            raise ValueError(f"Duplicate source spec after merging: {spec}")
        verify_dsc(dsc, spec)
        observed.add(spec)
    if observed != set(specs):
        raise ValueError(f"Source spec mismatch: missing={sorted(set(specs)-observed)}, extra={sorted(observed-set(specs))}")

    shutil.copyfile(specs_path, output / "SOURCE_PACKAGES.txt")
    shutil.copyfile(binary_tsv, output / "BINARY_PACKAGES.tsv")
    with (output / "SHA256SUMS").open("w", encoding="utf-8") as manifest:
        for item in sorted(output.iterdir()):
            if item.is_file() and source_file(item.name):
                manifest.write(f"{digest(item)}  ./{item.name}\n")
    print(f"Verified {len(observed)} exact source specs and {len(dscs)} .dsc files", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
