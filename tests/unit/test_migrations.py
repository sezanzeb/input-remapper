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
import os
import shutil
import unittest

import pkg_resources
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

from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.configs.mapping import UIMapping
from inputremapper.configs.migrations import Migrations
from inputremapper.configs.paths import PathUtils
from inputremapper.configs.preset import Preset
from inputremapper.injection.global_uinputs import GlobalUInputs, UInput
from inputremapper.logging.logger import VERSION
from inputremapper.user import UserUtils
from tests.lib.test_setup import test_setup
from tests.lib.tmp import tmp


@test_setup
class TestMigrations(unittest.TestCase):
    def setUp(self):
        # some extra care to ensure those tests are not destroying actual presets
        self.assertTrue(UserUtils.home.startswith("/tmp"))
        self.assertTrue(PathUtils.config_path().startswith("/tmp"))
        self.assertTrue(PathUtils.get_preset_path().startswith("/tmp"))
        self.assertTrue(PathUtils.get_preset_path("foo", "bar").startswith("/tmp"))
        self.assertTrue(PathUtils.get_config_path().startswith("/tmp"))
        self.assertTrue(PathUtils.get_config_path("foo").startswith("/tmp"))

        self.v1_dir = os.path.join(UserUtils.home, ".config", "input-remapper")
        self.beta_dir = os.path.join(
            UserUtils.home, ".config", "input-remapper", "beta_1.6.0-beta"
        )

        global_uinputs = GlobalUInputs(UInput)
        global_uinputs.prepare_all()
        self.migrations = Migrations(global_uinputs)

    def test_migrate_suffix(self):
        old = os.path.join(PathUtils.config_path(), "config")
        new = os.path.join(PathUtils.config_path(), "config.json")

        try:
            os.remove(new)
        except FileNotFoundError:
            pass

        PathUtils.touch(old)
        with open(old, "w") as f:
            f.write("{}")

        self.migrations.migrate()
        self.assertTrue(os.path.exists(new))
        self.assertFalse(os.path.exists(old))

    def test_rename_config(self):
        old = os.path.join(UserUtils.home, ".config", "key-mapper")
        new = PathUtils.config_path()

        # we are not destroying our actual config files with this test
        self.assertTrue(new.startswith(tmp), f'Expected "{new}" to start with "{tmp}"')

        try:
            shutil.rmtree(new)
        except FileNotFoundError:
            pass

        old_config_json = os.path.join(old, "config.json")
        PathUtils.touch(old_config_json)
        with open(old_config_json, "w") as f:
            f.write('{"foo":"bar"}')

        self.migrations.migrate()

        self.assertTrue(os.path.exists(new))
        self.assertFalse(os.path.exists(old))

        new_config_json = os.path.join(new, "config.json")
        with open(new_config_json, "r") as f:
            moved_config = json.loads(f.read())
            self.assertEqual(moved_config["foo"], "bar")

    def test_wont_migrate_suffix(self):
        old = os.path.join(PathUtils.config_path(), "config")
        new = os.path.join(PathUtils.config_path(), "config.json")

        PathUtils.touch(new)
        with open(new, "w") as f:
            f.write("{}")

        PathUtils.touch(old)
        with open(old, "w") as f:
            f.write("{}")

        self.migrations.migrate()
        self.assertTrue(os.path.exists(new))
        self.assertTrue(os.path.exists(old))

    def test_migrate_preset(self):
        if os.path.exists(PathUtils.config_path()):
            shutil.rmtree(PathUtils.config_path())

        p1 = os.path.join(PathUtils.config_path(), "foo1", "bar1.json")
        p2 = os.path.join(PathUtils.config_path(), "foo2", "bar2.json")
        PathUtils.touch(p1)
        PathUtils.touch(p2)

        with open(p1, "w") as f:
            f.write("{}")

        with open(p2, "w") as f:
            f.write("{}")

        self.migrations.migrate()

        self.assertFalse(
            os.path.exists(os.path.join(PathUtils.config_path(), "foo1", "bar1.json"))
        )
        self.assertFalse(
            os.path.exists(os.path.join(PathUtils.config_path(), "foo2", "bar2.json"))
        )

        self.assertTrue(
            os.path.exists(
                os.path.join(PathUtils.config_path(), "presets", "foo1", "bar1.json")
            ),
        )
        self.assertTrue(
            os.path.exists(
                os.path.join(PathUtils.config_path(), "presets", "foo2", "bar2.json")
            ),
        )

    def test_wont_migrate_preset(self):
        if os.path.exists(PathUtils.config_path()):
            shutil.rmtree(PathUtils.config_path())

        p1 = os.path.join(PathUtils.config_path(), "foo1", "bar1.json")
        p2 = os.path.join(PathUtils.config_path(), "foo2", "bar2.json")
        PathUtils.touch(p1)
        PathUtils.touch(p2)

        with open(p1, "w") as f:
            f.write("{}")

        with open(p2, "w") as f:
            f.write("{}")

        # already migrated
        PathUtils.mkdir(os.path.join(PathUtils.config_path(), "presets"))

        self.migrations.migrate()

        self.assertTrue(
            os.path.exists(os.path.join(PathUtils.config_path(), "foo1", "bar1.json"))
        )
        self.assertTrue(
            os.path.exists(os.path.join(PathUtils.config_path(), "foo2", "bar2.json"))
        )

        self.assertFalse(
            os.path.exists(
                os.path.join(PathUtils.config_path(), "presets", "foo1", "bar1.json")
            ),
        )
        self.assertFalse(
            os.path.exists(
                os.path.join(PathUtils.config_path(), "presets", "foo2", "bar2.json")
            ),
        )

    def test_migrate_mappings(self):
        """Test if mappings are migrated correctly

        mappings like
        {(type, code): symbol} or {(type, code, value): symbol} should migrate
        to {InputCombination: {target: target, symbol: symbol, ...}}
        """
        path = os.path.join(
            PathUtils.config_path(), "presets", "Foo Device", "test.json"
        )
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
        self.migrations.migrate()
        # use UIMapping to also load invalid mappings
        preset = Preset(PathUtils.get_preset_path("Foo Device", "test"), UIMapping)
        preset.load()

        self.assertEqual(
            preset.get_mapping(InputCombination([InputConfig(type=EV_KEY, code=1)])),
            UIMapping(
                input_combination=InputCombination([InputConfig(type=EV_KEY, code=1)]),
                target_uinput="keyboard",
                output_symbol="a",
            ),
        )
        self.assertEqual(
            preset.get_mapping(InputCombination([InputConfig(type=EV_KEY, code=2)])),
            UIMapping(
                input_combination=InputCombination([InputConfig(type=EV_KEY, code=2)]),
                target_uinput="gamepad",
                output_symbol="BTN_B",
            ),
        )
        self.assertEqual(
            preset.get_mapping(InputCombination([InputConfig(type=EV_KEY, code=3)])),
            UIMapping(
                input_combination=InputCombination([InputConfig(type=EV_KEY, code=3)]),
                target_uinput="keyboard",
                output_symbol="BTN_1\n# Broken mapping:\n# No target can handle all specified keycodes",
            ),
        )
        self.assertEqual(
            preset.get_mapping(InputCombination([InputConfig(type=EV_KEY, code=4)])),
            UIMapping(
                input_combination=InputCombination([InputConfig(type=EV_KEY, code=4)]),
                target_uinput="keyboard",
                output_symbol="d",
            ),
        )
        self.assertEqual(
            preset.get_mapping(
                InputCombination(
                    [InputConfig(type=EV_ABS, code=ABS_HAT0X, analog_threshold=-1)]
                )
            ),
            UIMapping(
                input_combination=InputCombination(
                    [InputConfig(type=EV_ABS, code=ABS_HAT0X, analog_threshold=-1)]
                ),
                target_uinput="keyboard",
                output_symbol="b",
            ),
        )
        self.assertEqual(
            preset.get_mapping(
                InputCombination(
                    InputCombination.from_tuples(
                        (EV_ABS, 1, 1), (EV_ABS, 2, -1), (EV_ABS, 3, 1)
                    )
                ),
            ),
            UIMapping(
                input_combination=InputCombination(
                    InputCombination.from_tuples(
                        (EV_ABS, 1, 1), (EV_ABS, 2, -1), (EV_ABS, 3, 1)
                    ),
                ),
                target_uinput="keyboard",
                output_symbol="c",
            ),
        )
        self.assertEqual(
            preset.get_mapping(InputCombination([InputConfig(type=EV_KEY, code=5)])),
            UIMapping(
                input_combination=InputCombination([InputConfig(type=EV_KEY, code=5)]),
                target_uinput="foo",
                output_symbol="e",
            ),
        )
        self.assertEqual(
            preset.get_mapping(InputCombination([InputConfig(type=EV_KEY, code=6)])),
            UIMapping(
                input_combination=InputCombination([InputConfig(type=EV_KEY, code=6)]),
                target_uinput="keyboard",
                output_symbol="key(a, b)",
            ),
        )

        self.assertEqual(8, len(preset))

    def test_migrate_otherwise(self):
        path = os.path.join(
            PathUtils.config_path(), "presets", "Foo Device", "test.json"
        )
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

        self.migrations.migrate()

        preset = Preset(PathUtils.get_preset_path("Foo Device", "test"), UIMapping)
        preset.load()

        self.assertEqual(
            preset.get_mapping(InputCombination([InputConfig(type=EV_KEY, code=1)])),
            UIMapping(
                input_combination=InputCombination([InputConfig(type=EV_KEY, code=1)]),
                target_uinput="keyboard",
                output_symbol="otherwise + otherwise",
            ),
        )
        self.assertEqual(
            preset.get_mapping(InputCombination([InputConfig(type=EV_KEY, code=2)])),
            UIMapping(
                input_combination=InputCombination([InputConfig(type=EV_KEY, code=2)]),
                target_uinput="keyboard",
                output_symbol="bar($otherwise)",
            ),
        )
        self.assertEqual(
            preset.get_mapping(InputCombination([InputConfig(type=EV_KEY, code=3)])),
            UIMapping(
                input_combination=InputCombination([InputConfig(type=EV_KEY, code=3)]),
                target_uinput="keyboard",
                output_symbol="foo(else=qux)",
            ),
        )
        self.assertEqual(
            preset.get_mapping(InputCombination([InputConfig(type=EV_KEY, code=4)])),
            UIMapping(
                input_combination=InputCombination([InputConfig(type=EV_KEY, code=4)]),
                target_uinput="foo",
                output_symbol="qux(otherwise).bar(else=1)",
            ),
        )
        self.assertEqual(
            preset.get_mapping(InputCombination([InputConfig(type=EV_KEY, code=5)])),
            UIMapping(
                input_combination=InputCombination([InputConfig(type=EV_KEY, code=5)]),
                target_uinput="keyboard",
                output_symbol="foo(otherwise1=2qux)",
            ),
        )

    def test_add_version(self):
        path = os.path.join(PathUtils.config_path(), "config.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as file:
            file.write("{}")

        self.migrations.migrate()
        self.assertEqual(
            pkg_resources.parse_version(VERSION), self.migrations.config_version()
        )

    def test_update_version(self):
        path = os.path.join(PathUtils.config_path(), "config.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as file:
            json.dump({"version": "0.1.0"}, file)

        self.migrations.migrate()
        self.assertEqual(
            pkg_resources.parse_version(VERSION), self.migrations.config_version()
        )

    def test_config_version(self):
        path = os.path.join(PathUtils.config_path(), "config.json")
        with open(path, "w") as file:
            file.write("{}")

        self.assertEqual("0.0.0", self.migrations.config_version().public)

        try:
            os.remove(path)
        except FileNotFoundError:
            pass

        self.assertEqual("0.0.0", self.migrations.config_version().public)

    def test_migrate_left_and_right_purpose(self):
        path = os.path.join(
            PathUtils.config_path(), "presets", "Foo Device", "test.json"
        )
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
        self.migrations.migrate()

        preset = Preset(PathUtils.get_preset_path("Foo Device", "test"), UIMapping)
        preset.load()
        # 2 mappings for mouse
        # 2 mappings for wheel
        self.assertEqual(len(preset), 4)
        self.assertEqual(
            preset.get_mapping(
                InputCombination([InputConfig(type=EV_ABS, code=ABS_X)])
            ),
            UIMapping(
                input_combination=InputCombination(
                    [InputConfig(type=EV_ABS, code=ABS_X)]
                ),
                target_uinput="mouse",
                output_type=EV_REL,
                output_code=REL_X,
                gain=50 / 100,
            ),
        )
        self.assertEqual(
            preset.get_mapping(
                InputCombination([InputConfig(type=EV_ABS, code=ABS_Y)])
            ),
            UIMapping(
                input_combination=InputCombination(
                    [InputConfig(type=EV_ABS, code=ABS_Y)]
                ),
                target_uinput="mouse",
                output_type=EV_REL,
                output_code=REL_Y,
                gain=50 / 100,
            ),
        )
        self.assertEqual(
            preset.get_mapping(
                InputCombination([InputConfig(type=EV_ABS, code=ABS_RX)])
            ),
            UIMapping(
                input_combination=InputCombination(
                    [InputConfig(type=EV_ABS, code=ABS_RX)]
                ),
                target_uinput="mouse",
                output_type=EV_REL,
                output_code=REL_HWHEEL_HI_RES,
                gain=10,
            ),
        )
        self.assertEqual(
            preset.get_mapping(
                InputCombination([InputConfig(type=EV_ABS, code=ABS_RY)])
            ),
            UIMapping(
                input_combination=InputCombination(
                    [InputConfig(type=EV_ABS, code=ABS_RY)]
                ),
                target_uinput="mouse",
                output_type=EV_REL,
                output_code=REL_WHEEL_HI_RES,
                gain=20,
            ),
        )

    def test_migrate_left_and_right_purpose2(self):
        # same as above, but left and right is swapped

        path = os.path.join(
            PathUtils.config_path(), "presets", "Foo Device", "test.json"
        )
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
        self.migrations.migrate()

        preset = Preset(PathUtils.get_preset_path("Foo Device", "test"), UIMapping)
        preset.load()
        # 2 mappings for mouse
        # 2 mappings for wheel
        self.assertEqual(len(preset), 4)
        self.assertEqual(
            preset.get_mapping(
                InputCombination([InputConfig(type=EV_ABS, code=ABS_RX)])
            ),
            UIMapping(
                input_combination=InputCombination(
                    [InputConfig(type=EV_ABS, code=ABS_RX)]
                ),
                target_uinput="mouse",
                output_type=EV_REL,
                output_code=REL_X,
                gain=50 / 100,
            ),
        )
        self.assertEqual(
            preset.get_mapping(
                InputCombination([InputConfig(type=EV_ABS, code=ABS_RY)])
            ),
            UIMapping(
                input_combination=InputCombination(
                    [InputConfig(type=EV_ABS, code=ABS_RY)]
                ),
                target_uinput="mouse",
                output_type=EV_REL,
                output_code=REL_Y,
                gain=50 / 100,
            ),
        )
        self.assertEqual(
            preset.get_mapping(
                InputCombination([InputConfig(type=EV_ABS, code=ABS_X)])
            ),
            UIMapping(
                input_combination=InputCombination(
                    [InputConfig(type=EV_ABS, code=ABS_X)]
                ),
                target_uinput="mouse",
                output_type=EV_REL,
                output_code=REL_HWHEEL_HI_RES,
                gain=10,
            ),
        )
        self.assertEqual(
            preset.get_mapping(
                InputCombination([InputConfig(type=EV_ABS, code=ABS_Y)])
            ),
            UIMapping(
                input_combination=InputCombination(
                    [InputConfig(type=EV_ABS, code=ABS_Y)]
                ),
                target_uinput="mouse",
                output_type=EV_REL,
                output_code=REL_WHEEL_HI_RES,
                gain=20,
            ),
        )

    def _create_v1_setup(self):
        """Create all files needed to mimic an outdated v1 configuration."""
        device_name = "device_name"

        PathUtils.mkdir(os.path.join(self.v1_dir, "presets", device_name))
        v1_config = {"autoload": {device_name: "foo"}, "version": "1.0"}
        with open(os.path.join(self.v1_dir, "config.json"), "w") as file:
            json.dump(v1_config, file)
        # insert something outdated that will be migrated, to ensure the files are
        # first copied and then migrated.
        with open(
            os.path.join(self.v1_dir, "presets", device_name, "foo.json"), "w"
        ) as file:
            json.dump({"mapping": {f"{EV_KEY},1": "a"}}, file)

    def _create_beta_setup(self):
        """Create all files needed to mimic a beta configuration."""
        device_name = "device_name"

        # same here, but a different contents to tell the difference
        PathUtils.mkdir(os.path.join(self.beta_dir, "presets", device_name))
        beta_config = {"autoload": {device_name: "bar"}, "version": "1.6"}
        with open(os.path.join(self.beta_dir, "config.json"), "w") as file:
            json.dump(beta_config, file)
        with open(
            os.path.join(self.beta_dir, "presets", device_name, "bar.json"), "w"
        ) as file:
            json.dump(
                [
                    {
                        "input_combination": [
                            {"type": EV_KEY, "code": 1},
                        ],
                        "target_uinput": "keyboard",
                        "output_symbol": "b",
                        "mapping_type": "key_macro",
                    }
                ],
                file,
            )

    def test_prioritize_v1_over_beta_configs(self):
        # if both v1 and beta presets and config exist, migrate v1
        PathUtils.remove(PathUtils.get_config_path())

        device_name = "device_name"
        self._create_v1_setup()
        self._create_beta_setup()

        self.assertFalse(os.path.exists(PathUtils.get_preset_path(device_name, "foo")))
        self.assertFalse(os.path.exists(PathUtils.get_config_path("config.json")))

        self.migrations.migrate()

        self.assertTrue(os.path.exists(PathUtils.get_preset_path(device_name, "foo")))
        self.assertTrue(os.path.exists(PathUtils.get_config_path("config.json")))
        self.assertFalse(os.path.exists(PathUtils.get_preset_path(device_name, "bar")))

        # expect all original files to still exist
        self.assertTrue(os.path.join(self.v1_dir, "config.json"))
        self.assertTrue(os.path.join(self.v1_dir, "presets", "foo.json"))
        self.assertTrue(os.path.join(self.beta_dir, "config.json"))
        self.assertTrue(os.path.join(self.beta_dir, "presets", "bar.json"))

        # v1 configs should be in the v2 dir now, and migrated
        with open(PathUtils.get_config_path("config.json"), "r") as f:
            config_json = json.load(f)
            self.assertDictEqual(
                config_json, {"autoload": {device_name: "foo"}, "version": VERSION}
            )
        with open(PathUtils.get_preset_path(device_name, "foo.json"), "r") as f:
            os.system(f'cat { PathUtils.get_preset_path(device_name, "foo.json") }')
            preset_foo_json = json.load(f)
            self.assertEqual(
                preset_foo_json,
                [
                    {
                        "input_combination": [
                            {"type": EV_KEY, "code": 1},
                        ],
                        "target_uinput": "keyboard",
                        "output_symbol": "a",
                        "mapping_type": "key_macro",
                    }
                ],
            )

    def test_copy_over_beta_configs(self):
        # same as test_prioritize_v1_over_beta_configs, but only create the beta
        # directory without any v1 presets.
        PathUtils.remove(PathUtils.get_config_path())

        device_name = "device_name"
        self._create_beta_setup()

        self.assertFalse(os.path.exists(PathUtils.get_preset_path(device_name, "bar")))
        self.assertFalse(os.path.exists(PathUtils.get_config_path("config.json")))

        self.migrations.migrate()

        self.assertTrue(os.path.exists(PathUtils.get_preset_path(device_name, "bar")))
        self.assertTrue(os.path.exists(PathUtils.get_config_path("config.json")))

        # expect all original files to still exist
        self.assertTrue(os.path.join(self.beta_dir, "config.json"))
        self.assertTrue(os.path.join(self.beta_dir, "presets", "bar.json"))

        # beta configs should be in the v2 dir now
        with open(PathUtils.get_config_path("config.json"), "r") as f:
            config_json = json.load(f)
            self.assertDictEqual(
                config_json, {"autoload": {device_name: "bar"}, "version": VERSION}
            )
        with open(PathUtils.get_preset_path(device_name, "bar.json"), "r") as f:
            os.system(f'cat { PathUtils.get_preset_path(device_name, "bar.json") }')
            preset_foo_json = json.load(f)
            self.assertEqual(
                preset_foo_json,
                [
                    {
                        "input_combination": [
                            {"type": EV_KEY, "code": 1},
                        ],
                        "target_uinput": "keyboard",
                        "output_symbol": "b",
                        "mapping_type": "key_macro",
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()
