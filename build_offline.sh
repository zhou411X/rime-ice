#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REUSE_BUNDLE=false
if [[ "${1:-}" == --reuse-bundle ]]; then
  REUSE_BUNDLE=true
  shift
fi
DIST_DIR=${1:-"$PROJECT_ROOT/dist"}
APP_DEB="$DIST_DIR/rime-ice-settings_0.1.0_all.deb"
OFFLINE_ARCHIVE="$DIST_DIR/rime-ice-settings_0.1.0_ubuntu24.04_amd64_offline.tar.gz"
ARCH=amd64
RELEASE=noble

if [[ ! -f "$APP_DEB" ]]; then
  printf 'Build the application package first: %s\n' "$APP_DEB" >&2
  exit 1
fi
source /etc/os-release
if [[ "${ID:-}" != ubuntu || "${VERSION_ID:-}" != 24.04 || "$(dpkg --print-architecture)" != "$ARCH" ]]; then
  printf 'This bundle builder requires Ubuntu 24.04 amd64.\n' >&2
  exit 1
fi
if [[ "$REUSE_BUNDLE" == false && ! -f /usr/share/keyrings/ubuntu-archive-keyring.gpg ]]; then
  printf 'Ubuntu archive signing keyring is missing.\n' >&2
  exit 1
fi

SCRATCH=$(mktemp -d)
trap 'rm -rf -- "$SCRATCH"' EXIT
mkdir -p "$SCRATCH/lists/partial" "$SCRATCH/archives/partial" "$SCRATCH/bundle/packages" "$SCRATCH/apt.conf.d" "$SCRATCH/sources.list.d" "$SCRATCH/preferences.d" "$SCRATCH/log"
: > "$SCRATCH/status"

if [[ "$REUSE_BUNDLE" == true ]]; then
  if [[ ! -f "$OFFLINE_ARCHIVE" ]]; then
    printf 'Cannot reuse missing archive: %s\n' "$OFFLINE_ARCHIVE" >&2
    exit 1
  fi
  tar -C "$SCRATCH" -xzf "$OFFLINE_ARCHIVE"
  if [[ -f "$SCRATCH/bundle/FULL_SHA256SUMS" ]]; then
    (cd "$SCRATCH/bundle" && sha256sum --check --strict FULL_SHA256SUMS)
  else
    (cd "$SCRATCH/bundle" && sha256sum --check --strict SHA256SUMS)
  fi
  old_app="$SCRATCH/bundle/packages/$(basename -- "$APP_DEB")"
  if [[ ! -f "$old_app" || "$(dpkg-deb --field "$old_app" Depends)" != "$(dpkg-deb --field "$APP_DEB" Depends)" ]]; then
    printf 'Application dependencies changed; rebuild the full bundle without --reuse-bundle.\n' >&2
    exit 1
  fi
  cp "$APP_DEB" "$old_app"
else
MIRROR=${RIME_ICE_APT_MIRROR:-https://archive.ubuntu.com/ubuntu}
SECURITY_MIRROR=${RIME_ICE_APT_SECURITY_MIRROR:-https://security.ubuntu.com/ubuntu}
cat > "$SCRATCH/sources.list" <<EOF
deb [arch=$ARCH signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] $MIRROR $RELEASE main universe
deb [arch=$ARCH signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] $MIRROR $RELEASE-updates main universe
deb [arch=$ARCH signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] $SECURITY_MIRROR $RELEASE-security main universe
EOF

# APT_CONFIG is read before the system apt.conf.d directory, disabling host
# hooks and preferences as well as host package sources for this process.
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
APT::Architecture "$ARCH";
APT::Architectures { "$ARCH"; };
APT::Sandbox::User "$(id -un)";
Debug::NoLocking "true";
Acquire::AllowInsecureRepositories "false";
Acquire::AllowDowngradeToInsecureRepositories "false";
APT::Get::AllowUnauthenticated "false";
EOF
export APT_CONFIG="$SCRATCH/apt.conf"

# An empty dpkg status makes APT download the dependency closure from scratch,
# independently of which packages happen to be installed on this computer.
# Every mutable APT path is confined to SCRATCH; no package is installed here.
apt-get update
apt-get --yes --download-only --no-install-recommends install "$APP_DEB"

cp "$APP_DEB" "$SCRATCH/bundle/packages/"
shopt -s nullglob
downloaded=("$SCRATCH"/archives/*.deb)
if (( ${#downloaded[@]} == 0 )); then
  printf 'APT downloaded no dependencies; refusing to produce an incomplete bundle.\n' >&2
  exit 1
fi
cp "${downloaded[@]}" "$SCRATCH/bundle/packages/"
fi
install -m 0755 "$PROJECT_ROOT/install-offline.sh" "$SCRATCH/bundle/install-offline.sh"
install -m 0644 "$PROJECT_ROOT/packaging/README-offline.txt" "$SCRATCH/bundle/README.txt"
python3 "$PROJECT_ROOT/packaging/make_index.py" "$SCRATCH/bundle"

# Include the exact project source snapshot used to build the application.
SOURCE_ROOT="$SCRATCH/source/rime-ice-settings-0.1.0"
mkdir -p "$SOURCE_ROOT/rime_ice" "$SOURCE_ROOT/data/rime" "$SOURCE_ROOT/data/themes" "$SOURCE_ROOT/packaging"
mkdir -p "$SOURCE_ROOT/tests"
cp "$PROJECT_ROOT"/rime_ice/*.py "$SOURCE_ROOT/rime_ice/"
cp "$PROJECT_ROOT"/tests/*.py "$PROJECT_ROOT/tests/session.conf" "$SOURCE_ROOT/tests/"
cp "$PROJECT_ROOT/prepare_data.py" "$SOURCE_ROOT/"
python3 "$PROJECT_ROOT/packaging/copy_data.py" "$PROJECT_ROOT/data/rime" "$SOURCE_ROOT/data/rime"
for theme in "$PROJECT_ROOT"/data/themes/rime-ice-*; do
  [[ -d "$theme" ]] || continue
  python3 "$PROJECT_ROOT/packaging/copy_data.py" "$theme" "$SOURCE_ROOT/data/themes/$(basename -- "$theme")"
done
cp "$PROJECT_ROOT/data/rime-ice.svg" "$SOURCE_ROOT/data/"
cp "$PROJECT_ROOT"/{README.txt,LICENSE,UPSTREAM.json,build_deb.sh,build_offline.sh,build_sources.sh,install-offline.sh} "$SOURCE_ROOT/"
cp "$PROJECT_ROOT"/packaging/{control,rime-ice-settings,rime-ice-settings.desktop,README-offline.txt,README.txt,copy_data.py,make_index.py,collect_sources.py} "$SOURCE_ROOT/packaging/"
mkdir -p "$SCRATCH/bundle/source"
tar -C "$SCRATCH/source" -czf "$SCRATCH/bundle/source/rime-ice-settings_0.1.0_source.tar.gz" rime-ice-settings-0.1.0

(
  cd "$SCRATCH/bundle"
  sha256sum packages/*.deb > SHA256SUMS
  printf 'Package\tVersion\tArchitecture\tSource\tFile\n' > PACKAGES.tsv
  for file in packages/*.deb; do
    package=$(dpkg-deb --field "$file" Package)
    version=$(dpkg-deb --field "$file" Version)
    architecture=$(dpkg-deb --field "$file" Architecture)
    source_package=$(dpkg-deb --field "$file" Source)
    printf '%s\t%s\t%s\t%s\t%s\n' "$package" "$version" "$architecture" "${source_package:-$package}" "$file" >> PACKAGES.tsv
  done
  sha256sum Packages Packages.gz SHA256SUMS PACKAGES.tsv README.txt install-offline.sh packages/*.deb source/*.tar.gz > FULL_SHA256SUMS
)

mkdir -p "$DIST_DIR"
tar -C "$SCRATCH" -czf "$OFFLINE_ARCHIVE" bundle
cp "$SCRATCH/bundle/source/rime-ice-settings_0.1.0_source.tar.gz" "$DIST_DIR/"
printf 'Created %s\n' "$OFFLINE_ARCHIVE"
