# SPDX-License-Identifier: GPL-3.0-only
"""Integration with an isolated Fcitx5 process and real Rime deployment."""
from pathlib import Path
import copy
import os
import shutil
import subprocess
import tempfile
import time

from rime_ice.model import Store, load_yaml, reload_input_method

project = Path(__file__).resolve().parents[1]
root = Path(tempfile.mkdtemp(prefix="rime-ice-engine-"))
store = Store(root, project / "data")
existing = Path((project / "dist/deploy-path.txt").read_text()) / "user"
shutil.copytree(existing, store.rime)
shutil.copytree(project / "data/themes", store.data / "fcitx5/themes")
(store.config / "fcitx5").mkdir(parents=True)
(store.config / "fcitx5/profile").write_text("[Groups/0]\nName=Default\nDefault Layout=us\nDefaultIM=rime\n[Groups/0/Items/0]\nName=keyboard-us\nLayout=\n[Groups/0/Items/1]\nName=rime\nLayout=\n[GroupOrder]\n0=Default\n")
runtime = root / "runtime"
runtime.mkdir(mode=0o700)
environment = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(store.config), XDG_DATA_HOME=str(store.data), XDG_STATE_HOME=str(store.state_dir), XDG_RUNTIME_DIR=str(runtime))
command = ["gdbus", "call", "--session", "--dest", "org.fcitx.Fcitx5", "--object-path", "/controller", "--method", "org.fcitx.Fcitx.Controller1.State"]
log_path = project / "dist/engine-integration.log"
with log_path.open("w") as log:
    process = subprocess.Popen(["fcitx5", "--disable=wayland"], env=environment, stdout=log, stderr=log)
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError("Fcitx exited: " + log_path.read_text()[-2000:])
            if subprocess.run(command, capture_output=True).returncode == 0:
                break
            time.sleep(.1)
        else:
            raise RuntimeError("Fcitx D-Bus startup timed out")
        store.load()
        settings = copy.deepcopy(store.settings)
        settings.update(page_size=7, theme="rime-ice-tiffany", dark_theme="rime-ice-tiffany-night", follow=True, vertical=True)
        entries = [{"text":"测试词条", "code":"csct", "weight":100, "second":True}]
        backup = store.apply(settings, entries)
        print(reload_input_method())
        built = store.rime / "build/rime_ice.schema.yaml"
        for _ in range(300):
            try:
                schema = load_yaml(built.read_text())
                if schema.get("menu", {}).get("page_size") == 7 and schema.get("rime_ice_settings_filter") == ["csct\t测试词条"]:
                    assert "lua_filter@*rime_ice_settings_filter" in schema["engine"]["filters"]
                    break
            except (OSError, ValueError):
                pass
            time.sleep(.1)
        else:
            raise RuntimeError("Rime did not compile changed configuration: " + log_path.read_text()[-4000:])
        print("ENGINE: isolated Fcitx5 start, atomic save, D-Bus reload/deploy, 7 candidates, custom filter compiled: PASS")
        classic_config = subprocess.check_output(["gdbus", "call", "--session", "--dest", "org.fcitx.Fcitx5", "--object-path", "/controller", "--method", "org.fcitx.Fcitx.Controller1.GetConfig", "fcitx://config/addon/classicui"], text=True)
        assert "rime-ice-tiffany-night" in classic_config and "rime-ice-tiffany" in classic_config
        print("ENGINE: Classic UI reports selected Tiffany light/night themes: PASS")
        store.restore(backup)
        print(reload_input_method())
        print("ENGINE: automatic backup restoration: PASS")
    finally:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
print("Integration fixture:", root)
