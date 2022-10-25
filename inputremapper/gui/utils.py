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
from __future__ import annotations

import time
from typing import List

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gtk, GLib, Gdk

from inputremapper.logger import logger


# status ctx ids

CTX_SAVE = 0
CTX_APPLY = 1
CTX_KEYCODE = 2
CTX_ERROR = 3
CTX_WARNING = 4
CTX_MAPPING = 5

debounces = {}


def debounce(timeout):
    """Debounce a function call to improve performance.

    Calling this creates the decorator, so use something like

    @debounce(50)
    def foo():
        ...
    """

    def decorator(func):
        def clear_debounce(self, *args):
            debounces[func.__name__] = None
            return func(self, *args)

        def wrapped(self, *args):
            if debounces.get(func.__name__) is not None:
                GLib.source_remove(debounces[func.__name__])

            debounces[func.__name__] = GLib.timeout_add(
                timeout, lambda: clear_debounce(self, *args)
            )

        return wrapped

    return decorator


class HandlerDisabled:
    """Safely modify a widget without causing handlers to be called.

    Use in a `with` statement.
    """

    def __init__(self, widget, handler):
        self.widget = widget
        self.handler = handler

    def __enter__(self):
        try:
            self.widget.handler_block_by_func(self.handler)
        except TypeError as error:
            # if nothing is connected to the given signal, it is not critical
            # at all
            logger.warning('HandlerDisabled entry failed: "%s"', error)

    def __exit__(self, *_):
        try:
            self.widget.handler_unblock_by_func(self.handler)
        except TypeError as error:
            logger.warning('HandlerDisabled exit failed: "%s"', error)


def gtk_iteration(iterations=0):
    """Iterate while events are pending."""
    while Gtk.events_pending():
        Gtk.main_iteration()
    for _ in range(iterations):
        time.sleep(0.002)
        while Gtk.events_pending():
            Gtk.main_iteration()


class Colors:
    """Looks up colors from the GTK theme.

    Defaults to libadwaita-light theme colors if the lookup fails.
    """

    fallback_accent = Gdk.RGBA(0.21, 0.52, 0.89, 1)
    fallback_background = Gdk.RGBA(0.98, 0.98, 0.98, 1)
    fallback_base = Gdk.RGBA(1, 1, 1, 1)
    fallback_border = Gdk.RGBA(0.87, 0.87, 0.87, 1)
    fallback_font = Gdk.RGBA(0.20, 0.20, 0.20, 1)

    @staticmethod
    def get_color(names: List[str], fallback: Gdk.RGBA) -> Gdk.RGBA:
        """Get theme colors. Provide multiple names for fallback purposes."""
        for name in names:
            found, color = Gtk.StyleContext().lookup_color(name)
            if found:
                return color

        return fallback

    @staticmethod
    def get_accent_color() -> Gdk.RGBA:
        """Look up the accent color from the current theme."""
        return Colors.get_color(
            ["accent_bg_color", "theme_selected_bg_color"],
            Colors.fallback_accent,
        )

    @staticmethod
    def get_background_color() -> Gdk.RGBA:
        """Look up the background-color from the current theme."""
        return Colors.get_color(
            ["theme_bg_color"],
            Colors.fallback_background,
        )

    @staticmethod
    def get_base_color() -> Gdk.RGBA:
        """Look up the base-color from the current theme."""
        return Colors.get_color(
            ["theme_base_color"],
            Colors.fallback_base,
        )

    @staticmethod
    def get_border_color() -> Gdk.RGBA:
        """Look up the border from the current theme."""
        return Colors.get_color(["borders"], Colors.fallback_border)

    @staticmethod
    def get_font_color() -> Gdk.RGBA:
        """Look up the border from the current theme."""
        return Colors.get_color(
            ["theme_fg_color"],
            Colors.fallback_font,
        )
