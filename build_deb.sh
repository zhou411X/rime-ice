#!/usr/bin/env bash
set -euo pipefail
umask 022

PROJECT_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
OUTPUT_DIR=${1:-"$PROJECT_ROOT/dist"}
CONTROL="$PROJECT_ROOT/packaging/control"
COMPAT_CONTROL="$PROJECT_ROOT/packaging/control-compat"
PACKAGE=$(sed -n 's/^Package: //p' "$CONTROL")
VERSION=$(sed -n 's/^Version: //p' "$CONTROL")
COMPAT_PACKAGE=$(sed -n 's/^Package: //p' "$COMPAT_CONTROL")
COMPAT_VERSION=$(sed -n 's/^Version: //p' "$COMPAT_CONTROL")
if [[ "$PACKAGE" != rime-ice || -z "$VERSION" || "$COMPAT_PACKAGE" != rime-ice-settings || "$COMPAT_VERSION" != "$VERSION" ]]; then
  printf 'Inconsistent primary/transitional Debian package metadata.\n' >&2
  exit 1
fi

STAGE=$(mktemp -d)
COMPAT_STAGE=$(mktemp -d)
trap 'rm -rf -- "$STAGE" "$COMPAT_STAGE"' EXIT
chmod 0755 "$STAGE" "$COMPAT_STAGE"

for file in rime_ice/__init__.py rime_ice/app.py rime_ice/model.py rime_ice/themes.py \
  data/rime-ice.svg README.txt LICENSE UPSTREAM.json THEME_UPSTREAM.json LICENSES/rime-color-scheme.txt; do
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
  if [[ ! -f "$theme/LICENSE" ]]; then
    printf 'Theme is missing attribution LICENSE: %s\n' "$theme" >&2
    exit 1
  fi
  python3 "$PROJECT_ROOT/packaging/copy_data.py" "$theme" "$STAGE/usr/share/fcitx5/themes/$(basename -- "$theme")"
  ((theme_count += 1))
done
if (( theme_count == 0 )); then
  printf 'No rime-ice-* theme directory found.\n' >&2
  exit 1
fi

install -m 0644 "$PROJECT_ROOT/data/rime-ice.svg" "$STAGE/usr/share/icons/hicolor/scalable/apps/rime-ice.svg"
install -m 0644 "$PROJECT_ROOT/README.txt" "$STAGE/usr/share/doc/$PACKAGE/README"
install -m 0644 "$PROJECT_ROOT/LICENSE" "$STAGE/usr/share/doc/$PACKAGE/copyright"
install -m 0644 "$PROJECT_ROOT/UPSTREAM.json" "$STAGE/usr/share/doc/$PACKAGE/UPSTREAM.json"
install -m 0644 "$PROJECT_ROOT/THEME_UPSTREAM.json" "$STAGE/usr/share/doc/$PACKAGE/THEME_UPSTREAM.json"
mkdir -p "$STAGE/usr/share/doc/$PACKAGE/LICENSES"
cp -a "$PROJECT_ROOT/LICENSES/." "$STAGE/usr/share/doc/$PACKAGE/LICENSES/"
install -m 0644 "$PROJECT_ROOT/packaging/rime-ice.desktop" "$STAGE/usr/share/applications/rime-ice.desktop"
install -m 0755 "$PROJECT_ROOT/packaging/rime-ice" "$STAGE/usr/bin/rime-ice"
install -m 0755 "$PROJECT_ROOT/packaging/rime-ice-settings" "$STAGE/usr/bin/rime-ice-settings"
install -m 0644 "$CONTROL" "$STAGE/DEBIAN/control"

# Keep the old package as a file-free transitional shell. The new primary
# package owns the compatibility launcher through its Replaces relationship.
mkdir -p "$COMPAT_STAGE/DEBIAN"
install -m 0644 "$COMPAT_CONTROL" "$COMPAT_STAGE/DEBIAN/control"

find "$STAGE" -type d -exec chmod 0755 {} +
find "$STAGE" -type f -exec chmod 0644 {} +
chmod 0755 "$STAGE/usr/bin/rime-ice" "$STAGE/usr/bin/rime-ice-settings"
find "$COMPAT_STAGE" -type d -exec chmod 0755 {} +
find "$COMPAT_STAGE" -type f -exec chmod 0644 {} +

mkdir -p "$OUTPUT_DIR"
dpkg-deb --build --root-owner-group "$STAGE" "$OUTPUT_DIR/${PACKAGE}_${VERSION}_all.deb"
dpkg-deb --build --root-owner-group "$COMPAT_STAGE" "$OUTPUT_DIR/${COMPAT_PACKAGE}_${VERSION}_all.deb"
