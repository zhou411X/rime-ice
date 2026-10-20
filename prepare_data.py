#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build distributable data from a pinned PUBLIC upstream archive, never HOME."""
import hashlib
import json
from pathlib import Path
import struct
import tarfile
import zlib

ROOT = Path(__file__).resolve().parent
SHA = "da1fbe602e38f26db846fa10120ee64c2b0324c0"
ARCHIVE = Path("/tmp/rime-ice-public-source.tar.gz")
DATA = ROOT / "data"
SOURCE = ROOT / "upstream"


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


def main():
    SOURCE.mkdir(exist_ok=True)
    data = DATA / "rime"
    data.mkdir(parents=True, exist_ok=True)
    public_dirs = {"cn_dicts", "en_dicts", "lua", "opencc"}
    with tarfile.open(ARCHIVE) as archive:
        for member in archive.getmembers():
            parts = Path(member.name).parts
            if len(parts) < 2 or not member.isfile():
                continue
            relative = Path(*parts[1:])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Invalid upstream archive path")
            content = archive.extractfile(member).read()
            target = SOURCE / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            if relative.parts[0] in public_dirs or (len(relative.parts)==1 and (relative.name.endswith((".yaml", ".txt")) or relative.name.startswith("LICENSE"))):
                if relative.name in {"custom_phrase.txt", "squirrel.yaml", "weasel.yaml"}:
                    continue
                target = data / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
    (data / "custom_phrase.txt").write_text("# 自定义短语：词条<TAB>编码<TAB>权重\n", encoding="utf-8")
    (data / "default.custom.yaml").write_text("patch:\n  schema_list:\n    - schema: rime_ice\n  menu/page_size: 9\n  ascii_composer/switch_key/Shift_L: commit_code\n", encoding="utf-8")
    (data / "rime_ice.custom.yaml").write_text("patch:\n  menu/page_size: 9\n  translator/enable_user_dict: true\n  translator/enable_encoder: true\n  translator/encode_commit_history: true\n  melt_eng/enable_user_dict: false\n", encoding="utf-8")
    (data / "lua/rime_ice_settings_filter.lua").write_text('''-- SPDX-License-Identifier: GPL-3.0-only
-- Rime Ice Settings: explicitly configured second candidate.
local M = {}
function M.init(env)
  env.targets = {}
  local items = env.engine.schema.config:get_list("rime_ice_settings_filter")
  if items then
    for i = 0, items.size - 1 do
      local code, text = items:get_value_at(i).value:match("([^\\t]+)\\t(.+)")
      if code and text then env.targets[code:gsub(" ", "")] = text end
    end
  end
end
function M.func(input, env)
  local target = env.targets[env.engine.context.input:gsub(" ", "")]
  if not target then
    for cand in input:iter() do yield(cand) end
    return
  end
  local emitted, selected = false, nil
  for cand in input:iter() do
    if cand.text == target then
      selected = cand
    elseif not emitted then
      yield(cand)
      yield(Candidate("custom", cand.start, cand._end, target, ""))
      emitted = true
    else
      yield(cand)
    end
  end
  if not emitted and selected then yield(selected) end
end
return M
''', encoding="utf-8")
    from rime_ice.model import THEMES
    for name, (title, bg, fg, active, highlight) in THEMES.items():
        target = DATA / "themes" / name
        target.mkdir(parents=True, exist_ok=True)
        png(target / "background.png", bg, highlight, 11)
        png(target / "highlight.png", highlight, highlight, 7)
        (target / "theme.conf").write_text(f'''[Metadata]
Name={title}
Version=1
Author=Rime Ice Settings contributors
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
    (DATA / "rime-ice.svg").write_text('''<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128"><rect x="8" y="8" width="112" height="112" rx="28" fill="#387b68"/><path d="M32 38h64M43 51h42M30 65h68M40 80h48M48 94h32" fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round"/></svg>''')
    (ROOT / "UPSTREAM.json").write_text(json.dumps({"repository":"https://github.com/iDvel/rime-ice", "commit":SHA,"archive_sha256":hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),"policy":"Public upstream only. Excludes local personal phrases, learned dictionaries, sync state and installation identifiers."}, indent=2)+"\n")
    license_path = next(SOURCE.glob("LICENSE*"))
    (ROOT / "LICENSE").write_bytes(license_path.read_bytes())
    print("Public dictionary, four themes, and provenance prepared.")


if __name__ == "__main__":
    main()
