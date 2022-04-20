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
from inputremapper.configs.mapping import UIMapping, Mapping
from tests.test import quick_cleanup, tmp

import os
import unittest
import shutil
import json

from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    ABS_HAT0X,
    ABS_X,
    ABS_Y,
    ABS_RX,
    ABS_RY,
    EV_REL,
    REL_X,
    REL_Y,
    REL_WHEEL_HI_RES,
    REL_HWHEEL_HI_RES,
)

from inputremapper.configs.migrations import migrate, config_version
from inputremapper.configs.preset import Preset
from inputremapper.configs.global_config import global_config
from inputremapper.configs.paths import touch, CONFIG_PATH, mkdir, get_preset_path
from inputremapper.logger import IS_BETA
from inputremapper.event_combination import EventCombination
from inputremapper.user import HOME

from inputremapper.logger import VERSION


class TestMigrations(unittest.TestCase):
    def tearDown(self):
        quick_cleanup()
        self.assertEqual(len(global_config.iterate_autoload_presets()), 0)

    def test_migrate_suffix(self):
        old = os.path.join(CONFIG_PATH, "config")
        new = os.path.join(CONFIG_PATH, "config.json")

        try:
            os.remove(new)
        except FileNotFoundError:
            pass

        touch(old)
        with open(old, "w") as f:
            f.write("{}")

        migrate()
        self.assertTrue(os.path.exists(new))
        self.assertFalse(os.path.exists(old))

    def test_rename_config(self):
        old = os.path.join(HOME, ".config", "key-mapper")
        if IS_BETA:
            new = os.path.join(*os.path.split(CONFIG_PATH)[:-1])
        else:
            new = CONFIG_PATH

        # we are not destroying our actual config files with this test
        self.assertTrue(new.startswith(tmp))

        try:
            shutil.rmtree(new)
        except FileNotFoundError:
            pass

        old_config_json = os.path.join(old, "config.json")
        touch(old_config_json)
        with open(old_config_json, "w") as f:
            f.write('{"foo":"bar"}')

        migrate()

        self.assertTrue(os.path.exists(new))
        self.assertFalse(os.path.exists(old))

        new_config_json = os.path.join(new, "config.json")
        with open(new_config_json, "r") as f:
            moved_config = json.loads(f.read())
            self.assertEqual(moved_config["foo"], "bar")

    def test_wont_migrate_suffix(self):
        old = os.path.join(CONFIG_PATH, "config")
        new = os.path.join(CONFIG_PATH, "config.json")

        touch(new)
        with open(new, "w") as f:
            f.write("{}")

        touch(old)
        with open(old, "w") as f:
            f.write("{}")

        migrate()
        self.assertTrue(os.path.exists(new))
        self.assertTrue(os.path.exists(old))

    def test_migrate_preset(self):
        if os.path.exists(CONFIG_PATH):
            shutil.rmtree(CONFIG_PATH)

        p1 = os.path.join(CONFIG_PATH, "foo1", "bar1.json")
        p2 = os.path.join(CONFIG_PATH, "foo2", "bar2.json")
        touch(p1)
        touch(p2)

        with open(p1, "w") as f:
            f.write("{}")

        with open(p2, "w") as f:
            f.write("{}")

        migrate()

        self.assertFalse(os.path.exists(os.path.join(CONFIG_PATH, "foo1", "bar1.json")))
        self.assertFalse(os.path.exists(os.path.join(CONFIG_PATH, "foo2", "bar2.json")))

        self.assertTrue(
            os.path.exists(os.path.join(CONFIG_PATH, "presets", "foo1", "bar1.json")),
        )
        self.assertTrue(
            os.path.exists(os.path.join(CONFIG_PATH, "presets", "foo2", "bar2.json")),
        )

    def test_wont_migrate_preset(self):
        if os.path.exists(CONFIG_PATH):
            shutil.rmtree(CONFIG_PATH)

        p1 = os.path.join(CONFIG_PATH, "foo1", "bar1.json")
        p2 = os.path.join(CONFIG_PATH, "foo2", "bar2.json")
        touch(p1)
        touch(p2)

        with open(p1, "w") as f:
            f.write("{}")

        with open(p2, "w") as f:
            f.write("{}")

        # already migrated
        mkdir(os.path.join(CONFIG_PATH, "presets"))

        migrate()

        self.assertTrue(os.path.exists(os.path.join(CONFIG_PATH, "foo1", "bar1.json")))
        self.assertTrue(os.path.exists(os.path.join(CONFIG_PATH, "foo2", "bar2.json")))

        self.assertFalse(
            os.path.exists(os.path.join(CONFIG_PATH, "presets", "foo1", "bar1.json")),
        )
        self.assertFalse(
            os.path.exists(os.path.join(CONFIG_PATH, "presets", "foo2", "bar2.json")),
        )

    def test_migrate_mappings(self):
        """Test if mappings are migrated correctly

        mappings like
        {(type, code): symbol} or {(type, code, value): symbol} should migrate
        to {EventCombination: {target: target, symbol: symbol, ...}}
        """
        path = os.path.join(CONFIG_PATH, "presets", "Foo Device", "test.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as file:
            json.dump(
                {
                    "mapping": {
                        f"{EV_KEY},1": "a",
                        f"{EV_KEY}, 2, 1": "BTN_B",  # can be mapped to "gamepad"
                        f"{EV_KEY}, 3, 1": "BTN_1",  # can not be mapped
                        f"{EV_ABS},{ABS_HAT0X},-1": "b",
                        f"{EV_ABS},1,1+{EV_ABS},2,-1+{EV_ABS},3,1": "c",
                        f"{EV_KEY}, 4, 1": ("d", "keyboard"),
                        f"{EV_KEY}, 5, 1": ("e", "foo"),  # unknown target
                        f"{EV_KEY}, 6, 1": ("key(a, b)", "keyboard"),  # broken macro
                        # ignored because broken
                        f"3,1,1,2": "e",
                        f"3": "e",
                        f",,+3,1,2": "g",
                        f"": "h",
                    }
                },
                file,
            )
        migrate()
        # use UIMapping to also load invalid mappings
        preset = Preset(get_preset_path("Foo Device", "test"), UIMapping)
        preset.load()

        self.assertEqual(
            preset.get_mapping(EventCombination([EV_KEY, 1, 1])),
            UIMapping(
                event_combination=EventCombination([EV_KEY, 1, 1]),
                target_uinput="keyboard",
                output_symbol="a",
            ),
        )
        self.assertEqual(
            preset.get_mapping(EventCombination([EV_KEY, 2, 1])),
            UIMapping(
                event_combination=EventCombination([EV_KEY, 2, 1]),
                target_uinput="gamepad",
                output_symbol="BTN_B",
            ),
        )
        self.assertEqual(
            preset.get_mapping(EventCombination([EV_KEY, 3, 1])),
            UIMapping(
                event_combination=EventCombination([EV_KEY, 3, 1]),
                target_uinput="keyboard",
                output_symbol="BTN_1\n# Broken mapping:\n# No target can handle all specified keycodes",
            ),
        )
        self.assertEqual(
            preset.get_mapping(EventCombination([EV_KEY, 4, 1])),
            UIMapping(
                event_combination=EventCombination([EV_KEY, 4, 1]),
                target_uinput="keyboard",
                output_symbol="d",
            ),
        )
        self.assertEqual(
            preset.get_mapping(EventCombination([EV_ABS, ABS_HAT0X, -1])),
            UIMapping(
                event_combination=EventCombination([EV_ABS, ABS_HAT0X, -1]),
                target_uinput="keyboard",
                output_symbol="b",
            ),
        )
        self.assertEqual(
            preset.get_mapping(
                EventCombination(((EV_ABS, 1, 1), (EV_ABS, 2, -1), (EV_ABS, 3, 1))),
            ),
            UIMapping(
                event_combination=EventCombination(
                    ((EV_ABS, 1, 1), (EV_ABS, 2, -1), (EV_ABS, 3, 1)),
                ),
                target_uinput="keyboard",
                output_symbol="c",
            ),
        )
        self.assertEqual(
            preset.get_mapping(EventCombination([EV_KEY, 5, 1])),
            UIMapping(
                event_combination=EventCombination([EV_KEY, 5, 1]),
                target_uinput="foo",
                output_symbol="e",
            ),
        )
        self.assertEqual(
            preset.get_mapping(EventCombination([EV_KEY, 6, 1])),
            UIMapping(
                event_combination=EventCombination([EV_KEY, 6, 1]),
                target_uinput="keyboard",
                output_symbol="key(a, b)",
            ),
        )

        self.assertEqual(8, len(preset))

    def test_migrate_otherwise(self):
        path = os.path.join(CONFIG_PATH, "presets", "Foo Device", "test.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as file:
            json.dump(
                {
                    "mapping": {
                        f"{EV_KEY},1,1": ("otherwise + otherwise", "keyboard"),
                        f"{EV_KEY},2,1": ("bar($otherwise)", "keyboard"),
                        f"{EV_KEY},3,1": ("foo(otherwise=qux)", "keyboard"),
                        f"{EV_KEY},4,1": ("qux(otherwise).bar(otherwise = 1)", "foo"),
                        f"{EV_KEY},5,1": ("foo(otherwise1=2qux)", "keyboard"),
                    }
                },
                file,
            )

        migrate()

        preset = Preset(get_preset_path("Foo Device", "test"), UIMapping)
        preset.load()

        self.assertEqual(
            preset.get_mapping(EventCombination([EV_KEY, 1, 1])),
            UIMapping(
                event_combination=EventCombination([EV_KEY, 1, 1]),
                target_uinput="keyboard",
                output_symbol="otherwise + otherwise",
            ),
        )
        self.assertEqual(
            preset.get_mapping(EventCombination([EV_KEY, 2, 1])),
            UIMapping(
                event_combination=EventCombination([EV_KEY, 2, 1]),
                target_uinput="keyboard",
                output_symbol="bar($otherwise)",
            ),
        )
        self.assertEqual(
            preset.get_mapping(EventCombination([EV_KEY, 3, 1])),
            UIMapping(
                event_combination=EventCombination([EV_KEY, 3, 1]),
                target_uinput="keyboard",
                output_symbol="foo(else=qux)",
            ),
        )
        self.assertEqual(
            preset.get_mapping(EventCombination([EV_KEY, 4, 1])),
            UIMapping(
                event_combination=EventCombination([EV_KEY, 4, 1]),
                target_uinput="foo",
                output_symbol="qux(otherwise).bar(else=1)",
            ),
        )
        self.assertEqual(
            preset.get_mapping(EventCombination([EV_KEY, 5, 1])),
            UIMapping(
                event_combination=EventCombination([EV_KEY, 5, 1]),
                target_uinput="keyboard",
                output_symbol="foo(otherwise1=2qux)",
            ),
        )

    def test_add_version(self):
        path = os.path.join(CONFIG_PATH, "config.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as file:
            file.write("{}")

        migrate()
        self.assertEqual(VERSION, config_version().public)

    def test_update_version(self):
        path = os.path.join(CONFIG_PATH, "config.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as file:
            json.dump({"version": "0.1.0"}, file)

        migrate()
        self.assertEqual(VERSION, config_version().public)

    def test_config_version(self):
        path = os.path.join(CONFIG_PATH, "config.json")
        with open(path, "w") as file:
            file.write("{}")

        self.assertEqual("0.0.0", config_version().public)

        try:
            os.remove(path)
        except FileNotFoundError:
            pass

        self.assertEqual("0.0.0", config_version().public)

    def test_migrate_left_and_right_purpose(self):
        path = os.path.join(CONFIG_PATH, "presets", "Foo Device", "test.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as file:
            json.dump(
                {
                    "gamepad": {
                        "joystick": {
                            "left_purpose": "mouse",
                            "right_purpose": "wheel",
                            "pointer_speed": 50,
                            "x_scroll_speed": 10,
                            "y_scroll_speed": 20,
                        }
                    }
                },
                file,
            )
        migrate()

        preset = Preset(get_preset_path("Foo Device", "test"), UIMapping)
        preset.load()
        # 2 mappings for mouse
        # 2 mappings for wheel
        self.assertEqual(len(preset), 4)
        self.assertEqual(
            preset.get_mapping(EventCombination((EV_ABS, ABS_X, 0))),
            UIMapping(
                event_combination=EventCombination((EV_ABS, ABS_X, 0)),
                target_uinput="mouse",
                output_type=EV_REL,
                output_code=REL_X,
                gain=50 / 100,
            ),
        )
        self.assertEqual(
            preset.get_mapping(EventCombination((EV_ABS, ABS_Y, 0))),
            UIMapping(
                event_combination=EventCombination((EV_ABS, ABS_Y, 0)),
                target_uinput="mouse",
                output_type=EV_REL,
                output_code=REL_Y,
                gain=50 / 100,
            ),
        )
        self.assertEqual(
            preset.get_mapping(EventCombination((EV_ABS, ABS_RX, 0))),
            UIMapping(
                event_combination=EventCombination((EV_ABS, ABS_RX, 0)),
                target_uinput="mouse",
                output_type=EV_REL,
                output_code=REL_HWHEEL_HI_RES,
                gain=10,
            ),
        )
        self.assertEqual(
            preset.get_mapping(EventCombination((EV_ABS, ABS_RY, 0))),
            UIMapping(
                event_combination=EventCombination((EV_ABS, ABS_RY, 0)),
                target_uinput="mouse",
                output_type=EV_REL,
                output_code=REL_WHEEL_HI_RES,
                gain=20,
            ),
        )

    def test_migrate_left_and_right_purpose2(self):
        # same as above, but left and right is swapped

        path = os.path.join(CONFIG_PATH, "presets", "Foo Device", "test.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as file:
            json.dump(
                {
                    "gamepad": {
                        "joystick": {
                            "right_purpose": "mouse",
                            "left_purpose": "wheel",
                            "pointer_speed": 50,
                            "x_scroll_speed": 10,
                            "y_scroll_speed": 20,
                        }
                    }
                },
                file,
            )
        migrate()

        preset = Preset(get_preset_path("Foo Device", "test"), UIMapping)
        preset.load()
        # 2 mappings for mouse
        # 2 mappings for wheel
        self.assertEqual(len(preset), 4)
        self.assertEqual(
            preset.get_mapping(EventCombination((EV_ABS, ABS_RX, 0))),
            UIMapping(
                event_combination=EventCombination((EV_ABS, ABS_RX, 0)),
                target_uinput="mouse",
                output_type=EV_REL,
                output_code=REL_X,
                gain=50 / 100,
            ),
        )
        self.assertEqual(
            preset.get_mapping(EventCombination((EV_ABS, ABS_RY, 0))),
            UIMapping(
                event_combination=EventCombination((EV_ABS, ABS_RY, 0)),
                target_uinput="mouse",
                output_type=EV_REL,
                output_code=REL_Y,
                gain=50 / 100,
            ),
        )
        self.assertEqual(
            preset.get_mapping(EventCombination((EV_ABS, ABS_X, 0))),
            UIMapping(
                event_combination=EventCombination((EV_ABS, ABS_X, 0)),
                target_uinput="mouse",
                output_type=EV_REL,
                output_code=REL_HWHEEL_HI_RES,
                gain=10,
            ),
        )
        self.assertEqual(
            preset.get_mapping(EventCombination((EV_ABS, ABS_Y, 0))),
            UIMapping(
                event_combination=EventCombination((EV_ABS, ABS_Y, 0)),
                target_uinput="mouse",
                output_type=EV_REL,
                output_code=REL_WHEEL_HI_RES,
                gain=20,
            ),
        )


if __name__ == "__main__":
    unittest.main()
