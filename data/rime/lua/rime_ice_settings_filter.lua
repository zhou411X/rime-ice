-- SPDX-License-Identifier: GPL-3.0-only
-- Rime Ice Settings: explicitly configured second candidate.
local M = {}
function M.init(env)
  env.targets = {}
  local items = env.engine.schema.config:get_list("rime_ice_settings_filter")
  if items then
    for i = 0, items.size - 1 do
      local code, text = items:get_value_at(i).value:match("([^\t]+)\t(.+)")
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
