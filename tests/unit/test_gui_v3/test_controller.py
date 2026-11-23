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
from dataclasses import dataclass, replace
from pathlib import Path

from inputremapper.gui_v3.controller import (
    RECORD_BLOCKED_MESSAGE,
    Controller,
    unique_name,
)
from inputremapper.gui_v3.document import InputRef, Trigger
from inputremapper.gui_v3.tree import Call


@dataclass
class FakeGroup:
    key: str
    name: str


class FakeGroups:
    def __init__(self, *groups: FakeGroup) -> None:
        self.groups = list(groups)

    def get_groups(
        self,
    ) -> list[FakeGroup]:
        return self.groups


class FakeDaemon:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.fail: set[str] = set()
        self.running: dict[str, str] = {}

    def start_injecting(self, group_key: str, preset: str) -> bool:
        self.calls.append(("start", group_key, preset))
        if group_key in self.fail:
            return False
        self.running[group_key] = preset
        return True

    def set_config_dir(self, config_dir: str) -> None:
        self.config_dir = config_dir

    def stop_all(self) -> None:
        self.calls.append(("stop_all",))
        self.running = {}

    def get_running_preset(self, group_key: str) -> str:
        return self.running.get(group_key, "")

    def get_state(self, group_key: str) -> str:
        return "RUNNING" if group_key in self.running else "UNKNOWN"


class OldDaemon(FakeDaemon):
    """A service that can say what runs, but not which preset."""

    def get_running_preset(self, group_key: str) -> str:
        raise AttributeError("DBus object has no attribute 'get_running_preset'")


class TestController(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.profiles = root / "profiles"
        self.presets = root / "presets"
        self.daemon = FakeDaemon()
        self.groups = FakeGroups(FakeGroup("kbd", "Keyboard"))
        self.controller = Controller(
            self.daemon, self.groups, self.profiles, self.presets
        )

    def _profile_with_entry(self) -> None:
        self.controller.new_profile()
        self.controller.new_entry()
        self.controller.edit_entry(
            lambda e: replace(
                e,
                trigger=Trigger(inputs=(InputRef(1, 30),), device="kbd"),
                then=(Call.make("key", "a"),),
            )
        )

    def test_unique_name(self) -> None:
        self.assertEqual(unique_name("a", []), "a")
        self.assertEqual(unique_name("a", ["a"]), "a 2")
        self.assertEqual(unique_name("a", ["a", "a 2"]), "a 3")

    def test_new_profile_is_selected_and_undoable(self) -> None:
        self.controller.new_profile()
        self.controller.new_profile()
        self.assertEqual(self.controller.selected_profile, "New profile 2")
        self.controller.undo()
        self.assertEqual(len(self.controller.workspace.profiles), 1)
        self.assertEqual(self.controller.selected_profile, "New profile")
        self.controller.redo()
        self.assertEqual(len(self.controller.workspace.profiles), 2)

    def test_edits_are_saved_to_disk_and_undo_is_saved_too(self) -> None:
        self.controller.new_profile()
        self.assertTrue((self.profiles / "New profile.json").exists())
        self.controller.undo()
        self.assertFalse((self.profiles / "New profile.json").exists())

    def test_rename_collision_is_reported_not_raised(self) -> None:
        self.controller.new_profile()
        self.controller.new_profile()
        self.controller.rename_profile("New profile")
        self.assertIn("already exists", self.controller.message)
        self.assertEqual(self.controller.selected_profile, "New profile 2")

    def test_copy_and_delete(self) -> None:
        self.controller.new_profile()
        self.controller.copy_profile()
        self.assertEqual(self.controller.selected_profile, "New profile copy")
        self.controller.delete_profile()
        self.assertEqual(
            [p.name for p in self.controller.workspace.profiles], ["New profile"]
        )
        self.assertEqual(self.controller.selected_profile, "New profile")

    def test_typing_a_name_is_one_undo_step(self) -> None:
        self.controller.new_profile()
        self.controller.new_entry()
        for text in ("a", "ab", "abc"):
            self.controller.edit_entry(
                lambda e, t=text: replace(e, name=t), merge_key="name"
            )
        self.controller.undo()
        self.assertIsNone(self.controller.entry.name if self.controller.entry else None)

    def test_apply_stops_everything_then_starts_rendered_preset(self) -> None:
        self._profile_with_entry()
        self.controller.apply()
        self.assertEqual(
            self.daemon.calls,
            [("stop_all",), ("start", "kbd", "[v3 read-only] New profile")],
        )
        self.assertEqual(self.controller.active_profile, "New profile")
        written = self.presets / "Keyboard" / "[v3 read-only] New profile.json"
        self.assertEqual(json.loads(written.read_text())[0]["output_symbol"], "key(a)")

    def test_toggle_stops_whatever_runs_even_another_profile(self) -> None:
        self._profile_with_entry()
        self.daemon.running = {"kbd": "my old preset"}
        self.controller.sync_running()
        self.assertTrue(self.controller.running)
        self.controller.toggle_apply()
        self.assertEqual(self.daemon.calls[-1], ("stop_all",))
        self.assertFalse(self.controller.running)
        self.assertTrue(self.controller.can_record)

    def test_cannot_record_while_a_profile_runs(self) -> None:
        self._profile_with_entry()
        self.assertTrue(self.controller.can_record)
        self.controller.toggle_apply()
        self.assertFalse(self.controller.can_record)
        self.controller.start_recording()
        self.assertFalse(self.controller.recording)
        self.assertEqual(self.controller.message, RECORD_BLOCKED_MESSAGE)
        self.controller.toggle_apply()
        self.assertTrue(self.controller.can_record)

    def test_finds_a_profile_started_elsewhere(self) -> None:
        self._profile_with_entry()
        self.daemon.running = {"kbd": "[v3 read-only] New profile"}
        self.controller.sync_running()
        self.assertEqual(self.controller.active_profile, "New profile")
        self.assertFalse(self.controller.can_record)
        self.daemon.running = {}
        self.controller.sync_running()
        self.assertIsNone(self.controller.active_profile)
        self.assertTrue(self.controller.can_record)

    def test_finds_the_profile_from_its_devices_on_an_old_service(self) -> None:
        self._profile_with_entry()
        self.controller.daemon = OldDaemon()
        self.controller.daemon.running = {"kbd": "whatever"}
        self.controller.sync_running()
        self.assertEqual(self.controller.active_profile, "New profile")
        self.assertFalse(self.controller.can_record)

    def test_a_v1_preset_running_blocks_recording(self) -> None:
        self._profile_with_entry()
        self.daemon.running = {"kbd": "my old preset"}
        self.controller.sync_running()
        self.assertIsNone(self.controller.active_profile)
        self.assertFalse(self.controller.can_record)

    def test_add_variable_declares_it_once(self) -> None:
        self._profile_with_entry()
        self.controller.add_variable("$count")
        self.controller.add_variable("count")
        self.controller.add_variable("not valid")
        self.controller.add_variable("")
        profile = self.controller.profile
        assert profile is not None
        self.assertEqual(profile.variables, ("count",))

    def test_toggle_stops_the_active_profile(self) -> None:
        self._profile_with_entry()
        self.controller.toggle_apply()
        self.controller.toggle_apply()
        self.assertIsNone(self.controller.active_profile)
        self.assertEqual(self.daemon.calls[-1], ("stop_all",))

    def test_applying_another_profile_replaces_the_active_one(self) -> None:
        self._profile_with_entry()
        self.controller.apply()
        self.controller.copy_profile()
        self.controller.apply()
        self.assertEqual(self.controller.active_profile, "New profile copy")

    def test_apply_with_an_invalid_entry_changes_nothing(self) -> None:
        self.controller.new_profile()
        self.controller.new_entry()
        self.controller.apply()
        self.assertEqual(self.daemon.calls, [])
        self.assertIsNotNone(self.controller.error)
        assert self.controller.error is not None
        self.assertTrue(self.controller.error.startswith("In this mapping, "))
        self.assertIsNotNone(self.controller.entry)
        self.assertIsNone(self.controller.active_profile)

    def test_apply_selects_the_entry_with_the_problem(self) -> None:
        self._profile_with_entry()
        self.controller.new_entry()  # an empty second entry
        good = self.controller.workspace.profiles[0].entries[0].id
        bad = self.controller.selected_entry
        self.controller.select_entry(good)
        self.controller.apply()
        self.assertEqual(self.controller.selected_entry, bad)
        self.controller.dismiss_error()
        self.assertIsNone(self.controller.error)

    def test_failed_start_is_reported(self) -> None:
        self._profile_with_entry()
        self.daemon.fail.add("kbd")
        self.controller.apply()
        self.assertIn("kbd", self.controller.error or "")

    def test_deleting_the_active_profile_stops_it(self) -> None:
        self._profile_with_entry()
        self.controller.apply()
        self.controller.delete_profile()
        self.assertIsNone(self.controller.active_profile)
        self.assertEqual(self.daemon.calls[-1], ("stop_all",))

    def test_import_skips_rendered_presets(self) -> None:
        directory = self.presets / "Keyboard"
        directory.mkdir(parents=True)
        mapping = [
            {
                "input_combination": [{"type": 1, "code": 30}],
                "target_uinput": "keyboard",
                "output_symbol": "b",
            }
        ]
        (directory / "mine.json").write_text(json.dumps(mapping))
        (directory / "[v3 read-only] x.json").write_text("[]")

        found = self.controller.list_v1_presets()
        self.assertEqual([p.name for p in found], ["mine"])

        self.controller.new_profile()
        self.controller.import_v1(found[0])
        profile = self.controller.profile
        assert profile is not None
        self.assertEqual(len(profile.entries), 1)
        self.assertEqual(profile.entries[0].trigger.device, "kbd")
        self.controller.undo()
        profile = self.controller.profile
        assert profile is not None
        self.assertEqual(len(profile.entries), 0)

    def test_import_declares_the_variables_macros_use(self) -> None:
        directory = self.presets / "Keyboard"
        directory.mkdir(parents=True)
        mappings = [
            {
                "input_combination": [{"type": 1, "code": 30}],
                "target_uinput": "keyboard",
                "output_symbol": "set(mode, 1).if_eq($mode, 1, key(a), key(b))",
            },
            {
                "input_combination": [{"type": 1, "code": 31}],
                "target_uinput": "keyboard",
                "output_symbol": "set(count, 2).bogus($other)",
            },
        ]
        (directory / "vars.json").write_text(json.dumps(mappings))
        self.controller.new_profile()
        self.controller.set_variables(["existing"])
        self.controller.import_v1(self.controller.list_v1_presets()[0])
        profile = self.controller.profile
        assert profile is not None
        self.assertEqual(profile.variables, ("existing", "mode", "count", "other"))
        self.controller.undo()
        profile = self.controller.profile
        assert profile is not None
        self.assertEqual(profile.variables, ("existing",))

    def test_variables_are_cleaned(self) -> None:
        self.controller.new_profile()
        self.controller.set_variables([" a ", "", "a", "b"])
        profile = self.controller.profile
        assert profile is not None
        self.assertEqual(profile.variables, ("a", "b"))


if __name__ == "__main__":
    unittest.main()
