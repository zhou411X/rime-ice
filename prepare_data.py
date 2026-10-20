#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build distributable data from a pinned PUBLIC upstream archive, never HOME."""
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parent
SHA = "da1fbe602e38f26db846fa10120ee64c2b0324c0"
ARCHIVE = Path("/tmp/rime-ice-public-source.tar.gz")
DATA = ROOT / "data"
SOURCE = ROOT / "upstream"



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
    from prepare_themes import write_themes
    write_themes(DATA / "themes")
    (DATA / "rime-ice.svg").write_text('''<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128"><rect x="8" y="8" width="112" height="112" rx="28" fill="#387b68"/><path d="M32 38h64M43 51h42M30 65h68M40 80h48M48 94h32" fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round"/></svg>''')
    (ROOT / "UPSTREAM.json").write_text(json.dumps({"repository":"https://github.com/iDvel/rime-ice", "commit":SHA,"archive_sha256":hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),"policy":"Public upstream only. Excludes local personal phrases, learned dictionaries, sync state and installation identifiers."}, indent=2)+"\n")
    license_path = next(SOURCE.glob("LICENSE*"))
    (ROOT / "LICENSE").write_bytes(license_path.read_bytes())
    print("Public dictionary, four themes, and provenance prepared.")


if __name__ == "__main__":
    main()
