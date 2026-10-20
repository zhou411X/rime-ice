# SPDX-License-Identifier: GPL-3.0-only
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rime_ice.model import Store, ConfigError, ini_set, ini_get, parse_phrases, merge_phrases, load_yaml, patch_get, patch_set


class ModelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.assets = self.home / "assets"
        (self.assets / "rime/lua").mkdir(parents=True)
        (self.assets / "rime/lua/rime_ice_settings_filter.lua").write_text("return {}\n")
        self.store = Store(self.home, self.assets)
        self.store.rime.mkdir(parents=True)
        (self.store.rime / "rime_ice.custom.yaml").write_text("patch:\n  unrelated/setting: 42\n  engine/filters/+: [other_filter]\n")
        self.store.load()

    def tearDown(self):
        self.tmp.cleanup()

    def test_ini_preserves_other_sections_and_comments(self):
        raw = "# hello\nFont=Old\n[Other]\nFont=Untouched\n# retained\n"
        result = ini_set(raw, "", "Font", '"Noto 14"')
        self.assertIn("# hello", result)
        self.assertIn("Font=Untouched\n# retained", result)
        self.assertEqual(ini_get(result, "", "Font"), "Noto 14")

    def test_ini_insert_no_loss(self):
        raw = "[Other]\nx=y\n"
        self.assertIn("Font=Noto\n[Other]", ini_set(raw, "", "Font", "Noto"))
        self.assertIn("[Hotkey/TriggerKeys]\n0=Control+space", ini_set(raw, "Hotkey/TriggerKeys", "0", "Control+space"))

    def test_nested_patch_updates_without_conflicting_override(self):
        doc = {"patch": {"menu": {"page_size": 5, "other": 1}}}
        patch_set(doc, "menu/page_size", 9)
        self.assertEqual(patch_get(doc, "menu/page_size"), 9)
        self.assertEqual(doc["patch"]["menu"]["other"], 1)
        self.assertNotIn("menu/page_size", doc["patch"])

    def test_reject_duplicate_yaml_keys(self):
        with self.assertRaises(ConfigError):
            load_yaml("patch: {}\npatch: {}\n")

    def test_rime_plain_tab_scalar_compatibility(self):
        doc = load_yaml("patch:\n  second_cand_filter:\n    - vim\tvim\n")
        self.assertEqual(doc["patch"]["second_cand_filter"], ["vim\tvim"])

    def test_save_preserves_unknown_yaml(self):
        settings = copy.deepcopy(self.store.settings)
        settings["page_size"] = 7
        backup = self.store.apply(settings, [])
        doc = load_yaml((self.store.rime / "rime_ice.custom.yaml").read_text())
        self.assertEqual(doc["patch"]["unrelated/setting"], 42)
        self.assertEqual(doc["patch"]["menu/page_size"], 7)
        self.assertTrue(backup.exists())
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)

    def test_noop_does_not_touch_files(self):
        self.assertIsNone(self.store.apply(self.store.settings, []))
        self.assertFalse(self.store.backups.exists())

    def test_concurrent_modification_refused(self):
        path = self.store.rime / "rime_ice.custom.yaml"
        path.write_text("patch: {other: true}\n")
        settings = copy.deepcopy(self.store.settings)
        settings["page_size"] = 7
        with self.assertRaisesRegex(ConfigError, "其他程序"):
            self.store.apply(settings, [])
        self.assertIn("other: true", path.read_text())

    def test_transaction_rolls_back_partial_writes(self):
        a, b = self.store.rime / "a.txt", self.store.rime / "b.txt"
        a.write_bytes(b"original")
        from rime_ice import model
        original = model.atomic_write
        def failing(path, data, mode=0o600):
            if path == b:
                raise OSError("disk full")
            return original(path, data, mode)
        with patch.object(model, "atomic_write", failing):
            with self.assertRaises(OSError):
                self.store.commit({a:b"changed", b:b"new"})
        self.assertEqual(a.read_bytes(), b"original")
        self.assertFalse(b.exists())

    def test_phrases_merge_deduplicates_preserving_existing_weight(self):
        old, _ = parse_phrases("你好\tnh\t9\n")
        imported, _ = parse_phrases("你好\tnh\t100\n再见\tzj\t100\n")
        merged = merge_phrases(old, imported)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["weight"], 9)

    def test_invalid_phrase_is_not_silently_dropped(self):
        with self.assertRaises(ConfigError):
            parse_phrases("bad data without tabs\n")

    def test_phrase_update_preserves_filter_chain(self):
        entries = [{"text":"triton", "code":"triton", "weight":100, "second":True}]
        self.store.apply(self.store.settings, entries)
        doc = load_yaml((self.store.rime / "rime_ice.custom.yaml").read_text())
        self.assertEqual(doc["patch"]["engine/filters/+"], ["other_filter", "lua_filter@*rime_ice_settings_filter"])
        self.store.apply(self.store.settings, [])
        doc = load_yaml((self.store.rime / "rime_ice.custom.yaml").read_text())
        self.assertEqual(len(doc["patch"]["engine/filters/+"]), 2)

    def test_backup_restore_round_trip(self):
        export = self.home / "backup.json"
        self.store.export_backup(export)
        original = (self.store.rime / "rime_ice.custom.yaml").read_bytes()
        settings = copy.deepcopy(self.store.settings)
        settings["page_size"] = 7
        self.store.apply(settings, [])
        self.store.restore(export)
        self.assertEqual((self.store.rime / "rime_ice.custom.yaml").read_bytes(), original)

    def test_backup_never_includes_learning_db(self):
        (self.store.rime / "private.userdb").mkdir()
        (self.store.rime / "private.userdb/data").write_text("private")
        export = self.home / "backup.json"
        self.store.export_backup(export)
        self.assertNotIn("userdb", export.read_text())

    def test_path_traversal_rejected(self):
        export = self.home / "bad.json"
        export.write_text(json.dumps({"format":"rime-ice-backup-v1","files":{"data/fcitx5/../../../outside.txt":"eA=="}}))
        with self.assertRaises(ConfigError):
            self.store.restore(export)

    def test_unowned_rime_files_cannot_be_deleted_by_backup(self):
        schema = self.store.rime / "rime_ice.schema.yaml"
        schema.write_text("schema: {schema_id: mine}")
        export = self.home / "bad.json"
        export.write_text(json.dumps({"format":"rime-ice-backup-v1","files":{"data/fcitx5/rime/rime_ice.schema.yaml":None}}))
        with self.assertRaisesRegex(ConfigError, "管理范围"):
            self.store.restore(export)
        self.assertTrue(schema.exists())

    def test_invalid_restore_is_rejected_before_live_write(self):
        import base64
        original = (self.store.rime / "rime_ice.custom.yaml").read_bytes()
        for content in (b"patch: {menu/page_size: bogus}", b"patch: {rime_ice_settings_filter: [bad]}"):
            export = self.home / "bad.json"
            export.write_text(json.dumps({"format":"rime-ice-backup-v1", "files":{"data/fcitx5/rime/rime_ice.custom.yaml":base64.b64encode(content).decode()}}))
            with self.assertRaises(ConfigError):
                self.store.restore(export)
            self.assertEqual((self.store.rime / "rime_ice.custom.yaml").read_bytes(), original)

    def test_edited_owned_filter_is_not_overwritten(self):
        path = self.store.rime / "lua/rime_ice_settings_filter.lua"
        path.parent.mkdir()
        path.write_text("local edit")
        entries = [{"text":"word", "code":"word", "weight":100, "second":True}]
        with self.assertRaisesRegex(ConfigError, "其他程序"):
            self.store.apply(self.store.settings, entries)

    def test_existing_install_repaired_without_overwriting_custom_files(self):
        (self.assets / "rime/rime_ice.schema.yaml").write_text("schema: {new: true}")
        (self.assets / "rime/default.yaml").write_text("new: true")
        (self.store.rime / "rime_ice.schema.yaml").write_text("schema: {mine: true}")
        self.store.initialize()
        self.assertTrue((self.store.rime / "default.yaml").exists())
        self.assertIn("mine: true", (self.store.rime / "rime_ice.schema.yaml").read_text())

    def test_new_user_activation_sets_explicit_theme_without_overwriting_existing(self):
        (self.assets / "rime/rime_ice.schema.yaml").write_text("schema: {}")
        self.store.initialize()
        self.assertEqual(self.store.settings["theme"], "rime-ice-jade")
        config = self.store.config / "fcitx5/config"
        self.assertIn("[Hotkey/AltTriggerKeys]", config.read_text())
        classic = self.store.config / "fcitx5/conf/classicui.conf"
        classic.write_text("Theme=my-theme\n")
        self.store.initialize()
        self.assertEqual(classic.read_text(), "Theme=my-theme\n")

    def test_new_user_conflicts_stop_before_any_write(self):
        (self.assets / "rime/rime_ice.schema.yaml").write_text("schema: {}")
        (self.assets / "rime/default.yaml").write_text("different: true")
        (self.store.rime / "default.yaml").write_text("mine: true")
        with self.assertRaises(ConfigError):
            self.store.initialize()
        self.assertFalse((self.store.rime / "rime_ice.schema.yaml").exists())


if __name__ == "__main__":
    unittest.main()
