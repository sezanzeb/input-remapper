# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2026 sezanzeb <4t1pzast9@mozmail.com>
#
# This file is part of input-remapper.
#
# input-remapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# input-remapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with input-remapper.  If not, see <https://www.gnu.org/licenses/>.


import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from evdev.ecodes import EV_KEY, KEY_F4, KEY_LEFTCTRL

from inputremapper.configs.mapping import Mapping
from inputremapper.gui_v3.document import Entry, InputRef, Profile, Trigger, Workspace
from inputremapper.gui_v3.macro_text import parse_text
from inputremapper.gui_v3.render import (
    RenderError,
    import_preset_file,
    is_rendered_name,
    render_profile,
    rendered_name,
    write_rendered,
)
from inputremapper.gui_v3.store import load_workspace, save_workspace
from tests.lib.test_setup import test_setup

MACRO = "set(clicking, 1).while_eq($clicking, 1, key(KEY_SPACE).wait(40))"


def make_entry(name="Start", macro=MACRO, device="kbd"):
    return Entry(
        name=name,
        trigger=Trigger(
            inputs=(InputRef(EV_KEY, KEY_LEFTCTRL), InputRef(EV_KEY, KEY_F4)),
            device=device,
        ),
        then=parse_text(macro),
        v1_extra={"release_timeout": 0.2},
    )


@test_setup
class TestDocument(unittest.TestCase):
    def test_edits_do_not_mutate(self):
        entry = make_entry()
        profile = Profile("p", (entry,))
        renamed = profile.with_entry(replace(entry, name="x"))
        self.assertEqual(profile.entries[0].name, "Start")
        self.assertEqual(renamed.entries[0].name, "x")

    def test_move_remove_copy_rename(self):
        a, b = make_entry("a"), make_entry("b")
        profile = Profile("p", (a, b))
        self.assertEqual(profile.moved_entry(b.id, 0).entries, (b, a))
        self.assertEqual(profile.without_entry(a.id).entries, (b,))

        workspace = Workspace((profile,))
        copied = workspace.copied_profile("p", "p2")
        self.assertEqual(len(copied.profiles), 2)
        self.assertNotEqual(copied.get("p2").entries[0].id, a.id)
        renamed = workspace.renamed_profile("p", "q")
        self.assertIsNone(renamed.get("p"))
        with self.assertRaises(ValueError):
            copied.renamed_profile("p", "p2")

    def test_json_round_trip(self):
        profile = Profile(
            "p", (make_entry(), make_entry(name=None, macro="KEY_ESC")), ("clicking",)
        )
        loaded = Profile.from_json("p", json.loads(json.dumps(profile.to_json())))
        self.assertEqual(loaded, profile)

    def test_store_round_trip_and_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            first = Workspace((Profile("a", (make_entry(),)), Profile("b / c")))
            save_workspace(first, directory)
            self.assertEqual(
                load_workspace(directory),
                Workspace((Profile("a", first.get("a").entries), Profile("b _ c"))),
            )

            second = first.without_profile("a")
            save_workspace(second, directory, previous=first)
            self.assertEqual(
                [p.name for p in load_workspace(directory).profiles], ["b _ c"]
            )

    def test_broken_file_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "bad.json").write_text("{nope")
            save_workspace(Workspace((Profile("ok"),)), directory)
            self.assertEqual(
                [p.name for p in load_workspace(directory).profiles], ["ok"]
            )


@test_setup
class TestRender(unittest.TestCase):
    def test_mapping_is_valid_v1(self):
        profile = Profile("p", (make_entry(),))
        mappings = render_profile(profile)["kbd"]
        mapping = Mapping(**mappings[0])
        self.assertEqual(mapping.output_symbol, MACRO)
        self.assertEqual(mapping.release_timeout, 0.2)
        self.assertEqual(len(mapping.input_combination), 2)

    def test_write_rendered_names_and_skips_disconnected(self):
        profile = Profile("Auto", (make_entry(device="kbd"), make_entry(device="gone")))
        with tempfile.TemporaryDirectory() as tmp:
            result = write_rendered(
                profile, lambda key: {"kbd": "My Keyboard"}.get(key), presets_dir=tmp
            )
            self.assertEqual(result, {"kbd": "[v3 read-only] Auto"})
            path = Path(tmp) / "My Keyboard" / "[v3 read-only] Auto.json"
            self.assertEqual(len(json.loads(path.read_text())), 1)
            self.assertFalse((Path(tmp) / "gone").exists())

    def test_apply_reports_what_the_service_would_reject(self):
        def entry(code: str) -> Entry:
            return Entry(
                trigger=Trigger(inputs=(InputRef(EV_KEY, KEY_F4),), device="kbd"),
                then=parse_text(code),
            )

        with self.assertRaises(RenderError) as bad_time:
            render_profile(Profile("p", (entry("wait(40fdsaf)"),)))
        self.assertIn("time", str(bad_time.exception))
        self.assertIsNotNone(bad_time.exception.entry_id)

        # The engine picks the device per key, also when keys and buttons mix.
        for code in ("key(B)", "key(BTN_LEFT)", "key(a).key_down(BTN_LEFT)"):
            rendered = render_profile(Profile("p", (entry(code),)))
            self.assertEqual(rendered["kbd"][0]["target_uinput"], "auto")

        render_profile(Profile("p", (entry("key(a)"),)))

    def test_missing_trigger_or_device(self):
        with self.assertRaises(RenderError):
            render_profile(Profile("p", (Entry(trigger=Trigger(device="kbd")),)))
        with self.assertRaises(RenderError):
            render_profile(
                Profile(
                    "p",
                    (
                        replace(
                            make_entry(), trigger=Trigger(inputs=(InputRef(EV_KEY, 1),))
                        ),
                    ),
                )
            )

    def test_rendered_name(self):
        self.assertTrue(is_rendered_name(rendered_name("x")))
        self.assertFalse(is_rendered_name("x"))

    def test_import_then_render_is_lossless(self):
        original = [
            {
                "input_combination": [{"type": 1, "code": 30}],
                "target_uinput": "keyboard",
                "output_symbol": "KEY_B",
                "name": "a to b",
                "release_timeout": 0.1,
            },
            {
                "input_combination": [{"type": 1, "code": 31}, {"type": 1, "code": 32}],
                "target_uinput": "keyboard + mouse",
                "output_symbol": "key(a).wait(5)",
                "macro_key_sleep_ms": 20,
            },
            {
                "input_combination": [{"type": 3, "code": 0}],
                "target_uinput": "gamepad",
                "output_type": 3,
                "output_code": 1,
                "mapping_type": "analog",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "preset.json"
            path.write_text(json.dumps(original))
            entries = import_preset_file(path, "kbd")

        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[2].then, ())
        rendered = render_profile(Profile("p", tuple(entries)))["kbd"]
        # A plain key output is upgraded to the equivalent macro.
        original[0]["output_symbol"] = "hold_keys(KEY_B)"
        # v3 has no output device: key outputs go through "auto", and an analog one
        # takes the device that fits it.
        original[0]["target_uinput"] = "auto"
        original[1]["target_uinput"] = "auto"
        for before, after in zip(original, rendered):
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
