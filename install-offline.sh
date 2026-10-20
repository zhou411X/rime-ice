#!/usr/bin/env bash
set -euo pipefail

BUNDLE_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source /etc/os-release
if [[ "${ID:-}" != ubuntu || "${VERSION_ID:-}" != 24.04 || "$(dpkg --print-architecture)" != amd64 ]]; then
  printf 'This bundle requires Ubuntu 24.04 amd64.\n' >&2
  exit 1
fi
if [[ ! -f "$BUNDLE_ROOT/SHA256SUMS" ]]; then
  printf 'Missing SHA256SUMS manifest.\n' >&2
  exit 1
fi
if [[ ! -f "$BUNDLE_ROOT/FULL_SHA256SUMS" ]]; then
  printf 'Missing FULL_SHA256SUMS manifest.\n' >&2
  exit 1
fi

shopt -s nullglob
packages=("$BUNDLE_ROOT"/packages/*.deb)
if (( ${#packages[@]} == 0 )); then
  printf 'No Debian packages found.\n' >&2
  exit 1
fi
expected_count=$(wc -l < "$BUNDLE_ROOT/SHA256SUMS")
if (( expected_count != ${#packages[@]} )); then
  printf 'Package count differs from SHA256SUMS; refusing installation.\n' >&2
  exit 1
fi
(
  cd "$BUNDLE_ROOT"
  sha256sum --check --strict FULL_SHA256SUMS
  sha256sum --check --strict SHA256SUMS
)

if (( EUID != 0 )); then
  printf 'Run this installer with sudo to install the verified packages.\n' >&2
  exit 1
fi

SCRATCH=$(mktemp -d)
trap 'rm -rf -- "$SCRATCH"' EXIT
mkdir -p "$SCRATCH/lists/partial" "$SCRATCH/archives/partial" "$SCRATCH/apt.conf.d" "$SCRATCH/sources.list.d" "$SCRATCH/preferences.d" "$SCRATCH/log"
ln -s "$BUNDLE_ROOT" "$SCRATCH/repo"
cp "${packages[@]}" "$SCRATCH/archives/"
printf 'deb [trusted=yes] file:%s/repo ./\n' "$SCRATCH" > "$SCRATCH/sources.list"
cat > "$SCRATCH/apt.conf" <<EOF
Dir::Etc::main "/dev/null";
Dir::Etc::parts "$SCRATCH/apt.conf.d";
Dir::Etc::sourcelist "$SCRATCH/sources.list";
Dir::Etc::sourceparts "$SCRATCH/sources.list.d";
Dir::Etc::preferences "/dev/null";
Dir::Etc::preferencesparts "$SCRATCH/preferences.d";
Dir::State::lists "$SCRATCH/lists";
Dir::Cache::archives "$SCRATCH/archives";
Dir::Cache::pkgcache "$SCRATCH/pkgcache.bin";
Dir::Cache::srcpkgcache "$SCRATCH/srcpkgcache.bin";
Dir::Log "$SCRATCH/log";
APT::Sandbox::User "root";
Acquire::Retries "0";
EOF
export APT_CONFIG="$SCRATCH/apt.conf"
# This index is read only from the extracted bundle; no network source exists.
apt-get update

printf '\nAPT installation preview:\n'
apt-get --simulate --yes --no-download --no-install-recommends --no-remove --no-allow-downgrades install rime-ice-settings

if [[ "${1:-}" != --yes ]]; then
  printf '\nInstall the packages shown above? [y/N] '
  read -r answer
  [[ "$answer" == y || "$answer" == Y ]] || exit 0
fi

apt-get --yes --no-download --no-install-recommends --no-remove --no-allow-downgrades install rime-ice-settings
