# SPDX-License-Identifier: GPL-3.0-only
"""Native GTK4 preferences. No web service, account or network dependency."""
from __future__ import annotations

import copy
from pathlib import Path
import subprocess
import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango

from . import __version__
from .themes import DARK_THEMES, THEME_PAIRS
from .model import (Store, THEMES, SHIFT_ACTIONS, ConfigError, DeploymentError, atomic_write,
                    parse_phrases, phrase_bytes, merge_phrases, validate_phrases,
                    reload_input_method, enable_input_method)

CSS = b"""
window { background: @window_bg_color; }
.ice-sidebar { background: alpha(@window_fg_color, .035); padding: 16px 10px; }
.ice-sidebar row { border-radius: 10px; padding: 11px 12px; margin: 3px 0; }
.ice-sidebar row:selected { background: alpha(#387b68, .14); color: #387b68; }
.ice-brand { font-weight: 700; font-size: 18px; letter-spacing: .5px; }
.ice-logo { background: #387b68; color: white; border-radius: 11px; padding: 7px 11px; font-size: 19px; }
.ice-page-title { font-size: 27px; font-weight: 700; letter-spacing: -.5px; }
.ice-subtitle { opacity: .65; margin-top: 7px; margin-bottom: 22px; }
.ice-preview-stage { background: alpha(#387b68, .075); border-radius: 18px; padding: 22px; }
.ice-preview-caption { font-size: 11px; opacity: .65; letter-spacing: 1px; }
.ice-candidate { border-radius: 11px; padding: 13px; margin-top: 16px; }
.ice-code { font-size: 14px; margin-bottom: 9px; }
.ice-word { padding: 5px 8px; border-radius: 7px; }
.ice-theme { padding: 12px; border-radius: 12px; background: transparent; box-shadow: none; }
.ice-theme:checked { outline: 2px solid #387b68; outline-offset: -2px; }
switch:checked { background: #387b68; }
.ice-chip { border-radius: 7px; padding: 6px; margin-bottom: 4px; }
.ice-swatch-word { padding: 5px 4px; border-radius: 5px; font-size: 12px; }
.ice-theme-name { font-size: 12px; font-weight: 600; }
.ice-theme-hex { font-size: 11px; opacity: .65; }
.ice-footer { padding: 13px 22px; border-top: 1px solid alpha(@window_fg_color, .1); }
.ice-status { font-size: 12px; opacity: .7; }
button.suggested-action { background: #387b68; color: white; }
.ice-group { margin-top: 20px; }
.ice-phrase { padding: 12px; }
.ice-mini { font-size: 12px; opacity: .65; }
"""


def label(text, css=None, wrap=False):
    widget = Gtk.Label(label=text, xalign=0, wrap=wrap)
    if css:
        widget.add_css_class(css)
    return widget


def button(text, callback, primary=False, icon=None):
    widget = Gtk.Button(label=text)
    if icon:
        content = Gtk.Box(spacing=7)
        content.append(Gtk.Image.new_from_icon_name(icon))
        content.append(Gtk.Label(label=text))
        widget.set_child(content)
    if primary:
        widget.add_css_class("suggested-action")
    widget.connect("clicked", lambda _: callback())
    return widget


class SettingsWindow(Adw.ApplicationWindow):
    def __init__(self, application, store=None):
        super().__init__(application=application, title="Rime Ice · 雾凇输入法")
        self.set_default_size(1060, 800)
        self.set_size_request(760, 560)
        self.store = store or Store()
        self.store.load()
        self.values = copy.deepcopy(self.store.settings)
        self.entries = copy.deepcopy(self.store.phrases)
        self.busy = False
        self.loading = True
        self.dirty = False
        self.widgets = {}
        self.choice_keys = {}
        self.theme_variant = "dark" if self.values["theme"] in DARK_THEMES else "light"
        self.provider = Gtk.CssProvider()
        self.provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(self.get_display(), self.provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.preview_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(self.get_display(), self.preview_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        self.connect("close-request", self.on_close)
        self.build()
        self.loading = False
        self.update_preview()

    def build(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(outer)
        header = Adw.HeaderBar()
        brand = Gtk.Box(spacing=10, valign=Gtk.Align.CENTER)
        brand.append(label("雾", "ice-logo"))
        brand.append(label("雾凇输入法", "ice-brand"))
        header.set_title_widget(brand)
        mode = button("明 / 暗", self.toggle_mode, icon="weather-clear-night-symbolic")
        mode.set_tooltip_text("切换设置窗口外观；候选框主题在下方单独设置")
        header.pack_end(mode)
        outer.append(header)
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, vexpand=True)
        outer.append(body)
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, width_request=185)
        sidebar.add_css_class("ice-sidebar")
        body.append(sidebar)
        nav = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        nav.add_css_class("navigation-sidebar")
        sidebar.append(nav)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, hexpand=True, vexpand=True)
        body.append(self.stack)
        pages = [("general", "常用设置", "preferences-system-symbolic", self.general),
                 ("appearance", "外观与候选框", "applications-graphics-symbolic", self.appearance),
                 ("shortcuts", "快捷键", "input-keyboard-symbolic", self.shortcuts),
                 ("dictionary", "个人词库", "accessories-dictionary-symbolic", self.dictionary),
                 ("backup", "数据与备份", "document-save-symbolic", self.backup),
                 ("installation", "安装与依赖", "package-x-generic-symbolic", self.installation)]
        for name, title, icon, factory in pages:
            row = Gtk.ListBoxRow()
            row.page_name = name
            line = Gtk.Box(spacing=10)
            line.append(Gtk.Image.new_from_icon_name(icon))
            line.append(label(title))
            row.set_child(line)
            nav.append(row)
            scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
            container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            for edge in ("top", "bottom", "start", "end"):
                getattr(container, "set_margin_" + edge)(28)
            scroller.set_child(container)
            factory(container)
            self.stack.add_named(scroller, name)
        nav.connect("row-selected", lambda _, row: self.stack.set_visible_child_name(row.page_name) if row else None)
        nav.select_row(nav.get_row_at_index(1))
        spacer = Gtk.Box(vexpand=True)
        sidebar.append(spacer)
        sidefoot = label("让输入，刚刚好。\n\nRime Ice  " + __version__ + "\nUbuntu 24.04 · 本地优先", "ice-mini")
        sidefoot.set_margin_start(12)
        sidefoot.set_margin_bottom(12)
        sidebar.append(sidefoot)
        footer = Gtk.Box(spacing=12)
        footer.add_css_class("ice-footer")
        outer.append(footer)
        self.status = label("已读取本机配置 · 保存前自动备份", "ice-status", True)
        self.status.set_hexpand(True)
        footer.append(self.status)
        footer.append(button("重新加载", self.confirm_reload))
        self.apply_button = button("应用设置", self.save, True)
        footer.append(self.apply_button)

    def title(self, box, title, subtitle):
        box.append(label(title, "ice-page-title"))
        box.append(label(subtitle, "ice-subtitle", True))

    def group(self, box, title, description=None):
        group = Adw.PreferencesGroup(title=title)
        if description:
            group.set_description(description)
        group.add_css_class("ice-group")
        box.append(group)
        return group

    def row(self, group, title, subtitle=None, widget=None):
        row = Adw.ActionRow(title=title)
        if subtitle:
            row.set_subtitle(subtitle)
        if widget:
            widget.set_valign(Gtk.Align.CENTER)
            row.add_suffix(widget)
            if isinstance(widget, Gtk.Switch):
                row.set_activatable_widget(widget)
        group.add(row)
        return row

    def switch(self, group, key, title, subtitle=None):
        widget = Gtk.Switch(active=self.values[key])
        widget.connect("notify::active", lambda w, _: self.change(key, w.get_active()))
        self.widgets[key] = widget
        self.row(group, title, subtitle, widget)

    def dropdown(self, group, key, title, choices, subtitle=None):
        names = list(choices)
        if self.values[key] not in names:
            choices = dict(choices)
            choices[self.values[key]] = "保留当前：" + str(self.values[key])
            names = list(choices)
        widget = Gtk.DropDown.new_from_strings([choices[n] for n in names])
        widget.set_selected(names.index(self.values[key]))
        widget.connect("notify::selected", lambda w, _: self.change(key, names[w.get_selected()]))
        self.widgets[key] = widget
        self.choice_keys[key] = names
        self.row(group, title, subtitle, widget)

    def change(self, key, value):
        self.values[key] = value
        if not self.loading:
            self.dirty = True
            self.status.set_text("有未保存的修改 · 应用前会自动备份")
            self.update_preview()

    def general(self, box):
        self.title(box, "常用设置", "把熟悉的输入习惯，留在指尖。")
        group = self.group(box, "输入方案")
        self.row(group, "雾凇拼音 · 全拼", "本页管理全拼方案；其他方案可在系统配置工具中选择。", button("配置工具", self.open_config))
        self.row(group, "首次启用", "部署公开词典，并引导将 Rime 添加到 Fcitx5。", button("启用输入法", self.confirm_enable, True))
        self.row(group, "重新部署", "保存成功但输入法未加载时，可在这里重试。", button("重新部署", lambda: self.run_work(reload_input_method, "正在请求重新部署…")))
        group = self.group(box, "词库学习")
        self.switch(group, "learn", "学习中文词汇", "按输入习惯调整词频，学习记录仅保存在本机。")
        self.switch(group, "english_learn", "学习英文词汇", "开启英文用户词典；不影响公开英文词库。")
        group = self.group(box, "输入状态")
        self.row(group, "简繁、全半角与 Emoji", "在输入时按 F4 打开 Rime 方案选单切换；保留现有快捷键。")
        self.row(group, "默认不使用云候选", "核心输入、主题、词库和备份均可离线使用。")

    def appearance(self, box):
        self.title(box, "外观与候选框", "十一种标志色，让熟悉的输入多一点个性。")
        stage = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        stage.add_css_class("ice-preview-stage")
        self.preview_caption = label("候选框预览  /  示例文字", "ice-preview-caption")
        stage.append(self.preview_caption)
        self.candidate = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, halign=Gtk.Align.FILL, hexpand=True)
        self.candidate.add_css_class("ice-candidate")
        self.candidate.append(label("chun feng", "ice-code"))
        self.words = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=False)
        self.candidate.append(self.words)
        stage.append(self.candidate)
        box.append(stage)
        themes = self.group(box, "主题配色", "11 种标志色各有浅色与夜色，另保留 4 套经典主题。选择配色会配对对应夜色。")
        browser = Gtk.Box(spacing=8, margin_top=8, margin_bottom=8)
        self.variant_buttons = {}
        for variant, title in (("light", "浏览浅色"), ("dark", "浏览夜色")):
            toggle = Gtk.ToggleButton(label=title)
            toggle.connect("clicked", lambda _, v=variant: self.set_theme_variant(v))
            browser.append(toggle)
            self.variant_buttons[variant] = toggle
        themes.add(browser)
        tiles = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True, min_children_per_line=2, max_children_per_line=4, column_spacing=8, row_spacing=8)
        themes.add(tiles)
        self.theme_buttons = {}
        for name, (title, bg, fg, active, hl) in THEMES.items():
            toggle = Gtk.ToggleButton()
            toggle.add_css_class("ice-theme")
            toggle.set_active(self.values["theme"] == name)
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            sample = Gtk.Box(spacing=5, homogeneous=True)
            sample.add_css_class("ice-chip")
            first = label("1 春风", "ice-swatch-word")
            second = label("2 春丰", "ice-swatch-word")
            for widget, css in ((sample, f"box {{background:{bg};}}"), (first, f"label {{background:{hl};color:{active};}}"), (second, f"label {{color:{fg};}}")):
                provider = Gtk.CssProvider()
                provider.load_from_data(css.encode())
                widget.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
            sample.append(first)
            sample.append(second)
            inner.append(sample)
            inner.append(label(title, "ice-theme-name", True))
            inner.append(label(hl.upper(), "ice-theme-hex"))
            toggle.set_tooltip_text(f"{title} · 选中色 {hl.upper()}")
            toggle.set_child(inner)
            toggle.connect("clicked", lambda _, n=name: self.select_theme(n))
            tiles.insert(toggle, -1)
            self.theme_buttons[name] = toggle
        self.set_theme_variant(self.theme_variant)
        box.append(label("主题用于 Fcitx5 Classic UI；桌面扩展接管候选框时由扩展控制外观。", "ice-mini", True))
        group = self.group(box, "候选框样式")
        self.switch(group, "follow", "跟随系统明暗", "浅色时使用所选主题，深色时使用下方深色主题。")
        self.dropdown(group, "dark_theme", "深色主题", {k: v[0] for k, v in THEMES.items() if k in DARK_THEMES})
        self.switch(group, "vertical", "纵向排列", "关闭时横向排列候选。")
        font_button = Gtk.FontButton(font=self.values["font"], use_font=False, use_size=False)
        font_button.connect("font-set", lambda w: self.change("font", w.get_font()))
        self.widgets["font"] = font_button
        self.row(group, "候选字体与字号", "使用本机字体；离线包附带思源黑体（Noto CJK）。", font_button)
        count = Gtk.SpinButton.new_with_range(3, 9, 1)
        count.set_value(self.values["page_size"])
        count.connect("value-changed", lambda w: self.change("page_size", w.get_value_as_int()))
        self.widgets["page_size"] = count
        self.row(group, "每页候选数", "数字键选择对应候选。", count)

    def set_theme_variant(self, variant):
        self.theme_variant = variant
        for key, widget in self.variant_buttons.items():
            widget.set_active(key == variant)
        for name, widget in self.theme_buttons.items():
            widget.get_parent().set_visible((name in DARK_THEMES) == (variant == "dark"))

    def select_theme(self, name):
        self.change("theme", name)
        dark = THEME_PAIRS.get(name, name if name in DARK_THEMES else None)
        if dark:
            self.widgets["dark_theme"].set_selected(self.choice_keys["dark_theme"].index(dark))
        for key, widget in self.theme_buttons.items():
            widget.set_active(key == name)
        self.set_theme_variant("dark" if name in DARK_THEMES else "light")

    def update_preview(self):
        if not hasattr(self, "candidate"):
            return
        manager = Adw.StyleManager.get_default()
        theme = self.values["dark_theme"] if self.values["follow"] and manager.get_dark() else self.values["theme"]
        self.preview_caption.set_text(f"{THEMES[theme][0]}  /  选中色 {THEMES[theme][4].upper()}" if theme in THEMES else "当前使用其他主题；下方以青玉示意，选择主题后可预览")
        _, bg, fg, active, hl = THEMES.get(theme, THEMES["rime-ice-jade"])
        description = Pango.FontDescription.from_string(self.values["font"])
        size = description.get_size() / Pango.SCALE or 14
        self.preview_provider.load_from_data(f".ice-candidate {{background:{bg};color:{fg};}} .ice-word {{font-size:{size}pt;}} .ice-first {{background:{hl};color:{active};}}".encode())
        while self.words.get_first_child():
            self.words.remove(self.words.get_first_child())
        self.words.set_max_children_per_line(1 if self.values["vertical"] else 5)
        self.words.set_min_children_per_line(1 if self.values["vertical"] else 3)
        for index, text in enumerate(["春风", "春丰", "春峰", "淳风", "春凤", "春枫", "醇风", "春锋", "春逢"][:self.values["page_size"]]):
            word = label(f"{index+1}  {text}", "ice-word")
            attributes = Pango.AttrList()
            attributes.insert(Pango.attr_font_desc_new(description))
            word.set_attributes(attributes)
            if not index:
                word.add_css_class("ice-first")
            self.words.insert(word, -1)

    def toggle_mode(self):
        manager = Adw.StyleManager.get_default()
        manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT if manager.get_dark() else Adw.ColorScheme.FORCE_DARK)
        self.update_preview()

    def shortcuts(self, box):
        self.title(box, "快捷键", "少一点切换，多一点顺手。")
        group = self.group(box, "切换输入状态")
        self.dropdown(group, "trigger", "启用 / 关闭输入法", {"Control+space": "Ctrl + Space", "Control+Shift+space": "Ctrl + Shift + Space", "Alt+space": "Alt + Space", "Super+space": "Super + Space"}, "桌面可能占用相同组合键；应用只修改首个切换键，保留其他绑定。")
        self.dropdown(group, "shift", "左 Shift 行为", SHIFT_ACTIONS, "输入拼音时按下左 Shift 的处理方式。")
        group = self.group(box, "Rime 常用操作")
        self.row(group, "选择候选", "空格选择首个候选，数字键选择对应项。")
        self.row(group, "删除已学习候选", "选中候选后按 Ctrl + Delete；不删除公开词典。")
        self.row(group, "更多快捷键", "翻页、方案切换和应用级快捷键可在系统工具中配置。", button("打开配置工具", self.open_config))

    def dictionary(self, box):
        self.title(box, "个人词库", "你的常用短语和专业术语，保存在自己的电脑。")
        actions = Gtk.Box(spacing=8)
        self.search = Gtk.SearchEntry(hexpand=True, placeholder_text="搜索词条或编码")
        self.search.connect("search-changed", lambda _: self.render_phrases())
        actions.append(self.search)
        actions.append(button("添加词条", lambda: self.phrase_dialog(), True))
        box.append(actions)
        actions = Gtk.Box(spacing=8, margin_top=10, margin_bottom=14)
        actions.append(button("导入 TXT", lambda: self.choose_file(False, "导入自定义词库", self.import_phrases)))
        actions.append(button("导出 TXT", lambda: self.choose_file(True, "导出自定义词库", self.export_phrases, "custom_phrase.txt")))
        box.append(actions)
        self.phrase_count = label("", "ice-mini")
        box.append(self.phrase_count)
        self.phrase_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, margin_top=10)
        self.phrase_list.add_css_class("boxed-list")
        box.append(self.phrase_list)
        box.append(label("修改在点击“应用设置”后生效。TXT 导出保留词条、编码和权重；固定第二位规则请用配置备份迁移。", "ice-mini", True))
        group = self.group(box, "自动学习词库")
        self.row(group, "与自定义短语分开存储", "个人配置备份不包含正在使用的学习数据库。可从 Rime 菜单“同步用户数据”后自行保管同步文件。", button("打开词库目录", lambda: self.open_path(self.store.rime)))
        self.render_phrases()

    def render_phrases(self):
        query = self.search.get_text().lower()
        while self.phrase_list.get_first_child():
            self.phrase_list.remove(self.phrase_list.get_first_child())
        matches = [(index, entry) for index, entry in enumerate(self.entries) if query in (entry["text"] + " " + entry["code"]).lower()]
        self.phrase_count.set_text(f"共 {len(self.entries)} 个词条 · 匹配 {len(matches)} 个" + (" · 仅显示前 200 条，请搜索缩小范围" if len(matches) > 200 else ""))
        for index, entry in matches[:200]:
            row = Adw.ActionRow(title=GLib.markup_escape_text(entry["text"]), subtitle=GLib.markup_escape_text(entry["code"] + ("  · 固定第二位" if entry.get("second") else f"  · 权重 {entry['weight']}")))
            edit = button("编辑", lambda i=index: self.phrase_dialog(i))
            edit.set_valign(Gtk.Align.CENTER)
            row.add_suffix(edit)
            remove = button("删除", lambda i=index: self.delete_phrase(i))
            remove.set_valign(Gtk.Align.CENTER)
            row.add_suffix(remove)
            self.phrase_list.append(row)
        if not matches:
            self.phrase_list.append(label("暂无词条，添加一条试试。", "ice-phrase"))

    def phrase_dialog(self, index=None):
        entry = self.entries[index] if index is not None else {"text": "", "code": "", "weight": 100, "second": False}
        dialog = Gtk.Dialog(title="编辑词条" if index is not None else "添加词条", transient_for=self, modal=True)
        dialog.add_button("取消", Gtk.ResponseType.CANCEL)
        dialog.add_button("保存到待应用列表", Gtk.ResponseType.OK)
        area = dialog.get_content_area()
        area.set_spacing(10)
        for edge in ("top", "bottom", "start", "end"):
            getattr(area, "set_margin_" + edge)(22)
        text = Gtk.Entry(text=entry["text"], placeholder_text="例如：你好，世界")
        code = Gtk.Entry(text=entry["code"], placeholder_text="例如：nhsj")
        weight = Gtk.SpinButton.new_with_range(0, 2147483647, 1)
        weight.set_value(entry["weight"])
        second = Gtk.CheckButton(label="固定为第二候选", active=entry.get("second", False))
        for title, widget in (("词条", text), ("输入编码", code), ("权重（越高越靠前）", weight)):
            area.append(label(title, "ice-mini"))
            area.append(widget)
        area.append(second)
        error = label("", "error", True)
        area.append(error)
        def response(_, response_id):
            if response_id == Gtk.ResponseType.OK:
                proposal = copy.deepcopy(self.entries)
                item = {"text": text.get_text().strip(), "code": code.get_text().strip(), "weight": weight.get_value_as_int(), "second": second.get_active()}
                if index is None:
                    proposal.append(item)
                else:
                    proposal[index] = item
                try:
                    validate_phrases(proposal)
                except ConfigError as exc:
                    error.set_text(str(exc))
                    return
                self.entries = proposal
                self.mark_dictionary_dirty()
            dialog.destroy()
        dialog.connect("response", response)
        dialog.present()

    def mark_dictionary_dirty(self):
        self.dirty = True
        self.status.set_text("词库有未保存修改 · 点击应用设置后生效")
        self.render_phrases()

    def delete_phrase(self, index):
        self.confirm("删除这个自定义词条？", self.entries[index]["text"] + "\n点击应用前仍可重新加载撤销。", lambda: self.remove_phrase(index), "删除")

    def remove_phrase(self, index):
        self.entries.pop(index)
        self.mark_dictionary_dirty()

    def choose_file(self, save, title, callback, name=None):
        chooser = Gtk.FileChooserNative.new(title, self, Gtk.FileChooserAction.SAVE if save else Gtk.FileChooserAction.OPEN, "保存" if save else "打开", "取消")
        if name:
            chooser.set_current_name(name)
        def response(dialog, result):
            if result == Gtk.ResponseType.ACCEPT:
                path = dialog.get_file().get_path()
                if path:
                    try:
                        callback(Path(path))
                    except Exception as exc:
                        self.error(exc)
            dialog.destroy()
        chooser.connect("response", response)
        chooser.show()

    def import_phrases(self, path):
        if path.stat().st_size > 16 * 1024 * 1024:
            raise ConfigError("词库文件超过 16 MiB，请分批导入。")
        entries, _ = parse_phrases(path.read_text(encoding="utf-8-sig"))
        merged = merge_phrases(self.entries, entries)
        count = len(merged) - len(self.entries)
        def finish():
            self.entries = merged
            self.mark_dictionary_dirty()
        self.confirm("导入词库预览", f"读取 {len(entries)} 条，将新增 {count} 条；重复词条保留原权重。\n\n" + "\n".join(f"{e['text']}  /  {e['code']}" for e in entries[:6]), finish, "合并到待应用列表")

    def export_phrases(self, path):
        atomic_write(path, phrase_bytes(self.entries, ["# Rime Ice 自定义短语：词条、编码、权重（TAB 分隔）"]))
        self.status.set_text("词库已导出到：" + str(path))

    def backup(self, box):
        self.title(box, "数据与备份", "输入留在本机，迁移由你决定。")
        group = self.group(box, "个人备份")
        self.row(group, "设置、主题与自定义短语", "备份已保存的配置。不包含学习数据库、同步目录和机器标识。", button("创建备份", lambda: self.choose_file(True, "保存个人配置备份", self.export_backup, "rime-ice-backup.json"), True))
        self.row(group, "从备份恢复", "恢复前会再次备份当前配置；恢复后请求重新部署。", button("选择备份", lambda: self.choose_file(False, "选择配置备份", self.confirm_restore)))
        self.row(group, "自动备份目录", "每次修改前保存原文件；可用文件管理器查看。", button("打开目录", lambda: self.open_path(self.store.backups)))
        group = self.group(box, "隐私与分享")
        self.row(group, "分享安装包不包含个人数据", "安装包仅包含公开词典、通用主题和设置中心；系统依赖由 APT 管理。")
        self.row(group, "不需要登录", "本应用没有云端服务，不收集输入内容。")

    def export_backup(self, path):
        self.store.export_backup(path)
        self.status.set_text("个人配置备份已保存；请妥善保管其中的短语。")

    def confirm_restore(self, path):
        def restore():
            self.run_work(lambda: (self.store.restore(path), reload_input_method()), "正在恢复配置…", rebuild=True)
        self.confirm("恢复这个备份？", f"{path.name}\n当前配置将先自动备份，未应用的编辑将被放弃。", restore, "备份并恢复")

    def installation(self, box):
        self.title(box, "安装与依赖", "安装应用，所需依赖由 Ubuntu 软件源提供。")
        group = self.group(box, "当前版本")
        self.row(group, "Rime Ice " + __version__, "包含设置中心、雾凇拼音方案、公开词典和 26 套候选框主题。")
        self.row(group, "Ubuntu 24.04 · x86_64", "目前验证 Intel / AMD 64 位电脑；其他版本和架构尚未验证。")
        group = self.group(box, "安装应用")
        self.row(group, "1. 下载应用安装包", "从 GitHub Releases 下载 rime-ice_" + __version__ + "_all.deb。")
        self.row(group, "2. 使用 APT 安装", "在下载目录执行 sudo apt install ./rime-ice_" + __version__ + "_all.deb；缺少的依赖会从软件源安装。")
        self.row(group, "3. 启用雾凇拼音", "打开常用设置，启用输入法并在 Fcitx5 中添加 Rime，然后注销并重新登录。")
        group = self.group(box, "系统依赖")
        self.row(group, "Fcitx5、Rime、GTK 与字体", "应用包不包含这些系统软件；安装时由 APT 检查并安装缺少的依赖，需要可用的软件源与网络。")
        self.row(group, "遇到缺少依赖的提示", "若使用 dpkg 安装后依赖未满足，请联网执行 sudo apt --fix-broken install，并检查确认安装计划。")
        self.row(group, "安装后可离线输入", "拼音输入、公开词典、主题和个人配置均在本机使用，无需云服务。")
        group = self.group(box, "升级与卸载")
        self.row(group, "升级应用", "下载新版 .deb 并使用 APT 安装；从旧名称升级时可同时安装发布页提供的过渡包。个人词库保留在用户目录。")
        self.row(group, "卸载设置中心", "使用系统软件管理器移除 rime-ice；不自动删除个人词库。")
        self.row(group, "开源说明与源代码", "应用源码与安装包一同发布，保留 GPL 和上游许可。", button("查看说明", lambda: self.open_path(Path("/usr/share/doc/rime-ice"))))

    def open_path(self, path):
        if not path.exists():
            self.error(ConfigError("目录尚不存在：" + str(path)))
            return
        Gio.AppInfo.launch_default_for_uri(path.as_uri(), None)

    def open_config(self):
        try:
            subprocess.Popen(["fcitx5-configtool"])
        except OSError as exc:
            self.error(exc)

    def confirm_enable(self):
        self.confirm("为当前用户启用雾凇输入法？", "复制缺失的公开词典，保留已有方案文件。随后使用系统 im-config 选择 Fcitx5，并打开配置工具添加 Rime。\n\n启用后会重新加载配置，尚未应用的编辑将被放弃。完成后需要注销并重新登录。", lambda: self.run_work(lambda: (self.store.initialize(), enable_input_method()), "正在准备输入方案…", rebuild=True), "启用")

    def confirm(self, title, body, callback, action="继续"):
        dialog = Adw.MessageDialog.new(self, title, body)
        dialog.add_response("cancel", "取消")
        dialog.add_response("continue", action)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.set_response_appearance("continue", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", lambda _, response: callback() if response == "continue" else None)
        dialog.present()

    def error(self, error):
        dialog = Adw.MessageDialog.new(self, "操作未完成", str(error))
        dialog.add_response("close", "知道了")
        dialog.present()

    def run_work(self, operation, message, rebuild=False, commits=False):
        if self.busy:
            return
        self.busy = True
        self.get_content().set_sensitive(False)
        self.status.set_text(message)
        def work():
            try:
                result, error = operation(), None
            except Exception as exc:
                result, error = None, exc
            GLib.idle_add(done, result, error)
        def done(result, error):
            self.busy = False
            self.get_content().set_sensitive(True)
            if error:
                if isinstance(error, DeploymentError):
                    if commits or rebuild:
                        self.rebuild()
                    self.status.set_text("重新部署未完成，可重试；待应用的编辑仍保留" if not (commits or rebuild) else "配置已保存 · 重新部署未完成，可在常用设置中重试")
                else:
                    self.status.set_text("操作未完成；请查看详细信息。")
                self.error(error)
            else:
                if rebuild:
                    self.rebuild()
                if commits or rebuild:
                    self.dirty = False
                message = result if isinstance(result, str) else result[-1] if isinstance(result, tuple) and isinstance(result[-1], str) else "操作完成。"
                if self.dirty:
                    message += " 尚有未应用的编辑。"
                self.status.set_text(message)
            return GLib.SOURCE_REMOVE
        threading.Thread(target=work, daemon=True).start()

    def save(self):
        if not (self.store.rime / "rime_ice.schema.yaml").exists():
            self.error(ConfigError("请先在“常用设置”中启用输入方案，再应用设置。"))
            return
        if not self.dirty:
            self.status.set_text("没有需要应用的修改。")
            return
        values, entries = copy.deepcopy(self.values), copy.deepcopy(self.entries)
        def apply():
            backup = self.store.apply(values, entries)
            if backup is None:
                return None, "没有需要写入的修改。"
            return backup, "配置已保存。" + reload_input_method()
        self.run_work(apply, "正在备份并应用设置…", commits=True)

    def rebuild(self):
        page = self.stack.get_visible_child_name()
        self.store.load()
        self.values = copy.deepcopy(self.store.settings)
        self.theme_variant = "dark" if self.values["theme"] in DARK_THEMES else "light"
        self.entries = copy.deepcopy(self.store.phrases)
        self.loading = True
        self.build()
        self.loading = False
        self.stack.set_visible_child_name(page)
        self.update_preview()
        self.dirty = False

    def confirm_reload(self):
        if self.dirty:
            self.confirm("放弃未应用的修改？", "重新读取本机配置。已经保存到本机的设置不会被撤销。", self.safe_rebuild, "重新加载")
        else:
            self.safe_rebuild()

    def safe_rebuild(self):
        try:
            self.rebuild()
        except Exception as exc:
            self.error(exc)

    def on_close(self, _):
        if self.busy:
            return True
        if self.dirty:
            self.confirm("退出并放弃未应用的修改？", "本机已经保存的设置不受影响。", self.destroy, "退出")
            return True
        return False


class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.rimeice.Settings", flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self):
        if self.get_active_window():
            self.get_active_window().present()
            return
        try:
            window = SettingsWindow(self)
            window.present()
        except Exception as error:
            dialog = Adw.MessageDialog(heading="无法读取输入法配置", body=str(error))
            self.add_window(dialog)
            dialog.add_response("close", "关闭")
            dialog.present()


def main():
    import sys
    return Application().run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
