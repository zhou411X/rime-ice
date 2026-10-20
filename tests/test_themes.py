# SPDX-License-Identifier: GPL-3.0-only
"""Check requested RGB colors across selectable palettes, PNGs and saved config."""
import configparser
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from rime_ice.model import Store, ini_get
from rime_ice.themes import THEMES, THEME_PAIRS, DARK_THEMES

REQUESTED = {
    'tiffany': '#81D8D0', 'hermes': '#F37021', 'klein': '#002FA7',
    'coke': '#F40009', 'ikea-blue': '#0058A3', 'ikea-yellow': '#FFDA1A',
    'classic-blue': '#0F4C81', 'peri': '#6667AB', 'royal': '#4169E1',
    'chartreuse': '#DFFF00', 'millennial': '#F3C6C8',
}
ASSETS = Path(__file__).resolve().parents[1] / 'data'


def png_center(path):
    contents = path.read_bytes()
    assert contents[:8] == b'\x89PNG\r\n\x1a\n'
    offset, compressed = 8, b''
    while offset < len(contents):
        length = struct.unpack('!I', contents[offset:offset + 4])[0]
        kind = contents[offset + 4:offset + 8]
        value = contents[offset + 8:offset + 8 + length]
        if kind == b'IHDR':
            width, height, depth, color, _, _, interlace = struct.unpack('!2I5B', value)
            assert (depth, color, interlace) == (8, 6, 0)
        elif kind == b'IDAT':
            compressed += value
        offset += length + 12
    raw = zlib.decompress(compressed)
    row = (1 + width * 4) * (height // 2)
    assert raw[row] == 0
    center = raw[row + 1 + (width // 2) * 4:row + 5 + (width // 2) * 4]
    assert center[3] == 255
    return '#' + center[:3].hex().upper()


class ThemeTest(unittest.TestCase):
    def test_all_requested_colors_have_exact_rgb_day_and_night_assets(self):
        self.assertEqual(len(THEMES), 26)
        self.assertEqual(len(DARK_THEMES), 13)
        for slug, expected in REQUESTED.items():
            light = 'rime-ice-' + slug
            dark = light + '-night'
            self.assertEqual(THEME_PAIRS[light], dark)
            for name in (light, dark):
                with self.subTest(theme=name):
                    self.assertEqual(THEMES[name][4], expected)
                    path = ASSETS / 'themes' / name
                    config = configparser.ConfigParser()
                    config.read(path / 'theme.conf')
                    self.assertEqual(config['InputPanel']['HighlightBackgroundColor'], expected)
                    self.assertEqual(config['InputPanel']['HighlightCandidateColor'], THEMES[name][3])
                    self.assertEqual(png_center(path / 'highlight.png'), expected)
                    self.assertEqual(png_center(path / 'background.png'), THEMES[name][1])
                    self.assertIn('Copyright (c) 2026 xxd', (path / 'LICENSE').read_text())

    def test_selected_theme_pair_roundtrips_without_overwriting_other_settings(self):
        for slug in REQUESTED:
            with self.subTest(theme=slug), tempfile.TemporaryDirectory() as home:
                store = Store(Path(home), ASSETS)
                classic = store.config / 'fcitx5/conf/classicui.conf'
                classic.parent.mkdir(parents=True)
                classic.write_text('Theme=default\nDarkTheme=default-dark\nUseAccentColor=True\n[Other]\nKeep=yes\n')
                store.load()
                selected = dict(store.settings, theme='rime-ice-' + slug,
                                dark_theme='rime-ice-' + slug + '-night', follow=True)
                store.apply(selected, [])
                store.load()
                self.assertEqual(store.settings['theme'], selected['theme'])
                self.assertEqual(store.settings['dark_theme'], selected['dark_theme'])
                self.assertTrue(store.settings['follow'])
                self.assertEqual(ini_get(classic.read_text(), '', 'UseAccentColor'), 'False')
                self.assertEqual(ini_get(classic.read_text(), 'Other', 'Keep'), 'yes')

    def test_legacy_theme_ids_remain_available(self):
        for name in ('jade', 'night', 'solarized-light', 'solarized-dark'):
            self.assertIn('rime-ice-' + name, THEMES)


if __name__ == '__main__':
    unittest.main()
