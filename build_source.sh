#!/usr/bin/env bash
set -euo pipefail
umask 022

PROJECT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
CONTROL="$PROJECT_ROOT/packaging/control"
PACKAGE=$(sed -n 's/^Package: //p' "$CONTROL")
APP_VERSION=$(sed -n 's/^Version: //p' "$CONTROL")
if [[ -z "$PACKAGE" || -z "$APP_VERSION" ]]; then
  printf 'Missing application package metadata in %s\n' "$CONTROL" >&2
  exit 1
fi

OUTPUT_DIR=$(realpath -m -- "${1:-$PROJECT_ROOT/dist}")
SCRATCH=$(mktemp -d)
PENDING_ARCHIVE=
cleanup() {
  [[ -z "$PENDING_ARCHIVE" ]] || rm -f -- "$PENDING_ARCHIVE"
  rm -rf -- "$SCRATCH"
}
trap cleanup EXIT

SOURCE_ROOT="$SCRATCH/${PACKAGE}-${APP_VERSION}"
mkdir -p "$SOURCE_ROOT/rime_ice" "$SOURCE_ROOT/data/rime" "$SOURCE_ROOT/data/themes" \
  "$SOURCE_ROOT/LICENSES" "$SOURCE_ROOT/tests" "$SOURCE_ROOT/packaging"
cp "$PROJECT_ROOT"/rime_ice/*.py "$SOURCE_ROOT/rime_ice/"
cp "$PROJECT_ROOT"/tests/*.py "$PROJECT_ROOT/tests/session.conf" "$SOURCE_ROOT/tests/"
cp "$PROJECT_ROOT/prepare_data.py" "$PROJECT_ROOT/prepare_themes.py" "$SOURCE_ROOT/"
python3 "$PROJECT_ROOT/packaging/copy_data.py" "$PROJECT_ROOT/data/rime" "$SOURCE_ROOT/data/rime"
shopt -s nullglob
themes=("$PROJECT_ROOT"/data/themes/rime-ice-*)
if (( ${#themes[@]} == 0 )); then
  printf 'No public Rime Ice themes found.\n' >&2
  exit 1
fi
for theme in "${themes[@]}"; do
  [[ -d "$theme" ]] || continue
  [[ -f "$theme/LICENSE" ]] || { printf 'Theme lacks LICENSE: %s\n' "$theme" >&2; exit 1; }
  python3 "$PROJECT_ROOT/packaging/copy_data.py" "$theme" "$SOURCE_ROOT/data/themes/$(basename -- "$theme")"
done
cp "$PROJECT_ROOT/data/rime-ice.svg" "$SOURCE_ROOT/data/"
python3 "$PROJECT_ROOT/packaging/copy_data.py" "$PROJECT_ROOT/LICENSES" "$SOURCE_ROOT/LICENSES"

cp "$PROJECT_ROOT"/{README.txt,LICENSE,UPSTREAM.json,THEME_UPSTREAM.json,build_deb.sh,build_source.sh,build_offline.sh,build_sources.sh,install-offline.sh} "$SOURCE_ROOT/"
if [[ -f "$PROJECT_ROOT/README.md" ]]; then
  cp "$PROJECT_ROOT/README.md" "$SOURCE_ROOT/"
fi
if [[ -f "$PROJECT_ROOT/docs/settings-preview.png" ]]; then
  mkdir -p "$SOURCE_ROOT/docs"
  cp "$PROJECT_ROOT/docs/settings-preview.png" "$SOURCE_ROOT/docs/"
fi
cp "$PROJECT_ROOT"/packaging/{control,control-compat,rime-ice,rime-ice-settings,rime-ice.desktop,README-offline.txt,README.txt,copy_data.py,make_index.py,collect_sources.py} "$SOURCE_ROOT/packaging/"

find "$SOURCE_ROOT" -type d -exec chmod 0755 {} +
find "$SOURCE_ROOT" -type f -exec chmod 0644 {} +
chmod 0755 "$SOURCE_ROOT"/{build_deb.sh,build_source.sh,build_offline.sh,build_sources.sh,install-offline.sh} \
  "$SOURCE_ROOT/packaging/rime-ice" "$SOURCE_ROOT/packaging/rime-ice-settings"

mkdir -p "$OUTPUT_DIR"
OUTPUT="$OUTPUT_DIR/${PACKAGE}_${APP_VERSION}_source.tar.gz"
PENDING_ARCHIVE=$(mktemp "$OUTPUT_DIR/.rime-ice-source.XXXXXXXX.tar.gz")
tar -C "$SCRATCH" -czf "$PENDING_ARCHIVE" "${PACKAGE}-${APP_VERSION}"
chmod 0644 "$PENDING_ARCHIVE"
mv -f -- "$PENDING_ARCHIVE" "$OUTPUT"
PENDING_ARCHIVE=
printf 'Created %s\n' "$OUTPUT"
