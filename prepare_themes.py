#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-only
"""Regenerate only Fcitx5 themes; never rewrite dictionaries or user files."""
from pathlib import Path
import struct
import zlib

from rime_ice.themes import THEMES

ROOT = Path(__file__).resolve().parent
LEGACY_THEMES = {"rime-ice-jade", "rime-ice-night", "rime-ice-solarized-light", "rime-ice-solarized-dark"}

def png(path, fill, border, radius):
    def rgb(hex_color):
        return tuple(int(hex_color[i:i+2], 16) for i in (1, 3, 5))
    fg, edge = rgb(fill), rgb(border)
    size, scale = 40, 4
    def inside(x, y, inset=0):
        r = max(radius-inset, 0)
        near_x = min(max(x, inset+r), size-inset-r)
        near_y = min(max(y, inset+r), size-inset-r)
        return inset <= x <= size-inset and inset <= y <= size-inset and (x-near_x)**2+(y-near_y)**2 <= r*r
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            samples = []
            for sy in range(scale):
                for sx in range(scale):
                    xx, yy = x+(sx+.5)/scale, y+(sy+.5)/scale
                    if inside(xx, yy):
                        samples.append(fg if inside(xx, yy, 1) else edge)
            if samples:
                row.extend([round(sum(c[i] for c in samples)/len(samples)) for i in range(3)]+[round(255*len(samples)/(scale*scale))])
            else:
                row.extend([0,0,0,0])
        rows.append(bytes(row))
    def chunk(name, data):
        return struct.pack('!I', len(data))+name+data+struct.pack('!I', zlib.crc32(name+data)&0xffffffff)
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',size,size,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows)))+chunk(b'IEND',b''))


def write_themes(destination):
    for name, (title, bg, fg, active, highlight) in THEMES.items():
        target = destination / name
        target.mkdir(parents=True, exist_ok=True)
        png(target / "background.png", bg, highlight, 11)
        png(target / "highlight.png", highlight, highlight, 7)
        (target / "theme.conf").write_text(f'''[Metadata]
Name={title}
Version=1
Author=Rime Ice contributors
Description=Local Rime Ice candidate theme
ScaleWithDPI=True

[InputPanel]
NormalColor={fg}
HighlightCandidateColor={active}
HighlightColor={active}
HighlightBackgroundColor={highlight}
CandidateLabelColor={fg}
HighlightCandidateLabelColor={active}
CandidateCommentColor={fg}
HighlightCandidateCommentColor={active}
FullWidthHighlight=True
PageButtonAlignment=Last Candidate
LabelTextSizeFactor=75

[InputPanel/TextMargin]
Left=8
Right=8
Top=5
Bottom=5

[InputPanel/ContentMargin]
Left=10
Right=10
Top=9
Bottom=9

[InputPanel/Background]
Image=background.png

[InputPanel/Background/Margin]
Left=12
Right=12
Top=12
Bottom=12

[InputPanel/Highlight]
Image=highlight.png

[InputPanel/Highlight/Margin]
Left=8
Right=8
Top=8
Bottom=8

[Menu]
NormalColor={fg}
HighlightCandidateColor={active}

[Menu/Background]
Image=background.png

[Menu/Background/Margin]
Left=12
Right=12
Top=12
Bottom=12

[Menu/ContentMargin]
Left=10
Right=10
Top=10
Bottom=10

[Menu/TextMargin]
Left=8
Right=8
Top=5
Bottom=5

[Menu/Highlight]
Image=highlight.png

[Menu/Highlight/Margin]
Left=8
Right=8
Top=8
Bottom=8

[Menu/Separator]
Color={highlight}
''', encoding="utf-8")
        license_path = ROOT / ("LICENSE" if name in LEGACY_THEMES else "LICENSES/rime-color-scheme.txt")
        (target / "LICENSE").write_bytes(license_path.read_bytes())


if __name__ == "__main__":
    write_themes(ROOT / "data/themes")
