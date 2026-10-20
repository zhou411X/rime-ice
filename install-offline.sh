#!/usr/bin/env bash
set -euo pipefail

BUNDLE_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source /etc/os-release
if [[ "${ID:-}" != ubuntu || "${VERSION_ID:-}" != 24.04 || "$(dpkg --print-architecture)" != amd64 ]]; then
  printf 'This bundle requires Ubuntu 24.04 amd64.\n' >&2
  exit 1
fi
for manifest in SHA256SUMS FULL_SHA256SUMS INSTALL_PACKAGES; do
  if [[ ! -f "$BUNDLE_ROOT/$manifest" ]]; then
    printf 'Missing bundle metadata: %s\n' "$manifest" >&2
    exit 1
  fi
done

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

mapfile -t requested < "$BUNDLE_ROOT/INSTALL_PACKAGES"
if (( ${#requested[@]} != 2 )); then
  printf 'Expected the primary and transitional package versions in INSTALL_PACKAGES.\n' >&2
  exit 1
fi
for spec in "${requested[@]}"; do
  if [[ ! "$spec" =~ ^[a-z0-9][a-z0-9+.-]*=[0-9][^[:space:]]*$ ]]; then
    printf 'Invalid package specification: %s\n' "$spec" >&2
    exit 1
  fi
  found=false
  for deb in "${packages[@]}"; do
    if [[ "$(dpkg-deb --field "$deb" Package)=$(dpkg-deb --field "$deb" Version)" == "$spec" ]]; then
      found=true
      break
    fi
  done
  if [[ "$found" == false ]]; then
    printf 'Requested package absent from verified bundle: %s\n' "$spec" >&2
    exit 1
  fi
done

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
# The sole source is the verified local archive; there is no network URI.
apt-get update

printf '\nAPT installation preview:\n'
apt-get --simulate --yes --no-download --no-install-recommends --no-remove --no-allow-downgrades install "${requested[@]}"

if [[ "${1:-}" != --yes ]]; then
  printf '\nInstall the packages shown above? [y/N] '
  read -r answer
  [[ "$answer" == y || "$answer" == Y ]] || exit 0
fi

apt-get --yes --no-download --no-install-recommends --no-remove --no-allow-downgrades install "${requested[@]}"
