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
from dataclasses import dataclass
from typing import List, Callable, Dict, Optional

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


@dataclass()
class DebounceInfo:
    # constant after register:
    timeout_ms: int
    function: Optional[Callable]

    # can change when called again:
    args: list
    kwargs: dict
    glib_timeout: Optional[int]


class DebounceManager:
    """Stops all debounced functions if needed."""

    debounce_infos: Dict[int, DebounceInfo] = {}

    def register(self, function, timeout_ms):
        """Remember the timeout. `function` should be decorated with `@debounce`.

        This is needed for `call` to work.
        """
        self.debounce_infos[id(function)] = DebounceInfo(
            timeout_ms=timeout_ms,
            function=function,
            glib_timeout=None,
            args=[],
            kwargs={},
        )

    def debounce(self, function, *args, **kwargs):
        """Call this function with the given args later."""
        debounce_info = self.debounce_infos.get(id(function))
        if debounce_info is None:
            raise Exception(
                f"Function {function.__name__} has not been set up for debouncing"
            )

        debounce_info.args = args
        debounce_info.kwargs = kwargs

        glib_timeout = debounce_info.glib_timeout
        if glib_timeout is not None:
            GLib.source_remove(glib_timeout)

        def run():
            self.stop(function)
            return function(*args, **kwargs)

        debounce_info.glib_timeout = GLib.timeout_add(
            debounce_info.timeout_ms,
            lambda: run(),
        )

    def stop(self, function):
        """Stop the current debounce timeout of this function and don't call it.

        New calls to that function will be debounced again.
        """
        debounce_info = self.debounce_infos[id(function)]
        if debounce_info.glib_timeout is not None:
            GLib.source_remove(debounce_info.glib_timeout)
            debounce_info.glib_timeout = None

    def stop_all(self):
        """No debounced function should be called anymore after this.

        New calls to that function will be debounced again.
        """
        for debounce_info in self.debounce_infos.values():
            self.stop(debounce_info.function)

    def run_all_now(self):
        """Don't wait any longer."""
        for debounce_info in self.debounce_infos.values():
            if debounce_info.glib_timeout is None:
                # nothing is currently waiting for this function to be called
                continue

            self.stop(debounce_info.function)
            try:
                debounce_info.function(
                    *debounce_info.args,
                    **debounce_info.kwargs
                )
            except Exception as exception:
                # if individual functions fails, continue calling the others.
                # also, don't raise this because there is nowhere this exception
                # could be caught in a useful way
                logger.error(exception)


debounce_manager = DebounceManager()


def debounce(timeout):
    """Debounce a function call to improve performance.

    Calling this with a millisecond value creates the decorator, so use something like

    @debounce(50)
    def function(self):
        ...

    In tests, run_all_now can be used to avoid waiting to speed them up.
    """
    # the outside `debounce` function is needed to obtain the millisecond value

    def decorator(function):
        # the regular decorator.
        # @decorator
        # def foo():
        #   ...
        debounce_manager.register(function, timeout)

        def wrapped(*args, **kwargs):
            # this is the function that will actually be called
            debounce_manager.debounce(function, *args, **kwargs)

        return wrapped

    return decorator


class HandlerDisabled:
    """Safely modify a widget without causing handlers to be called.

    Use in a `with` statement.
    """

    def __init__(self, widget: Gtk.Widget, handler: Callable):
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
