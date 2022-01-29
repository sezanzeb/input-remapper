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


import os
import unittest
import shutil
import json

from evdev.ecodes import EV_KEY, EV_ABS, ABS_HAT0X

from inputremapper.migrations import migrate, config_version
from inputremapper.preset import Preset
from inputremapper.configs.global_config import global_config
from inputremapper.paths import touch, CONFIG_PATH, mkdir, get_preset_path
from inputremapper.key import Key
from inputremapper.user import HOME

from inputremapper.logger import VERSION

from tests.test import quick_cleanup, tmp


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
            self.assertIn("version", moved_config)

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
        if os.path.exists(tmp):
            shutil.rmtree(tmp)

        p1 = os.path.join(tmp, "foo1", "bar1.json")
        p2 = os.path.join(tmp, "foo2", "bar2.json")
        touch(p1)
        touch(p2)

        with open(p1, "w") as f:
            f.write("{}")

        with open(p2, "w") as f:
            f.write("{}")

        migrate()

        self.assertFalse(os.path.exists(os.path.join(tmp, "foo1", "bar1.json")))
        self.assertFalse(os.path.exists(os.path.join(tmp, "foo2", "bar2.json")))

        self.assertTrue(
            os.path.exists(os.path.join(tmp, "presets", "foo1", "bar1.json"))
        )
        self.assertTrue(
            os.path.exists(os.path.join(tmp, "presets", "foo2", "bar2.json"))
        )

    def test_wont_migrate_preset(self):
        if os.path.exists(tmp):
            shutil.rmtree(tmp)

        p1 = os.path.join(tmp, "foo1", "bar1.json")
        p2 = os.path.join(tmp, "foo2", "bar2.json")
        touch(p1)
        touch(p2)

        with open(p1, "w") as f:
            f.write("{}")

        with open(p2, "w") as f:
            f.write("{}")

        # already migrated
        mkdir(os.path.join(tmp, "presets"))

        migrate()

        self.assertTrue(os.path.exists(os.path.join(tmp, "foo1", "bar1.json")))
        self.assertTrue(os.path.exists(os.path.join(tmp, "foo2", "bar2.json")))

        self.assertFalse(
            os.path.exists(os.path.join(tmp, "presets", "foo1", "bar1.json"))
        )
        self.assertFalse(
            os.path.exists(os.path.join(tmp, "presets", "foo2", "bar2.json"))
        )

    def test_migrate_mappings(self):
        """test if mappings are migrated correctly

        mappings like
        {(type, code): symbol} or {(type, code, value): symbol} should migrate to
        {(type, code, value): (symbol, "keyboard")}
        """

        path = os.path.join(tmp, "presets", "Foo Device", "test.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as file:
            json.dump(
                {
                    "mapping": {
                        f"{EV_KEY},1": "a",
                        f"{EV_KEY}, 2, 1": "BTN_B",  # can be mapped to "gamepad"
                        f"{EV_KEY}, 3, 1": "BTN_1",  # can not be mapped
                        f"{EV_KEY}, 4, 1": ("a", "foo"),
                        f"{EV_ABS},{ABS_HAT0X},-1": "b",
                        f"{EV_ABS},1,1+{EV_ABS},2,-1+{EV_ABS},3,1": "c",
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
        loaded = Preset()
        self.assertEqual(loaded.num_saved_keys, 0)
        loaded.load(get_preset_path("Foo Device", "test"))
        self.assertEqual(len(loaded), 6)
        self.assertEqual(loaded.num_saved_keys, 6)

        self.assertEqual(loaded.get_mapping(Key(EV_KEY, 1, 1)), ("a", "keyboard"))
        self.assertEqual(loaded.get_mapping(Key(EV_KEY, 2, 1)), ("BTN_B", "gamepad"))
        self.assertEqual(
            loaded.get_mapping(Key(EV_KEY, 3, 1)),
            (
                "BTN_1\n# Broken mapping:\n# No target can handle all specified keycodes",
                "keyboard",
            ),
        )
        self.assertEqual(loaded.get_mapping(Key(EV_KEY, 4, 1)), ("a", "foo"))
        self.assertEqual(
            loaded.get_mapping(Key(EV_ABS, ABS_HAT0X, -1)), ("b", "keyboard")
        )
        self.assertEqual(
            loaded.get_mapping(Key((EV_ABS, 1, 1), (EV_ABS, 2, -1), Key(EV_ABS, 3, 1))),
            ("c", "keyboard"),
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


if __name__ == "__main__":
    unittest.main()
