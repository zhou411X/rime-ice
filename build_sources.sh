#!/usr/bin/env bash
set -euo pipefail
umask 022

PROJECT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
DIST_DIR=$(realpath -m -- "${1:-$PROJECT_ROOT/dist}")
BUNDLE="$DIST_DIR/rime-ice-settings_0.1.0_ubuntu24.04_amd64_offline.tar.gz"
OUTPUT="$DIST_DIR/rime-ice-settings_0.1.0_ubuntu24.04_sources.tar.gz"
CACHE="$DIST_DIR/source-cache"
if [[ ! -f "$BUNDLE" ]]; then
  printf 'Build the offline runtime archive first: %s\n' "$BUNDLE" >&2
  exit 1
fi
source /etc/os-release
if [[ "${ID:-}" != ubuntu || "${VERSION_ID:-}" != 24.04 || "$(dpkg --print-architecture)" != amd64 ]]; then
  printf 'This source collector requires Ubuntu 24.04 amd64.\n' >&2
  exit 1
fi
if [[ ! -f /usr/share/keyrings/ubuntu-archive-keyring.gpg ]]; then
  printf 'Ubuntu archive signing keyring is missing.\n' >&2
  exit 1
fi

mkdir -p "$DIST_DIR" "$CACHE"
SCRATCH=$(mktemp -d)
PENDING_ARCHIVE=
cleanup() {
  [[ -z "$PENDING_ARCHIVE" ]] || rm -f -- "$PENDING_ARCHIVE"
  rm -rf -- "$SCRATCH"
}
trap cleanup EXIT
mkdir -p "$SCRATCH/lists/partial" "$SCRATCH/archives/partial" "$SCRATCH/ubuntu-sources" \
  "$SCRATCH/apt.conf.d" "$SCRATCH/sources.list.d" "$SCRATCH/preferences.d" "$SCRATCH/log"
: > "$SCRATCH/status"
tar -C "$SCRATCH" -xzf "$BUNDLE" bundle/PACKAGES.tsv

python3 - "$SCRATCH/bundle/PACKAGES.tsv" > "$SCRATCH/specs.txt" <<'PY'
import csv
import re
import sys

specs = set()
with open(sys.argv[1], newline="", encoding="utf-8") as source:
    for row in csv.DictReader(source, delimiter="\t"):
        if row["Package"] == "rime-ice-settings":
            continue
        match = re.fullmatch(r"([^ ]+)(?: \(([^)]+)\))?", row["Source"])
        if not match:
            raise ValueError(f"Unrecognized source metadata: {row['Source']}")
        specs.add(f"{match.group(1)}={match.group(2) or row['Version']}")
print("\n".join(sorted(specs)))
PY

MIRROR=${RIME_ICE_APT_MIRROR:-https://archive.ubuntu.com/ubuntu}
SECURITY_MIRROR=${RIME_ICE_APT_SECURITY_MIRROR:-https://security.ubuntu.com/ubuntu}
cat > "$SCRATCH/sources.list" <<EOF
deb-src [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] $MIRROR noble main universe
deb-src [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] $MIRROR noble-updates main universe
deb-src [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] $SECURITY_MIRROR noble-security main universe
EOF
cat > "$SCRATCH/apt.conf" <<EOF
Dir::Etc::main "/dev/null";
Dir::Etc::parts "$SCRATCH/apt.conf.d";
Dir::Etc::sourcelist "$SCRATCH/sources.list";
Dir::Etc::sourceparts "$SCRATCH/sources.list.d";
Dir::Etc::preferences "/dev/null";
Dir::Etc::preferencesparts "$SCRATCH/preferences.d";
Dir::State::status "$SCRATCH/status";
Dir::State::lists "$SCRATCH/lists";
Dir::State::extended_states "$SCRATCH/extended_states";
Dir::Cache::archives "$SCRATCH/archives";
Dir::Cache::pkgcache "$SCRATCH/pkgcache.bin";
Dir::Cache::srcpkgcache "$SCRATCH/srcpkgcache.bin";
Dir::Log "$SCRATCH/log";
APT::Architecture "amd64";
APT::Architectures { "amd64"; };
APT::Sandbox::User "$(id -un)";
Debug::NoLocking "true";
Acquire::AllowInsecureRepositories "false";
Acquire::AllowDowngradeToInsecureRepositories "false";
APT::Get::AllowUnauthenticated "false";
EOF
export APT_CONFIG="$SCRATCH/apt.conf"

# Refresh authenticated indexes on every invocation; downloaded files persist.
apt-get update
python3 "$PROJECT_ROOT/packaging/collect_sources.py" \
  "$SCRATCH/specs.txt" "$SCRATCH/bundle/PACKAGES.tsv" \
  "$SCRATCH/apt.conf" "$CACHE" "$SCRATCH/ubuntu-sources"

PENDING_ARCHIVE=$(mktemp "$DIST_DIR/.rime-ice-sources.XXXXXXXX.tar.gz")
tar -C "$SCRATCH" -czf "$PENDING_ARCHIVE" ubuntu-sources
chmod 0644 "$PENDING_ARCHIVE"
mv -f -- "$PENDING_ARCHIVE" "$OUTPUT"
PENDING_ARCHIVE=
printf 'Created %s\n' "$OUTPUT"
