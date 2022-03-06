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


from gi.repository import Gtk, GLib


# status ctx ids
CTX_SAVE = 0
CTX_APPLY = 1
CTX_KEYCODE = 2
CTX_ERROR = 3
CTX_WARNING = 4
CTX_MAPPING = 5

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

class HandlerDisabled:
    """Safely modify a widget without causing handlers to be called.

    Use in a with statement.
    """

    def __init__(self, widget, handler):
        self.widget = widget
        self.handler = handler

    def __enter__(self):
        self.widget.handler_block_by_func(self.handler)

    def __exit__(self, *_):
        self.widget.handler_unblock_by_func(self.handler)


def gtk_iteration():
    """Iterate while events are pending."""
    while Gtk.events_pending():
        Gtk.main_iteration()
