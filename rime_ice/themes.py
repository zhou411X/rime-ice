# SPDX-License-Identifier: GPL-3.0-only
"""Fcitx5 RGB palettes; brand colors adapted from xxd's MIT-licensed schemes.

Reference: nevertoday/rime-color-scheme, f050083a029babb2e0653fef84ef85e3869ba6aa.
The MIT notice is shipped in every adapted theme directory and LICENSES/.
"""

# Tuple order: display name, background, foreground, selected text, selected fill.
THEMES = {
    "rime-ice-jade": ("青玉 · 浅色", "#ffffff", "#28353a", "#387b68", "#e7f1ed"),
    "rime-ice-night": ("墨夜 · 深色", "#242b32", "#e7eeeb", "#b8d6c9", "#3b5149"),
    "rime-ice-solarized-light": ("Solarized Light", "#fdf6e3", "#657b83", "#268bd2", "#eee8d5"),
    "rime-ice-solarized-dark": ("Solarized Dark", "#002b36", "#93a1a1", "#2aa198", "#073642"),
}

# Selected fills remain the exact requested RGB values in both variants.
# Source values are BGR; the values below have been converted to Fcitx5 RGB.
BRAND_PALETTES = {
    "tiffany": ("蒂芙尼蓝", "#81D8D0", "#0A7680", "#EDE8E2", "#2E3D3C", "#121A1A", "#E7E9E9"),
    "hermes": ("爱马仕橙", "#F37021", "#FFFFFF", "#F4EEE6", "#3D342E", "#1A120C", "#E9E8E7"),
    "klein": ("克莱因蓝", "#002FA7", "#FFFFFF", "#F1F3F7", "#2E323D", "#14110E", "#E7E8E9"),
    "coke": ("可口可乐红", "#F40009", "#FFFFFF", "#F7F3EC", "#3D2E2F", "#1C0C0E", "#E9E7E7"),
    "ikea-blue": ("宜家蓝", "#0058A3", "#FFFFFF", "#F2F5F8", "#2E363D", "#14110E", "#E7E8E9"),
    "ikea-yellow": ("宜家黄", "#FFDA1A", "#0058A3", "#1A3F6B", "#E7E7E4", "#1C1A10", "#E9E9E7"),
    "classic-blue": ("经典蓝", "#0F4C81", "#FFFFFF", "#F1F4F7", "#2E363D", "#14110E", "#E7E8E9"),
    "peri": ("长春花蓝", "#6667AB", "#FFFFFF", "#F3F3F8", "#2E2E3D", "#12121A", "#E7E7E9"),
    "royal": ("皇家蓝", "#4169E1", "#FFFFFF", "#F3F3F5", "#2E323D", "#10121C", "#E7E8E9"),
    "chartreuse": ("酸橙绿", "#DFFF00", "#5B6515", "#3E4128", "#E7E7E4", "#10120A", "#E9E9E7"),
    "millennial": ("千禧粉", "#F3C6C8", "#783639", "#F6F1EE", "#3D2E2F", "#1A1415", "#E9E7E7"),
}
THEME_PAIRS = {
    "rime-ice-jade": "rime-ice-night",
    "rime-ice-solarized-light": "rime-ice-solarized-dark",
}
for slug, (title, accent, selected, light_bg, light_fg, dark_bg, dark_fg) in BRAND_PALETTES.items():
    light = "rime-ice-" + slug
    dark = light + "-night"
    THEMES[light] = (title + " · 浅色", light_bg, light_fg, selected, accent)
    THEMES[dark] = (title + " · 夜色", dark_bg, dark_fg, selected, accent)
    THEME_PAIRS[light] = dark

DARK_THEMES = frozenset(THEME_PAIRS.values())
