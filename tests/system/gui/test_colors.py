#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2025 sezanzeb <b8x45ygc9@mozmail.com>
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

import unittest

import gi


gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GtkSource", "4")
gi.require_version("GLib", "2.0")
from gi.repository import Gdk

from inputremapper.gui.utils import Colors

from tests.lib.test_setup import test_setup
from tests.system.gui.gui_test_base import GuiTestBase


@test_setup
class TestColors(GuiTestBase):
    # requires a running ui, otherwise fails with segmentation faults
    def test_get_color_falls_back(self):
        fallback = Gdk.RGBA(0, 0.5, 1, 0.8)

        color = Colors.get_color(["doesnt_exist_1234"], fallback)

        self.assertIsInstance(color, Gdk.RGBA)
        self.assertAlmostEqual(color.red, fallback.red, delta=0.01)
        self.assertAlmostEqual(color.green, fallback.green, delta=0.01)
        self.assertAlmostEqual(color.blue, fallback.blue, delta=0.01)
        self.assertAlmostEqual(color.alpha, fallback.alpha, delta=0.01)

    def test_get_color_works(self):
        fallback = Gdk.RGBA(1, 0, 1, 0.1)

        color = Colors.get_color(
            ["accent_bg_color", "theme_selected_bg_color"], fallback
        )

        self.assertIsInstance(color, Gdk.RGBA)
        self.assertNotAlmostEqual(color.red, fallback.red, delta=0.01)
        self.assertNotAlmostEqual(color.green, fallback.blue, delta=0.01)
        self.assertNotAlmostEqual(color.blue, fallback.green, delta=0.01)
        self.assertNotAlmostEqual(color.alpha, fallback.alpha, delta=0.01)

    def _test_color_wont_fallback(self, get_color, fallback):
        color = get_color()
        self.assertIsInstance(color, Gdk.RGBA)
        if (
            (abs(color.green - fallback.green) < 0.01)
            and (abs(color.red - fallback.red) < 0.01)
            and (abs(color.blue - fallback.blue) < 0.01)
            and (abs(color.alpha - fallback.alpha) < 0.01)
        ):
            raise AssertionError(
                f"Color {color.to_string()} is similar to {fallback.toString()}"
            )

    def test_get_colors(self):
        self._test_color_wont_fallback(Colors.get_accent_color, Colors.fallback_accent)
        self._test_color_wont_fallback(Colors.get_border_color, Colors.fallback_border)
        self._test_color_wont_fallback(
            Colors.get_background_color, Colors.fallback_background
        )
        self._test_color_wont_fallback(Colors.get_base_color, Colors.fallback_base)
        self._test_color_wont_fallback(Colors.get_font_color, Colors.fallback_font)


if __name__ == "__main__":
    unittest.main()
