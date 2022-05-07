#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2022 sezanzeb <proxima@sezanzeb.de>
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


"""Autocompletion for the editor."""


import re

from gi.repository import Gdk, Gtk, GLib, GObject
from evdev.ecodes import EV_KEY

from inputremapper.configs.system_mapping import system_mapping
from inputremapper.injection.macros.parse import (
    FUNCTIONS,
    get_macro_argument_names,
    remove_comments,
)
from inputremapper.injection.global_uinputs import global_uinputs
from inputremapper.logger import logger


# no deprecated shorthand function-names
FUNCTION_NAMES = [name for name in FUNCTIONS.keys() if len(name) > 1]
# no deprecated functions
FUNCTION_NAMES.remove("ifeq")


def _get_left_text(iter):
    buffer = iter.get_buffer()
    result = buffer.get_text(buffer.get_start_iter(), iter, True)
    result = remove_comments(result)
    result = result.replace("\n", " ")
    return result.lower()


# regex to search for the beginning of a...
PARAMETER = r".*?[(,=+]\s*"
FUNCTION_CHAIN = r".*?\)\s*\.\s*"


def get_incomplete_function_name(iter):
    """Get the word that is written left to the TextIter."""
    left_text = _get_left_text(iter)

    # match foo in:
    #  bar().foo
    #  bar()\n.foo
    #  bar().\nfoo
    #  bar(\nfoo
    #  bar(\nqux=foo
    #  bar(KEY_A,\nfoo
    #  foo
    match = re.match(rf"(?:{FUNCTION_CHAIN}|{PARAMETER}|^)(\w+)$", left_text)

    if match is None:
        return ""

    return match[1]


def get_incomplete_parameter(iter):
    """Get the parameter that is written left to the TextIter."""
    left_text = _get_left_text(iter)

    # match foo in:
    #  bar(foo
    #  bar(a=foo
    #  bar(qux, foo
    #  foo
    #  bar + foo
    match = re.match(rf"(?:{PARAMETER}|^)(\w+)$", left_text)
    logger.debug(f"get_incomplete_parameter text: %s match: %s", left_text, match)

    if match is None:
        return None

    return match[1]


def propose_symbols(text_iter, codes):
    """Find key names that match the input at the cursor and are mapped to the codes."""
    incomplete_name = get_incomplete_parameter(text_iter)

    if incomplete_name is None or len(incomplete_name) <= 1:
        return []

    incomplete_name = incomplete_name.lower()

    return [
        (name, name)
        for name in list(system_mapping.list_names(codes=codes))
        if incomplete_name in name.lower() and incomplete_name != name.lower()
    ]


def propose_function_names(text_iter):
    """Find function names that match the input at the cursor."""
    incomplete_name = get_incomplete_function_name(text_iter)

    if incomplete_name is None or len(incomplete_name) <= 1:
        return []

    incomplete_name = incomplete_name.lower()

    return [
        (name, f"{name}({', '.join(get_macro_argument_names(FUNCTIONS[name]))})")
        for name in FUNCTION_NAMES
        if incomplete_name in name.lower() and incomplete_name != name.lower()
    ]


debounces = {}


def debounce(func):
    """Debounce a function call to improve performance."""

    def clear_debounce(self, *args):
        debounces[func.__name__] = None
        return func(self, *args)

    def wrapped(self, *args):
        if debounces.get(func.__name__) is not None:
            GLib.source_remove(debounces[func.__name__])

        timeout = self.debounce_timeout

        debounces[func.__name__] = GLib.timeout_add(
            timeout, lambda: clear_debounce(self, *args)
        )

    return wrapped


class SuggestionLabel(Gtk.Label):
    """A label with some extra internal information."""

    __gtype_name__ = "SuggestionLabel"

    def __init__(self, display_name, suggestion):
        super().__init__(label=display_name)
        self.suggestion = suggestion


class Autocompletion(Gtk.Popover):
    """Provide keyboard-controllable beautiful autocompletions.

    The one provided via source_view.get_completion() is not very appealing
    """

    __gtype_name__ = "Autocompletion"

    def __init__(self, text_input, target_selector):
        """Create an autocompletion popover.

        It will remain hidden until there is something to autocomplete.

        Parameters
        ----------
        text_input : Gtk.SourceView | Gtk.TextView
            The widget that contains the text that should be autocompleted
        """
        super().__init__(
            # Don't switch the focus to the popover when it shows
            modal=False,
            # Always show the popover below the cursor, don't move it to a different
            # position based on the location within the window
            constrain_to=Gtk.PopoverConstraint.NONE,
        )

        self.debounce_timeout = 100

        self.text_input = text_input
        self.target_selector = target_selector
        self._target_key_capabilities = []
        target_selector.connect("changed", self._update_target_key_capabilities)

        self.scrolled_window = Gtk.ScrolledWindow(
            min_content_width=200,
            max_content_height=200,
            propagate_natural_width=True,
            propagate_natural_height=True,
        )
        self.list_box = Gtk.ListBox()
        self.list_box.get_style_context().add_class("transparent")
        self.scrolled_window.add(self.list_box)

        # row-activated is on-click,
        # row-selected is when scrolling through it
        self.list_box.connect(
            "row-activated",
            self._on_suggestion_clicked,
        )

        self.add(self.scrolled_window)

        self.get_style_context().add_class("autocompletion")

        self.set_position(Gtk.PositionType.BOTTOM)

        text_input.connect("key-press-event", self.navigate)

        # add some delay, so that pressing the button in the completion works before
        # the popover is hidden due to focus-out-event
        text_input.connect("focus-out-event", self.on_text_input_unfocus)

        text_input.get_buffer().connect("changed", self.update)

        self.set_position(Gtk.PositionType.BOTTOM)

        self.visible = False

        self.show_all()
        self.popdown()  # hidden by default. this needs to happen after show_all!

    def on_text_input_unfocus(self, *_):
        """The code editor was unfocused."""
        GLib.timeout_add(100, self.popdown)
        # "(input-remapper-gtk:97611): Gtk-WARNING **: 16:33:56.464: GtkTextView -
        # did not receive focus-out-event. If you connect a handler to this signal,
        # it must return FALSE so the text view gets the event as well"
        return False

    def navigate(self, _, event):
        """Using the keyboard to select an autocompletion suggestion."""
        if not self.visible:
            return

        if event.keyval == Gdk.KEY_Escape:
            self.popdown()
            return

        selected_row = self.list_box.get_selected_row()

        if event.keyval not in [Gdk.KEY_Down, Gdk.KEY_Up, Gdk.KEY_Return]:
            # not one of the keys that controls the autocompletion. Deselect
            # the row but keep it open
            self.list_box.select_row(None)
            return

        if event.keyval == Gdk.KEY_Return:
            if selected_row is None:
                # nothing selected, forward the event to the text editor
                return

            # a row is selected and should be used for autocompletion
            self.list_box.emit("row-activated", selected_row)
            return Gdk.EVENT_STOP

        num_rows = len(self.list_box.get_children())

        if selected_row is None:
            # select the first row
            if event.keyval == Gdk.KEY_Down:
                new_selected_row = self.list_box.get_row_at_index(0)

            if event.keyval == Gdk.KEY_Up:
                new_selected_row = self.list_box.get_row_at_index(num_rows - 1)
        else:
            # select the next row
            selected_index = selected_row.get_index()
            new_index = selected_index

            if event.keyval == Gdk.KEY_Down:
                new_index += 1

            if event.keyval == Gdk.KEY_Up:
                new_index -= 1

            if new_index < 0:
                new_index = num_rows - 1

            if new_index > num_rows - 1:
                new_index = 0

            new_selected_row = self.list_box.get_row_at_index(new_index)

        self.list_box.select_row(new_selected_row)

        self._scroll_to_row(new_selected_row)

        # don't change editor contents
        return Gdk.EVENT_STOP

    def _scroll_to_row(self, row):
        """Scroll up or down so that the row is visible."""
        # unfortunately, it seems that without focusing the row it won't happen
        # automatically (or whatever the reason for this is, just a wild guess)
        # (the focus should not leave the code editor, so that continuing
        # to write code is possible), so here is a custom solution.
        row_height = row.get_allocation().height

        if row:
            y_offset = row.translate_coordinates(self.list_box, 0, 0)[1]
            height = self.scrolled_window.get_max_content_height()
            current_y_scroll = self.scrolled_window.get_vadjustment().get_value()

            vadjustment = self.scrolled_window.get_vadjustment()

            if y_offset > current_y_scroll + (height - row_height):
                vadjustment.set_value(y_offset - (height - row_height))

            if y_offset < current_y_scroll:
                # scroll up because the element is not visible anymore
                vadjustment.set_value(y_offset)

    def _get_text_iter_at_cursor(self):
        """Get Gtk.TextIter at the current text cursor location."""
        cursor = self.text_input.get_cursor_locations()[0]
        return self.text_input.get_iter_at_location(cursor.x, cursor.y)[1]

    def popup(self):
        self.visible = True
        super().popup()

    def popdown(self):
        self.visible = False
        super().popdown()

    @debounce
    def update(self, *_):
        """Find new autocompletion suggestions and display them. Hide if none."""
        if not self.text_input.is_focus():
            self.popdown()
            return

        self.list_box.forall(self.list_box.remove)

        # move the autocompletion to the text cursor
        cursor = self.text_input.get_cursor_locations()[0]
        # convert it to window coords, because the cursor values will be very large
        # when the TextView is in a scrolled down ScrolledWindow.
        window_coords = self.text_input.buffer_to_window_coords(
            Gtk.TextWindowType.TEXT, cursor.x, cursor.y
        )
        cursor.x = window_coords.window_x
        cursor.y = window_coords.window_y
        cursor.y += 12

        if self.text_input.get_show_line_numbers():
            cursor.x += 25

        self.set_pointing_to(cursor)

        text_iter = self._get_text_iter_at_cursor()
        suggested_names = propose_function_names(text_iter)
        suggested_names += propose_symbols(text_iter, self._target_key_capabilities)

        if len(suggested_names) == 0:
            self.popdown()
            return

        self.popup()  # ffs was this hard to find

        # add visible autocompletion entries
        for suggestion, display_name in suggested_names:
            label = SuggestionLabel(display_name, suggestion)
            self.list_box.insert(label, -1)
            label.show_all()

    def _update_target_key_capabilities(self, *_):
        target = self.target_selector.get_active_id()
        self._target_key_capabilities = global_uinputs.get_uinput(
            target
        ).capabilities()[EV_KEY]

    def _on_suggestion_clicked(self, _, selected_row):
        """An autocompletion suggestion was selected and should be inserted."""
        selected_label = selected_row.get_children()[0]
        suggestion = selected_label.suggestion
        buffer = self.text_input.get_buffer()

        # make sure to replace the complete unfinished word. Look to the right and
        # remove whatever there is
        cursor_iter = self._get_text_iter_at_cursor()
        right = buffer.get_text(cursor_iter, buffer.get_end_iter(), True)
        match = re.match(r"^(\w+)", right)
        right = match[1] if match else ""
        Gtk.TextView.do_delete_from_cursor(
            self.text_input, Gtk.DeleteType.CHARS, len(right)
        )

        # do the same to the left
        cursor_iter = self._get_text_iter_at_cursor()
        left = buffer.get_text(buffer.get_start_iter(), cursor_iter, True)
        match = re.match(r".*?(\w+)$", re.sub("\n", " ", left))
        left = match[1] if match else ""
        Gtk.TextView.do_delete_from_cursor(
            self.text_input, Gtk.DeleteType.CHARS, -len(left)
        )

        # insert the autocompletion
        Gtk.TextView.do_insert_at_cursor(self.text_input, suggestion)

        self.emit("suggestion-inserted")


GObject.signal_new(
    "suggestion-inserted", Autocompletion, GObject.SignalFlags.RUN_FIRST, None, []
)
