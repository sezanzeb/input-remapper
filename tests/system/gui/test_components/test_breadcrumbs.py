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


import gi
from evdev.ecodes import KEY_A, KEY_B

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk

from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.configs.mapping import Mapping
from inputremapper.gui.components.common import Breadcrumbs
from inputremapper.gui.messages.message_data import (
    GroupData,
    MappingData,
    PresetData,
)
from tests.lib.test_setup import test_setup
from tests.system.gui.test_components.base import ComponentBaseTest


@test_setup
class TestBreadcrumbs(ComponentBaseTest):
    def test_breadcrumbs(self):
        self.label_1 = Gtk.Label()
        self.label_2 = Gtk.Label()
        self.label_3 = Gtk.Label()
        self.label_4 = Gtk.Label()
        self.label_5 = Gtk.Label()

        Breadcrumbs(
            self.message_broker,
            self.label_1,
            show_device_group=False,
            show_preset=False,
            show_mapping=False,
        )
        Breadcrumbs(
            self.message_broker,
            self.label_2,
            show_device_group=True,
            show_preset=False,
            show_mapping=False,
        )
        Breadcrumbs(
            self.message_broker,
            self.label_3,
            show_device_group=True,
            show_preset=True,
            show_mapping=False,
        )
        Breadcrumbs(
            self.message_broker,
            self.label_4,
            show_device_group=True,
            show_preset=True,
            show_mapping=True,
        )
        Breadcrumbs(
            self.message_broker,
            self.label_5,
            show_device_group=False,
            show_preset=False,
            show_mapping=True,
        )

        self.assertEqual(self.label_1.get_text(), "")
        self.assertEqual(self.label_2.get_text(), "?")
        self.assertEqual(self.label_3.get_text(), "?  /  ?")
        self.assertEqual(self.label_4.get_text(), "?  /  ?  /  ?")
        self.assertEqual(self.label_5.get_text(), "?")

        self.message_broker.publish(PresetData("preset", None))

        self.assertEqual(self.label_1.get_text(), "")
        self.assertEqual(self.label_2.get_text(), "?")
        self.assertEqual(self.label_3.get_text(), "?  /  preset")
        self.assertEqual(self.label_4.get_text(), "?  /  preset  /  ?")
        self.assertEqual(self.label_5.get_text(), "?")

        self.message_broker.publish(GroupData("group", ()))

        self.assertEqual(self.label_1.get_text(), "")
        self.assertEqual(self.label_2.get_text(), "group")
        self.assertEqual(self.label_3.get_text(), "group  /  preset")
        self.assertEqual(self.label_4.get_text(), "group  /  preset  /  ?")
        self.assertEqual(self.label_5.get_text(), "?")

        self.message_broker.publish(MappingData(Mapping()))

        self.assertEqual(self.label_1.get_text(), "")
        self.assertEqual(self.label_2.get_text(), "group")
        self.assertEqual(self.label_3.get_text(), "group  /  preset")
        self.assertEqual(self.label_4.get_text(), "group  /  preset  /  Empty Mapping")
        self.assertEqual(self.label_5.get_text(), "Empty Mapping")

        self.message_broker.publish(MappingData(Mapping(name="mapping")))
        self.assertEqual(self.label_4.get_text(), "group  /  preset  /  mapping")
        self.assertEqual(self.label_5.get_text(), "mapping")

        combination = InputCombination(
            (
                InputConfig(type=1, code=KEY_A),
                InputConfig(type=1, code=KEY_B),
            )
        )
        self.message_broker.publish(MappingData(Mapping(input_combination=combination)))
        self.assertEqual(self.label_4.get_text(), "group  /  preset  /  a + b")
        self.assertEqual(self.label_5.get_text(), "a + b")

        combination = InputCombination([InputConfig(type=1, code=KEY_A)])
        self.message_broker.publish(
            MappingData(Mapping(name="qux", input_combination=combination))
        )
        self.assertEqual(self.label_4.get_text(), "group  /  preset  /  qux")
        self.assertEqual(self.label_5.get_text(), "qux")
