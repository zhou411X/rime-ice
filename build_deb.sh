#!/usr/bin/env bash
set -euo pipefail
umask 022

PROJECT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
VERSION=0.1.0
PACKAGE=rime-ice-settings
OUTPUT_DIR=${1:-"$PROJECT_ROOT/dist"}
STAGE=$(mktemp -d)
trap 'rm -rf -- "$STAGE"' EXIT
chmod 0755 "$STAGE"

for file in rime_ice/__init__.py rime_ice/app.py rime_ice/model.py data/rime-ice.svg README.txt LICENSE UPSTREAM.json; do
  if [[ ! -f "$PROJECT_ROOT/$file" ]]; then
    printf 'Missing required file: %s\n' "$file" >&2
    exit 1
  fi
done
for directory in data/rime data/themes; do
  if [[ ! -d "$PROJECT_ROOT/$directory" ]]; then
    printf 'Missing required directory: %s\n' "$directory" >&2
    exit 1
  fi
done

mkdir -p "$STAGE/DEBIAN" \
  "$STAGE/usr/bin" \
  "$STAGE/usr/lib/rime-ice/rime_ice" \
  "$STAGE/usr/share/rime-ice/rime" \
  "$STAGE/usr/share/fcitx5/themes" \
  "$STAGE/usr/share/applications" \
  "$STAGE/usr/share/icons/hicolor/scalable/apps" \
  "$STAGE/usr/share/doc/$PACKAGE"

cp "$PROJECT_ROOT"/rime_ice/*.py "$STAGE/usr/lib/rime-ice/rime_ice/"
python3 "$PROJECT_ROOT/packaging/copy_data.py" "$PROJECT_ROOT/data/rime" "$STAGE/usr/share/rime-ice/rime"
shopt -s nullglob
themes=("$PROJECT_ROOT"/data/themes/rime-ice-*)
if (( ${#themes[@]} == 0 )); then
  printf 'Missing data/themes/rime-ice-* theme directories\n' >&2
  exit 1
fi
theme_count=0
for theme in "${themes[@]}"; do
  [[ -d "$theme" ]] || continue
  python3 "$PROJECT_ROOT/packaging/copy_data.py" "$theme" "$STAGE/usr/share/fcitx5/themes/$(basename -- "$theme")"
  ((theme_count += 1))
done
if (( theme_count == 0 )); then
  printf 'No rime-ice-* theme directory found.\n' >&2
  exit 1
fi

install -m 0644 "$PROJECT_ROOT/data/rime-ice.svg" "$STAGE/usr/share/icons/hicolor/scalable/apps/rime-ice-settings.svg"
install -m 0644 "$PROJECT_ROOT/README.txt" "$STAGE/usr/share/doc/$PACKAGE/README"
install -m 0644 "$PROJECT_ROOT/LICENSE" "$STAGE/usr/share/doc/$PACKAGE/copyright"
install -m 0644 "$PROJECT_ROOT/UPSTREAM.json" "$STAGE/usr/share/doc/$PACKAGE/UPSTREAM.json"
install -m 0644 "$PROJECT_ROOT/packaging/rime-ice-settings.desktop" "$STAGE/usr/share/applications/rime-ice-settings.desktop"
install -m 0755 "$PROJECT_ROOT/packaging/rime-ice-settings" "$STAGE/usr/bin/rime-ice-settings"
install -m 0644 "$PROJECT_ROOT/packaging/control" "$STAGE/DEBIAN/control"

# Source checkout permissions can depend on the builder's umask. Debian
# payload permissions are fixed here so the archive is consistent.
find "$STAGE" -type d -exec chmod 0755 {} +
find "$STAGE" -type f -exec chmod 0644 {} +
chmod 0755 "$STAGE/usr/bin/rime-ice-settings"

mkdir -p "$OUTPUT_DIR"
dpkg-deb --build --root-owner-group "$STAGE" "$OUTPUT_DIR/${PACKAGE}_${VERSION}_all.deb"
