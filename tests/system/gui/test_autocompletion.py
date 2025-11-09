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

import time
import unittest

import gi

from inputremapper.gui.autocompletion import (
    get_incomplete_parameter,
    get_incomplete_function_name,
)

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GtkSource", "4")
gi.require_version("GLib", "2.0")
from gi.repository import Gtk, Gdk

from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.gui.utils import gtk_iteration

from tests.lib.test_setup import test_setup
from tests.system.gui.gui_test_base import GuiTestBase


@test_setup
class TestAutocompletion(GuiTestBase):
    def press_key(self, keyval):
        event = Gdk.EventKey()
        event.keyval = keyval
        self.user_interface.autocompletion.navigate(None, event)

    def get_suggestions(self, autocompletion):
        return [
            row.get_children()[0].get_text()
            for row in autocompletion.list_box.get_children()
        ]

    def test_get_incomplete_parameter(self):
        def test(text, expected):
            text_view = Gtk.TextView()
            Gtk.TextView.do_insert_at_cursor(text_view, text)
            text_iter = text_view.get_iter_at_location(0, 0)[1]
            text_iter.set_offset(len(text))
            self.assertEqual(get_incomplete_parameter(text_iter), expected)

        test("bar(foo", "foo")
        test("bar(a=foo", "foo")
        test("bar(qux, foo", "foo")
        test("foo", "foo")
        test("bar + foo", "foo")

    def test_get_incomplete_function_name(self):
        def test(text, expected):
            text_view = Gtk.TextView()
            Gtk.TextView.do_insert_at_cursor(text_view, text)
            text_iter = text_view.get_iter_at_location(0, 0)[1]
            text_iter.set_offset(len(text))
            self.assertEqual(get_incomplete_function_name(text_iter), expected)

        test("bar().foo", "foo")
        test("bar()\n.foo", "foo")
        test("bar().\nfoo", "foo")
        test("bar(\nfoo", "foo")
        test("bar(\nqux=foo", "foo")
        test("bar(KEY_A,\nfoo", "foo")
        test("foo", "foo")

    def test_autocomplete_names(self):
        autocompletion = self.user_interface.autocompletion

        def setup(text):
            self.set_focus(self.code_editor)
            self.code_editor.get_buffer().set_text("")
            Gtk.TextView.do_insert_at_cursor(self.code_editor, text)
            self.throttle(200)
            text_iter = self.code_editor.get_iter_at_location(0, 0)[1]
            text_iter.set_offset(len(text))

        setup("disa")
        self.assertNotIn("KEY_A", self.get_suggestions(autocompletion))
        self.assertIn("disable", self.get_suggestions(autocompletion))

        setup(" + _A")
        self.assertIn("KEY_A", self.get_suggestions(autocompletion))
        self.assertNotIn("disable", self.get_suggestions(autocompletion))

    def test_autocomplete_key(self):
        self.controller.update_mapping(output_symbol="")
        gtk_iteration()

        self.set_focus(self.code_editor)
        self.code_editor.get_buffer().set_text("")

        complete_key_name = "Test_Foo_Bar"

        keyboard_layout.clear()
        keyboard_layout._set(complete_key_name, 1)
        keyboard_layout._set("KEY_A", 30)  # we need this for the UIMapping to work

        # it can autocomplete a combination inbetween other things
        incomplete = "qux_1\n +  + qux_2"
        Gtk.TextView.do_insert_at_cursor(self.code_editor, incomplete)
        Gtk.TextView.do_move_cursor(
            self.code_editor,
            Gtk.MovementStep.VISUAL_POSITIONS,
            -8,
            False,
        )

        Gtk.TextView.do_insert_at_cursor(self.code_editor, "foo")
        self.throttle(200)
        gtk_iteration()

        autocompletion = self.user_interface.autocompletion
        self.assertTrue(autocompletion.visible)

        self.press_key(Gdk.KEY_Down)
        self.press_key(Gdk.KEY_Return)
        self.throttle(200)
        gtk_iteration()

        # the first suggestion should have been selected

        modified_symbol = self.get_code_input()
        self.assertEqual(modified_symbol, f"qux_1\n + {complete_key_name} + qux_2")

        # try again, but a whitespace completes the word and so no autocompletion
        # should be shown
        Gtk.TextView.do_insert_at_cursor(self.code_editor, " + foo ")

        time.sleep(0.11)
        gtk_iteration()

        self.assertFalse(autocompletion.visible)

    def test_autocomplete_function(self):
        self.controller.update_mapping(output_symbol="")
        gtk_iteration()

        source_view = self.focus_source_view()

        incomplete = "key(KEY_A).\nepea"
        Gtk.TextView.do_insert_at_cursor(source_view, incomplete)

        time.sleep(0.11)
        gtk_iteration()

        autocompletion = self.user_interface.autocompletion
        self.assertTrue(autocompletion.visible)

        self.press_key(Gdk.KEY_Down)
        self.press_key(Gdk.KEY_Return)

        # the first suggestion should have been selected
        modified_symbol = self.get_code_input()
        self.assertEqual(modified_symbol, "key(KEY_A).\nrepeat")

    def test_close_autocompletion(self):
        self.controller.update_mapping(output_symbol="")
        gtk_iteration()

        source_view = self.focus_source_view()

        Gtk.TextView.do_insert_at_cursor(source_view, "KEY_")

        time.sleep(0.11)
        gtk_iteration()

        autocompletion = self.user_interface.autocompletion
        self.assertTrue(autocompletion.visible)

        self.press_key(Gdk.KEY_Down)
        self.press_key(Gdk.KEY_Escape)

        self.assertFalse(autocompletion.visible)

        symbol = self.get_code_input()
        self.assertEqual(symbol, "KEY_")

    def test_writing_still_works(self):
        self.controller.update_mapping(output_symbol="")
        gtk_iteration()
        source_view = self.focus_source_view()

        Gtk.TextView.do_insert_at_cursor(source_view, "KEY_")

        autocompletion = self.user_interface.autocompletion

        time.sleep(0.11)
        gtk_iteration()
        self.assertTrue(autocompletion.visible)

        # writing still works while an entry is selected
        self.press_key(Gdk.KEY_Down)

        Gtk.TextView.do_insert_at_cursor(source_view, "A")

        time.sleep(0.11)
        gtk_iteration()
        self.assertTrue(autocompletion.visible)

        Gtk.TextView.do_insert_at_cursor(source_view, "1234foobar")

        time.sleep(0.11)
        gtk_iteration()
        # no key matches this completion, so it closes again
        self.assertFalse(autocompletion.visible)

    def test_cycling(self):
        self.controller.update_mapping(output_symbol="")
        gtk_iteration()
        source_view = self.focus_source_view()

        Gtk.TextView.do_insert_at_cursor(source_view, "KEY_")

        autocompletion = self.user_interface.autocompletion

        time.sleep(0.11)
        gtk_iteration()
        self.assertTrue(autocompletion.visible)

        self.assertEqual(
            autocompletion.scrolled_window.get_vadjustment().get_value(), 0
        )

        # cycle to the end of the list because there is no element higher than index 0
        self.press_key(Gdk.KEY_Up)
        self.assertGreater(
            autocompletion.scrolled_window.get_vadjustment().get_value(), 0
        )

        # go back to the start, because it can't go down further
        self.press_key(Gdk.KEY_Down)
        self.assertEqual(
            autocompletion.scrolled_window.get_vadjustment().get_value(), 0
        )


if __name__ == "__main__":
    unittest.main()
