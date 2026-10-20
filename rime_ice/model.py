# SPDX-License-Identifier: GPL-3.0-only
"""Configuration, portable phrase dictionaries, and recoverable local changes."""
from __future__ import annotations

import base64
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid

import yaml

from .themes import THEMES

SHIFT_ACTIONS = {"commit_code": "提交字母并切换英文", "commit_text": "提交候选并切换英文", "clear": "清空拼音并切换英文", "noop": "不使用左 Shift 切换", "inline_ascii": "临时英文模式"}
FILTER = "lua_filter@*rime_ice_settings_filter"


class ConfigError(ValueError):
    pass


class DeploymentError(ConfigError):
    """The on-disk save succeeded, but the running engine did not reload."""
    pass


class UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    loader.flatten_mapping(node)
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ConfigError(f"配置包含重复键：{key}，请先修正后重试。")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_yaml(text):
    # Rime/yaml-cpp accepts TAB-separated plain list scalars used by candidate
    # filters. PyYAML rejects those; quote this precise text form on read only.
    text = re.sub(r"^( *)(- )([a-z][a-z '/]*\t[^\r\n#]+)$", lambda m: m[1] + m[2] + json.dumps(m[3], ensure_ascii=False), text, flags=re.MULTILINE)
    value = yaml.load(text, Loader=UniqueLoader) or {}
    if not isinstance(value, dict):
        raise ConfigError("YAML 顶层必须是映射。")
    return value


def yaml_bytes(value):
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode()


def ini_get(text, section, key, default=""):
    current = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current = stripped[1:-1]
        elif current == section and "=" in line and not stripped.startswith(("#", ";")):
            name, value = line.split("=", 1)
            if name.strip() == key:
                return value.strip().strip('"')
    return default


def ini_set(text, section, key, value):
    """Change only the requested INI key; keep comments and all other settings."""
    lines = text.splitlines()
    current, start, end = "", None, len(lines)
    if section == "":
        start = 0
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if start is not None and current == section:
                end = index
                break
            current = stripped[1:-1]
            if current == section:
                start = index + 1
        elif current == section and "=" in line and not stripped.startswith(("#", ";")):
            if line.split("=", 1)[0].strip() == key:
                lines[index] = f"{key}={value}"
                return "\n".join(lines) + "\n"
    if start is None:
        lines.extend(["", f"[{section}]", f"{key}={value}"])
    else:
        lines.insert(end, f"{key}={value}")
    return "\n".join(lines) + "\n"


def patch_get(document, path, default=None):
    patch = document.get("patch", {})
    if not isinstance(patch, dict):
        raise ConfigError("patch 必须是映射。")
    if path in patch:
        return patch[path]
    parts = path.split("/")
    for size in range(len(parts) - 1, 0, -1):
        prefix = "/".join(parts[:size])
        if prefix in patch:
            value = patch[prefix]
            for key in parts[size:]:
                if not isinstance(value, dict) or key not in value:
                    return default
                value = value[key]
            return value
    return default


def patch_set(document, path, value):
    patch = document.setdefault("patch", {})
    if not isinstance(patch, dict):
        raise ConfigError("patch 必须是映射。")
    parts = path.split("/")
    for size in range(len(parts) - 1, 0, -1):
        prefix = "/".join(parts[:size])
        if prefix in patch and isinstance(patch[prefix], dict):
            target = patch[prefix]
            for part in parts[size:-1]:
                target = target.setdefault(part, {})
                if not isinstance(target, dict):
                    raise ConfigError(f"无法安全修改 {path}，现有父节点不是映射。")
            target[parts[-1]] = value
            patch.pop(path, None)
            return
    patch[path] = value


def atomic_write(path, data, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".rime-ice-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def digest(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def parse_phrases(text):
    entries, comments = [], []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            comments.append(line)
            continue
        parts = line.split("\t")
        if len(parts) not in (2, 3) or not parts[0] or not parts[1]:
            raise ConfigError(f"第 {number} 行格式错误；需要 词条<TAB>编码<TAB>权重。")
        try:
            weight = int(parts[2]) if len(parts) == 3 else 100
        except ValueError as error:
            raise ConfigError(f"第 {number} 行权重必须为整数。") from error
        entries.append({"text": parts[0], "code": parts[1], "weight": weight, "second": False})
    validate_phrases(entries)
    return entries, comments


def validate_phrases(entries):
    seen, seconds = set(), set()
    if len(entries) > 100000:
        raise ConfigError("单次最多管理 100000 条自定义短语。")
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("text"), str) or not isinstance(entry.get("code"), str):
            raise ConfigError("词条与编码必须为文本。")
        if not entry["text"].strip() or any(c in entry["text"] for c in "\t\r\n\0"):
            raise ConfigError("词条不能为空或包含换行、制表符。")
        if not re.fullmatch(r"[a-z][a-z '/]*", entry["code"]):
            raise ConfigError("编码需为小写英文字母，可含空格、单引号或斜杠。")
        if type(entry.get("weight")) is not int or not 0 <= entry["weight"] <= 2147483647:
            raise ConfigError("权重必须为 0 到 2147483647 的整数。")
        key = (entry["text"], entry["code"])
        if key in seen:
            raise ConfigError(f"重复词条：{entry['text']} / {entry['code']}")
        seen.add(key)
        if entry.get("second"):
            if entry["code"] in seconds:
                raise ConfigError(f"同一编码只能固定一个第二候选：{entry['code']}")
            seconds.add(entry["code"])


def phrase_bytes(entries, comments=()):
    validate_phrases(entries)
    return ("\n".join(list(comments) + [f"{e['text']}\t{e['code']}\t{e['weight']}" for e in entries]) + "\n").encode()


def merge_phrases(existing, imported):
    merged = {(e["text"], e["code"]): copy.deepcopy(e) for e in existing}
    for entry in imported:
        merged.setdefault((entry["text"], entry["code"]), copy.deepcopy(entry))
    result = list(merged.values())
    validate_phrases(result)
    return result


class Store:
    def __init__(self, home=None, assets=None):
        self.home = Path(home or Path.home())
        explicit = home is not None
        self.config = self.home / ".config" if explicit else Path(os.environ.get("XDG_CONFIG_HOME", self.home / ".config"))
        self.data = self.home / ".local/share" if explicit else Path(os.environ.get("XDG_DATA_HOME", self.home / ".local/share"))
        self.state_dir = self.home / ".local/state" if explicit else Path(os.environ.get("XDG_STATE_HOME", self.home / ".local/state"))
        self.rime = self.data / "fcitx5/rime"
        self.assets = Path(assets or "/usr/share/rime-ice")
        self.backups = self.state_dir / "rime-ice/backups"
        self.snapshots = {}
        self.settings = {}
        self.phrases = []

    def read(self, path):
        path = Path(path)
        data = path.read_bytes() if path.exists() else None
        self.snapshots[path] = digest(data)
        return (data or b"").decode("utf-8-sig")

    def document(self, name):
        return load_yaml(self.read(self.rime / name))

    def load(self):
        self.snapshots = {}
        self.default = self.document("default.custom.yaml")
        self.schema = self.document("rime_ice.custom.yaml")
        self.fcitx = self.read(self.config / "fcitx5/config")
        self.classic = self.read(self.config / "fcitx5/conf/classicui.conf")
        self.read(self.rime / "lua/rime_ice_settings_filter.lua")
        raw, self.phrase_comments = parse_phrases(self.read(self.rime / "custom_phrase.txt"))
        seconds = patch_get(self.schema, "rime_ice_settings_filter", []) or []
        second_map = dict(item.split("\t", 1) for item in seconds)
        for entry in raw:
            entry["second"] = second_map.get(entry["code"]) == entry["text"]
        self.phrases = raw
        default_pages = patch_get(self.default, "menu/page_size", 9)
        self.settings = {
            "page_size": int(patch_get(self.schema, "menu/page_size", default_pages)),
            "learn": bool(patch_get(self.schema, "translator/enable_user_dict", True)),
            "english_learn": bool(patch_get(self.schema, "melt_eng/enable_user_dict", False)),
            "shift": patch_get(self.default, "ascii_composer/switch_key/Shift_L", "commit_code"),
            "vertical": ini_get(self.classic, "", "Vertical Candidate List", "False") == "True",
            "font": ini_get(self.classic, "", "Font", "Sans 10"),
            "theme": ini_get(self.classic, "", "Theme", "default"),
            "dark_theme": ini_get(self.classic, "", "DarkTheme", "default-dark"),
            "follow": ini_get(self.classic, "", "UseDarkTheme", "False") == "True",
            "trigger": ini_get(self.fcitx, "Hotkey/TriggerKeys", "0", "Control+space"),
        }
        self.original_settings = copy.deepcopy(self.settings)
        self.original_phrases = copy.deepcopy(self.phrases)
        return self.settings

    def validate(self, settings):
        if not 3 <= settings["page_size"] <= 9:
            raise ConfigError("每页候选数须在 3–9 之间。")
        if settings["shift"] not in SHIFT_ACTIONS:
            raise ConfigError("不支持的 Shift 行为。")
        if not re.fullmatch(r"(?:(?:Control|Alt|Shift|Super)\+)+(?:[A-Za-z0-9_]+)", settings["trigger"]):
            raise ConfigError("切换快捷键格式示例：Control+space、Control+Shift+space。")
        if not settings["font"].strip() or any(c in settings["font"] for c in '\n\r\0"'):
            raise ConfigError("字体名称无效。")
        for key in ("theme", "dark_theme"):
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", settings[key]):
                raise ConfigError("主题名称无效。")

    def prepare(self, settings, entries):
        self.validate(settings)
        validate_phrases(entries)
        default, schema = copy.deepcopy(self.default), copy.deepcopy(self.schema)
        fcitx, classic = self.fcitx, self.classic
        changes = {}
        modified = {key for key in settings if settings[key] != self.original_settings[key]}
        for key, value in (("page_size", "menu/page_size"), ("learn", "translator/enable_user_dict"), ("english_learn", "melt_eng/enable_user_dict")):
            if key in modified:
                patch_set(schema, value, settings[key])
        if "learn" in modified:
            patch_set(schema, "translator/enable_encoder", settings["learn"])
            patch_set(schema, "translator/encode_commit_history", settings["learn"])
        if "shift" in modified:
            patch_set(default, "ascii_composer/switch_key/Shift_L", settings["shift"])
        if "trigger" in modified:
            fcitx = ini_set(fcitx, "Hotkey/TriggerKeys", "0", settings["trigger"])
        keys = {"vertical": "Vertical Candidate List", "font": "Font", "theme": "Theme", "dark_theme": "DarkTheme", "follow": "UseDarkTheme"}
        for key, field in keys.items():
            if key in modified:
                value = settings[key]
                if isinstance(value, bool):
                    value = str(value)
                if key == "font":
                    value = '"' + value + '"'
                classic = ini_set(classic, "", field, value)
        if "theme" in modified or "dark_theme" in modified:
            classic = ini_set(classic, "", "UseAccentColor", "False")
        if entries != self.original_phrases:
            changes[self.rime / "custom_phrase.txt"] = phrase_bytes(entries, self.phrase_comments)
            patch_set(schema, "rime_ice_settings_filter", [e["code"] + "\t" + e["text"] for e in entries if e.get("second")])
            # Use Rime's list append patch without replacing existing filters.
            filters = schema.setdefault("patch", {}).get("engine/filters/+", [])
            if not isinstance(filters, list):
                raise ConfigError("现有 engine/filters/+ 不是列表，请先检查自定义配置。")
            if FILTER not in filters:
                schema["patch"]["engine/filters/+"] = filters + [FILTER]
            changes[self.rime / "lua/rime_ice_settings_filter.lua"] = (self.assets / "rime/lua/rime_ice_settings_filter.lua").read_bytes()
        for path, value, original in ((self.rime / "default.custom.yaml", default, self.default), (self.rime / "rime_ice.custom.yaml", schema, self.schema)):
            if value != original:
                changes[path] = yaml_bytes(value)
        if fcitx != self.fcitx:
            changes[self.config / "fcitx5/config"] = fcitx.encode()
        if classic != self.classic:
            changes[self.config / "fcitx5/conf/classicui.conf"] = classic.encode()
        return changes

    def _portable(self, path):
        for prefix, base in (("config", self.config), ("data", self.data)):
            try:
                return prefix + "/" + str(path.relative_to(base))
            except ValueError:
                pass
        raise ConfigError("备份路径超出输入法配置范围。")

    def _resolve(self, name):
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or len(path.parts) < 3:
            raise ConfigError("备份包含非法路径。")
        if path.parts[0] not in ("config", "data") or path.parts[1] != "fcitx5":
            raise ConfigError("备份包含非输入法路径。")
        base = self.config if path.parts[0] == "config" else self.data
        target = base.joinpath(*path.parts[1:])
        if not target.resolve().is_relative_to((base / "fcitx5").resolve()):
            raise ConfigError("备份路径通过链接越出了输入法目录。")
        return target

    def commit(self, changes, label="应用设置"):
        if not changes:
            return None
        before = {}
        for path in changes:
            if path.is_symlink():
                raise ConfigError(f"配置文件是符号链接，请手动管理：{path}")
            content = path.read_bytes() if path.exists() else None
            if path in self.snapshots and digest(content) != self.snapshots[path]:
                raise ConfigError(f"文件已被其他程序修改，请重新加载：{path.name}")
            before[path] = content
        manifest = {"format": "rime-ice-backup-v1", "label": label, "files": {self._portable(p): base64.b64encode(b).decode() if b is not None else None for p, b in before.items()}}
        name = datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8] + ".json"
        backup = self.backups / name
        atomic_write(backup, json.dumps(manifest, ensure_ascii=False, indent=2).encode())
        written = []
        try:
            for path, content in changes.items():
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_write(path, content)
                written.append(path)
        except Exception:
            for path in reversed(written):
                if before[path] is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_write(path, before[path])
            raise
        return backup

    def apply(self, settings, entries):
        backup = self.commit(self.prepare(settings, entries))
        self.load()
        return backup

    def initialize(self):
        """Install public data only into a new user directory; never replace it."""
        source = self.assets / "rime"
        existing_install = (self.rime / "rime_ice.schema.yaml").exists()
        files = [p for p in source.rglob("*") if p.is_file()]
        if not files:
            raise ConfigError("安装包中的公开词典缺失。")
        changes = {}
        for path in files:
            target = self.rime / path.relative_to(source)
            if target.exists() and target.read_bytes() != path.read_bytes() and not existing_install:
                raise ConfigError(f"现有 Rime 文件与初始方案冲突：{target.name}。请先备份并用配置工具处理。")
            if not target.exists():
                changes[target] = path.read_bytes()
        classic = self.config / "fcitx5/conf/classicui.conf"
        if not classic.exists():
            changes[classic] = b'Vertical Candidate List=False\nFont="Noto Sans CJK SC 14"\nTheme=rime-ice-jade\nDarkTheme=rime-ice-night\nUseDarkTheme=True\nUseAccentColor=False\n'
        global_config = self.config / "fcitx5/config"
        if not global_config.exists():
            changes[global_config] = b'[Hotkey/TriggerKeys]\n0=Control+space\n\n[Hotkey/AltTriggerKeys]\n# Left Shift is managed by Rime.\n'
        backup = self.commit(changes, "首次部署公开输入方案")
        self.load()
        return backup

    def restore(self, backup):
        path = Path(backup)
        if path.stat().st_size > 128 * 1024 * 1024:
            raise ConfigError("备份文件过大。")
        document = json.loads(path.read_text())
        if document.get("format") != "rime-ice-backup-v1" or not isinstance(document.get("files"), dict):
            raise ConfigError("不是 Rime Ice 配置备份。")
        changes = {}
        allowed = {
            self.rime / "default.custom.yaml", self.rime / "rime_ice.custom.yaml",
            self.rime / "custom_phrase.txt", self.rime / "lua/rime_ice_settings_filter.lua",
            self.config / "fcitx5/config", self.config / "fcitx5/conf/classicui.conf",
        }
        for name, value in document["files"].items():
            target = self._resolve(name)
            if target not in allowed:
                raise ConfigError("备份包含设置中心管理范围之外的文件：" + name)
            own_filter = target == self.rime / "lua/rime_ice_settings_filter.lua"
            changes[target] = base64.b64decode(value, validate=True) if value is not None else None
            if own_filter and changes[target] is not None and changes[target] != (self.assets / "rime/lua/rime_ice_settings_filter.lua").read_bytes():
                raise ConfigError("备份中的扩展脚本与安装版本不同，请手动检查。")
        for target, data in changes.items():
            if data is not None and target.suffix == ".yaml":
                load_yaml(data.decode())
            if data is not None and target.name == "custom_phrase.txt":
                parse_phrases(data.decode("utf-8-sig"))
        restored_schema = changes.get(self.rime / "rime_ice.custom.yaml")
        if restored_schema and "rime_ice_settings_filter" in restored_schema.decode():
            # Portable backups carry data, not executable code. Supply our own
            # installed implementation when restoring its settings on a new user.
            changes[self.rime / "lua/rime_ice_settings_filter.lua"] = (self.assets / "rime/lua/rime_ice_settings_filter.lua").read_bytes()
        # Validate the complete prospective state before touching live files.
        with tempfile.TemporaryDirectory(prefix="rime-ice-restore-check-") as directory:
            validator = Store(Path(directory), self.assets)
            for target in allowed:
                content = changes.get(target, target.read_bytes() if target.exists() else None)
                if content is not None:
                    atomic_write(validator._resolve(self._portable(target)), content)
            try:
                validator.load()
                validator.validate(validator.settings)
            except (ValueError, TypeError, AttributeError) as error:
                raise ConfigError("备份中的设置内容无效：" + str(error)) from error
        result = self.commit(changes, "恢复备份前的状态")
        self.load()
        return result

    def export_backup(self, path):
        names = [self.rime / n for n in ("default.custom.yaml", "rime_ice.custom.yaml", "custom_phrase.txt")]
        names += [self.config / "fcitx5/config", self.config / "fcitx5/conf/classicui.conf"]
        files = {self._portable(p): base64.b64encode(p.read_bytes()).decode() for p in names if p.exists()}
        atomic_write(Path(path), json.dumps({"format": "rime-ice-backup-v1", "label": "个人配置与短语备份", "files": files}, ensure_ascii=False, indent=2).encode())


def reload_input_method():
    """Use the engine's supported asynchronous deploy entrypoint, not a second writer."""
    common = ["gdbus", "call", "--session", "--dest", "org.fcitx.Fcitx5", "--object-path", "/controller", "--method"]
    for method, args in (("ReloadConfig", []), ("ReloadAddonConfig", ["classicui"]), ("SetConfig", ["fcitx://config/addon/rime/deploy", "<@a{sv} {}>"])):
        result = subprocess.run(common + ["org.fcitx.Fcitx.Controller1." + method] + args, capture_output=True, text=True, timeout=15)
        if result.returncode:
            raise DeploymentError("重新部署请求失败：" + result.stderr.strip() + "。已写入磁盘的配置不受影响，可在“常用设置 → 重新部署”重试。")
    return "已请求重新部署；请等待输入法完成部署。"


def enable_input_method():
    """Enable through desktop-supported tools, without killing other IM daemons."""
    result = subprocess.run(["im-config", "-n", "fcitx5"], capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise ConfigError("启用失败：" + (result.stderr or result.stdout).strip())
    subprocess.Popen(["fcitx5-configtool"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return "已选择 Fcitx5。请在配置工具中添加 Rime，然后注销并重新登录。"
