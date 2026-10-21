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

import time
from unittest.mock import MagicMock

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk

from inputremapper.configs.mapping import Mapping
from inputremapper.gui.components.editor import (
    TransformationDrawArea,
)
from inputremapper.gui.messages.message_data import (
    MappingData,
)
from inputremapper.gui.utils import gtk_iteration
from tests.lib.spy import spy
from tests.lib.test_setup import test_setup
from tests.system.gui.test_components.base import ComponentBaseTest


@test_setup
class TestTransformationDrawArea(ComponentBaseTest):
    def setUp(self) -> None:
        super().setUp()
        self.gui = Gtk.Window()
        self.draw_area = Gtk.DrawingArea()
        self.gui.add(self.draw_area)
        self.transform_draw_area = TransformationDrawArea(
            self.message_broker,
            self.controller_mock,
            self.draw_area,
        )

    def test_draws_transform(self):
        with spy(self.transform_draw_area, "_transformation") as mock:
            # show the window, it takes some time and iterations until it pops up
            self.gui.show_all()
            for _ in range(5):
                gtk_iteration()
                time.sleep(0.01)

            mock.assert_called()

    def test_updates_transform_when_mapping_updates(self):
        old_tf = self.transform_draw_area._transformation
        self.message_broker.publish(MappingData(Mapping(gain=2)))
        self.assertIsNot(old_tf, self.transform_draw_area._transformation)

    def test_redraws_when_mapping_updates(self):
        self.gui.show_all()
        gtk_iteration(20)
        mock = MagicMock()
        self.draw_area.connect("draw", mock)
        self.message_broker.publish(MappingData(Mapping(gain=2)))
        gtk_iteration(20)
        mock.assert_called()
