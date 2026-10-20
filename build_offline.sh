#!/usr/bin/env bash
set -euo pipefail
umask 022

PROJECT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
CONTROL="$PROJECT_ROOT/packaging/control"
COMPAT_CONTROL="$PROJECT_ROOT/packaging/control-compat"
PACKAGE=$(sed -n 's/^Package: //p' "$CONTROL")
APP_VERSION=$(sed -n 's/^Version: //p' "$CONTROL")
COMPAT_PACKAGE=$(sed -n 's/^Package: //p' "$COMPAT_CONTROL")
COMPAT_VERSION=$(sed -n 's/^Version: //p' "$COMPAT_CONTROL")
if [[ -z "$PACKAGE" || -z "$APP_VERSION" || "$COMPAT_VERSION" != "$APP_VERSION" ]]; then
  printf 'Inconsistent Debian package metadata.\n' >&2
  exit 1
fi

FROM_BUNDLE=
DIST_ARG=
while (( $# )); do
  case "$1" in
    --reuse-bundle)
      [[ -z "$FROM_BUNDLE" ]] || { printf 'Select only one reuse option.\n' >&2; exit 2; }
      FROM_BUNDLE=default
      shift
      ;;
    --from-bundle)
      [[ -z "$FROM_BUNDLE" && $# -ge 2 ]] || { printf 'Invalid --from-bundle argument.\n' >&2; exit 2; }
      FROM_BUNDLE=$2
      shift 2
      ;;
    --)
      shift
      [[ $# -eq 1 && -z "$DIST_ARG" ]] || { printf 'Expected one output directory.\n' >&2; exit 2; }
      DIST_ARG=$1
      shift
      ;;
    -*)
      printf 'Unknown option: %s\n' "$1" >&2
      exit 2
      ;;
    *)
      [[ -z "$DIST_ARG" ]] || { printf 'Expected one output directory.\n' >&2; exit 2; }
      DIST_ARG=$1
      shift
      ;;
  esac
done

DIST_DIR=$(realpath -m -- "${DIST_ARG:-$PROJECT_ROOT/dist}")
APP_DEB="$DIST_DIR/${PACKAGE}_${APP_VERSION}_all.deb"
COMPAT_DEB="$DIST_DIR/${COMPAT_PACKAGE}_${APP_VERSION}_all.deb"
OFFLINE_ARCHIVE="$DIST_DIR/${PACKAGE}_${APP_VERSION}_ubuntu24.04_amd64_offline.tar.gz"
if [[ "$FROM_BUNDLE" == default ]]; then
  FROM_BUNDLE=$OFFLINE_ARCHIVE
elif [[ -n "$FROM_BUNDLE" ]]; then
  FROM_BUNDLE=$(realpath -m -- "$FROM_BUNDLE")
fi
for package_file in "$APP_DEB" "$COMPAT_DEB"; do
  [[ -f "$package_file" ]] || { printf 'Build the Debian packages first: %s\n' "$package_file" >&2; exit 1; }
done
source /etc/os-release
if [[ "${ID:-}" != ubuntu || "${VERSION_ID:-}" != 24.04 || "$(dpkg --print-architecture)" != amd64 ]]; then
  printf 'This bundle builder requires Ubuntu 24.04 amd64.\n' >&2
  exit 1
fi
if [[ -z "$FROM_BUNDLE" && ! -f /usr/share/keyrings/ubuntu-archive-keyring.gpg ]]; then
  printf 'Ubuntu archive signing keyring is missing.\n' >&2
  exit 1
fi

SCRATCH=$(mktemp -d)
trap 'rm -rf -- "$SCRATCH"' EXIT
mkdir -p "$SCRATCH/lists/partial" "$SCRATCH/archives/partial" "$SCRATCH/bundle/packages" \
  "$SCRATCH/apt.conf.d" "$SCRATCH/sources.list.d" "$SCRATCH/preferences.d" "$SCRATCH/log"
: > "$SCRATCH/status"

if [[ -n "$FROM_BUNDLE" ]]; then
  [[ -f "$FROM_BUNDLE" ]] || { printf 'Cannot reuse missing archive: %s\n' "$FROM_BUNDLE" >&2; exit 1; }
  tar -C "$SCRATCH" -xzf "$FROM_BUNDLE"
  [[ -f "$SCRATCH/bundle/FULL_SHA256SUMS" ]] || { printf 'Reuse archive lacks full manifest.\n' >&2; exit 1; }
  (cd "$SCRATCH/bundle" && sha256sum --check --strict FULL_SHA256SUMS)
  shopt -s nullglob
  old_packages=("$SCRATCH"/bundle/packages/*.deb)
  old_app=
  for old_deb in "${old_packages[@]}"; do
    old_name=$(dpkg-deb --field "$old_deb" Package)
    if [[ "$old_name" == "$PACKAGE" ]]; then
      old_app=$old_deb
      break
    fi
    if [[ "$old_name" == "$COMPAT_PACKAGE" && -z "$old_app" ]]; then
      old_app=$old_deb
    fi
  done
  if [[ -z "$old_app" || "$(dpkg-deb --field "$old_app" Depends)" != "$(dpkg-deb --field "$APP_DEB" Depends)" ]]; then
    printf 'Primary application dependencies changed; rebuild without --from-bundle.\n' >&2
    exit 1
  fi
  for old_deb in "${old_packages[@]}"; do
    old_name=$(dpkg-deb --field "$old_deb" Package)
    if [[ "$old_name" == "$PACKAGE" || "$old_name" == "$COMPAT_PACKAGE" ]]; then
      rm -f -- "$old_deb"
    fi
  done
  rm -f -- "$SCRATCH"/bundle/source/*.tar.gz
else
  MIRROR=${RIME_ICE_APT_MIRROR:-https://archive.ubuntu.com/ubuntu}
  SECURITY_MIRROR=${RIME_ICE_APT_SECURITY_MIRROR:-https://security.ubuntu.com/ubuntu}
  cat > "$SCRATCH/sources.list" <<EOF
deb [arch=amd64 signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] $MIRROR noble main universe
deb [arch=amd64 signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] $MIRROR noble-updates main universe
deb [arch=amd64 signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] $SECURITY_MIRROR noble-security main universe
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
  apt-get update
  apt-get --yes --download-only --no-install-recommends install "$APP_DEB" "$COMPAT_DEB"
  shopt -s nullglob
  downloaded=("$SCRATCH"/archives/*.deb)
  if (( ${#downloaded[@]} == 0 )); then
    printf 'APT downloaded no dependencies; refusing to produce an incomplete bundle.\n' >&2
    exit 1
  fi
  cp "${downloaded[@]}" "$SCRATCH/bundle/packages/"
fi

cp "$APP_DEB" "$COMPAT_DEB" "$SCRATCH/bundle/packages/"
install -m 0755 "$PROJECT_ROOT/install-offline.sh" "$SCRATCH/bundle/install-offline.sh"
install -m 0644 "$PROJECT_ROOT/packaging/README-offline.txt" "$SCRATCH/bundle/README.txt"
printf '%s=%s\n%s=%s\n' "$PACKAGE" "$APP_VERSION" "$COMPAT_PACKAGE" "$APP_VERSION" > "$SCRATCH/bundle/INSTALL_PACKAGES"
python3 "$PROJECT_ROOT/packaging/make_index.py" "$SCRATCH/bundle"

SOURCE_ROOT="$SCRATCH/source/${PACKAGE}-${APP_VERSION}"
mkdir -p "$SOURCE_ROOT/rime_ice" "$SOURCE_ROOT/data/rime" "$SOURCE_ROOT/data/themes" "$SOURCE_ROOT/packaging" "$SOURCE_ROOT/tests"
mkdir -p "$SOURCE_ROOT/LICENSES"
cp "$PROJECT_ROOT"/rime_ice/*.py "$SOURCE_ROOT/rime_ice/"
cp "$PROJECT_ROOT"/tests/*.py "$PROJECT_ROOT/tests/session.conf" "$SOURCE_ROOT/tests/"
cp "$PROJECT_ROOT/prepare_data.py" "$PROJECT_ROOT/prepare_themes.py" "$SOURCE_ROOT/"
python3 "$PROJECT_ROOT/packaging/copy_data.py" "$PROJECT_ROOT/data/rime" "$SOURCE_ROOT/data/rime"
for theme in "$PROJECT_ROOT"/data/themes/rime-ice-*; do
  [[ -d "$theme" ]] || continue
  python3 "$PROJECT_ROOT/packaging/copy_data.py" "$theme" "$SOURCE_ROOT/data/themes/$(basename -- "$theme")"
done
cp "$PROJECT_ROOT/data/rime-ice.svg" "$SOURCE_ROOT/data/"
cp -a "$PROJECT_ROOT/LICENSES/." "$SOURCE_ROOT/LICENSES/"
cp "$PROJECT_ROOT"/{README.txt,LICENSE,UPSTREAM.json,THEME_UPSTREAM.json,build_deb.sh,build_offline.sh,build_sources.sh,install-offline.sh} "$SOURCE_ROOT/"
cp "$PROJECT_ROOT"/packaging/{control,control-compat,rime-ice,rime-ice-settings,rime-ice.desktop,README-offline.txt,README.txt,copy_data.py,make_index.py,collect_sources.py} "$SOURCE_ROOT/packaging/"
mkdir -p "$SCRATCH/bundle/source"
tar -C "$SCRATCH/source" -czf "$SCRATCH/bundle/source/${PACKAGE}_${APP_VERSION}_source.tar.gz" "${PACKAGE}-${APP_VERSION}"

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
  sha256sum Packages Packages.gz SHA256SUMS PACKAGES.tsv README.txt INSTALL_PACKAGES install-offline.sh packages/*.deb source/*.tar.gz > FULL_SHA256SUMS
)

mkdir -p "$DIST_DIR"
TEMP_ARCHIVE=$(mktemp "$DIST_DIR/.rime-ice-offline.XXXXXXXX.tar.gz")
trap 'rm -rf -- "$SCRATCH"; rm -f -- "$TEMP_ARCHIVE"' EXIT
tar -C "$SCRATCH" -czf "$TEMP_ARCHIVE" bundle
mv -f -- "$TEMP_ARCHIVE" "$OFFLINE_ARCHIVE"
cp "$SCRATCH/bundle/source/${PACKAGE}_${APP_VERSION}_source.tar.gz" "$DIST_DIR/"
printf 'Created %s\n' "$OFFLINE_ARCHIVE"
