# SPDX-License-Identifier: GPL-3.0-only
"""Exercise native widgets on an isolated home; never touch a real input method."""
import os
from pathlib import Path
import tempfile
import traceback
import time

from gi.repository import GLib
from rime_ice.app import Application, SettingsWindow
from rime_ice.model import Store, DeploymentError
from rime_ice.themes import BRAND_PALETTES, THEME_PAIRS, THEMES
from gi.repository import Adw

tmp = tempfile.TemporaryDirectory()
home = Path(tmp.name)
store = Store(home, Path(__file__).resolve().parents[1] / "data")
app = Application()
app.register(None)
window = SettingsWindow(app, store)
window.present()
loop = GLib.MainLoop()
failure = []


def exercise():
    try:
        for page in ("general", "appearance", "shortcuts", "dictionary", "backup", "installation"):
            window.stack.set_visible_child_name(page)
            assert window.stack.get_visible_child_name() == page
        window.stack.set_visible_child_name("appearance")
        window.select_theme("rime-ice-solarized-light")
        window.widgets["vertical"].set_active(True)
        window.widgets["page_size"].set_value(7)
        assert window.values["theme"] == "rime-ice-solarized-light"
        assert window.values["vertical"] is True
        assert window.values["page_size"] == 7
        assert window.dirty
        window.select_theme("rime-ice-jade")
        window.widgets["vertical"].set_active(False)
        window.widgets["page_size"].set_value(9)
        window.search.set_text("不存在")
        window.render_phrases()
        window.rebuild()
        assert window.values["page_size"] == 9
        assert not window.dirty
        assert not store.rime.exists(), "GUI must not create user settings on startup"
        window.select_theme("rime-ice-jade")
        expected = dict(window.values)
        for fail in (False, True):
            window.error = lambda error: None
            def redeploy():
                if fail:
                    raise DeploymentError("simulated unavailable input method")
                return "reloaded"
            window.run_work(redeploy, "Test pure redeploy")
            deadline = time.monotonic() + 5
            while window.busy and time.monotonic() < deadline:
                GLib.MainContext.default().iteration(False)
                time.sleep(.01)
            assert not window.busy
            assert window.dirty, "Pure redeploy must preserve pending edits"
            assert window.values == expected
        print("GUI: redeploy success/failure preserve pending edits: PASS")
        print("GUI: 6 pages, theme, layout, candidate count, search, reload, no startup writes: PASS")
        window.rebuild()
        window.set_theme_variant("dark")
        assert not window.dirty, "Browsing night colors must not modify settings"
        assert sum(w.get_parent().get_visible() for w in window.theme_buttons.values()) == 13
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        for slug in BRAND_PALETTES:
            light = "rime-ice-" + slug
            dark = THEME_PAIRS[light]
            window.select_theme(light)
            assert window.values["theme"] == light
            assert window.values["dark_theme"] == dark
            dropdown = window.widgets["dark_theme"]
            assert window.choice_keys["dark_theme"][dropdown.get_selected()] == dark
            window.widgets["follow"].set_active(True)
            window.toggle_mode()
            assert THEMES[dark][0] in window.preview_caption.get_text()
            window.toggle_mode()
            assert THEMES[light][0] in window.preview_caption.get_text()
            window.select_theme(dark)
            assert window.theme_variant == "dark"
            assert window.values["theme"] == dark
        print("GUI: 11 palette pairs, day/night browser, dropdown pairing and dark previews: PASS")
        window.select_theme("rime-ice-tiffany")
        window.widgets["page_size"].set_value(5)
        window.status.set_text("蒂芙尼蓝 · 浅色与夜色已配对 · 应用设置后生效")
        GLib.timeout_add(400, capture)
    except Exception:
        failure.append(traceback.format_exc())
        loop.quit()
    return GLib.SOURCE_REMOVE


def capture():
    try:
        # Use the GTK rendering API directly to export the actual native window.
        import ctypes
        gtk = ctypes.CDLL("libgtk-4.so.1")
        gobject = ctypes.CDLL("libgobject-2.0.so.0")
        def fn(name, restype, *args):
            f = getattr(gtk, name)
            f.restype = restype
            f.argtypes = args
            return f
        p = ctypes.c_void_p
        paintable = fn("gtk_widget_paintable_new", p, p)(hash(window))
        snapshot = fn("gtk_snapshot_new", p)()
        fn("gdk_paintable_snapshot", None, p, p, ctypes.c_double, ctypes.c_double)(paintable, snapshot, window.get_width(), window.get_height())
        node = fn("gtk_snapshot_free_to_node", p, p)(snapshot)
        renderer = fn("gtk_native_get_renderer", p, p)(hash(window))
        texture = fn("gsk_renderer_render_texture", p, p, p, p)(renderer, node, None)
        output = Path(__file__).resolve().parents[1] / "dist/settings-preview-0.2.0.png"
        output.parent.mkdir(exist_ok=True)
        result = fn("gdk_texture_save_to_png", ctypes.c_int, p, ctypes.c_char_p)(texture, str(output).encode())
        assert result
        print("Native screenshot:", output)
        gobject.g_object_unref.argtypes = [p]
        gobject.g_object_unref(texture)
        gobject.g_object_unref(paintable)
        fn("gsk_render_node_unref", None, p)(node)
    except Exception:
        failure.append(traceback.format_exc())
    finally:
        window.destroy()
        loop.quit()
    return GLib.SOURCE_REMOVE


GLib.timeout_add(500, exercise)
GLib.timeout_add_seconds(20, lambda: (failure.append("GUI timeout"), loop.quit(), False)[-1])
loop.run()
tmp.cleanup()
if failure:
    raise RuntimeError("\n".join(failure))
