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

"""A popover to search a list by typing, shared by the block palette and the key
fields: a search box over the matches, listed under a heading per group with a bar
in the group's color. Matching is in `search`."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from inputremapper.gui_v3.search import Item, search

_GREY = "#8a8a8a"


class SearchPopover(Gtk.Popover):
    def __init__(
        self,
        items: Sequence[Item],
        colors: dict[str, str],
        on_choose: Callable[[str], None],
        placeholder: str = "Search",
        current: Callable[[], str | None] = lambda: None,
        width: int = 240,
    ) -> None:
        """`current` is the value to start on when opened, if any."""
        super().__init__()
        self._items = items
        self._colors = colors
        self._on_choose = on_choose
        self._current = current
        self._shown_query: str | None = None

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        for margin in ("top", "bottom", "start", "end"):
            getattr(outer, f"set_margin_{margin}")(8)
        self._search = Gtk.SearchEntry(placeholder_text=placeholder)
        outer.pack_start(self._search, False, False, 0)

        # value, what is shown, whether it is a group heading
        self._found = Gtk.ListStore(str, str, bool)
        self._view = Gtk.TreeView(
            model=self._found, headers_visible=False, activate_on_single_click=True
        )
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("")
        column.pack_start(renderer, True)
        column.add_attribute(renderer, "markup", 1)
        self._view.append_column(column)
        self._selection = self._view.get_selection()
        # Headings can't be chosen.
        self._selection.set_select_function(
            lambda _s, model, path, _c: not model[path][2]
        )
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            min_content_height=260,
            min_content_width=width,
        )
        scrolled.add(self._view)
        outer.pack_start(scrolled, True, True, 0)

        self._search.connect("search-changed", lambda *_: self._show_matches())
        self._search.connect("activate", self._activated)
        self._search.connect("key-press-event", self._key_pressed)
        self._search.connect("stop-search", lambda *_: self.popdown())
        self._view.connect("row-activated", self._row_activated)
        self.connect("show", self._opened)
        outer.show_all()
        self.add(outer)

    def open_with(self, text: str) -> None:
        """Open with something already typed into the search."""
        self.popup()
        self._search.set_text(text)
        self._search.set_position(-1)

    # Showing -------------------------------------------------------------------

    def _show_matches(self, select: str | None = None) -> None:
        query = self._search.get_text()
        self._shown_query = query
        self._found.clear()
        for group, matches in search(self._items, query):
            color = self._colors.get(group, _GREY)
            self._found.append(
                [
                    "",
                    f'<span foreground="{_GREY}"><b>{GLib.markup_escape_text(group)}</b></span>',
                    True,
                ]
            )
            for item in matches:
                bar = f'<span foreground="{color}">▌</span>'
                label = GLib.markup_escape_text(item.label)
                self._found.append([item.value, f"{bar} {label}", False])

        row = next((r for r in self._found if select and r[0] == select), None)
        row = row or next((r for r in self._found if not r[2]), None)
        if row is not None:
            self._selection.select_iter(row.iter)
            self._view.scroll_to_cell(row.path, None, True, 0.5, 0)

    def _opened(self, *_: Any) -> None:
        self._search.set_text("")
        self._show_matches(self._current())
        self._search.grab_focus()

    # Choosing ------------------------------------------------------------------

    def _choose(self, value: str) -> None:
        self.popdown()
        self._on_choose(value)

    def _row_activated(self, _view: Gtk.TreeView, path: Gtk.TreePath, *_: Any) -> None:
        if not self._found[path][2]:
            self._choose(self._found[path][0])

    def _activated(self, *_: Any) -> None:
        # The entry reports changes after a short delay; don't act on stale ones.
        if self._search.get_text() != self._shown_query:
            self._show_matches()
        model, row = self._selection.get_selected()
        if row is not None:
            self._choose(model[row][0])

    def _key_pressed(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> bool:
        if event.keyval in (Gdk.KEY_Down, Gdk.KEY_Up):
            self._move(1 if event.keyval == Gdk.KEY_Down else -1)
            return True
        return False

    def _move(self, step: int) -> None:
        model, row = self._selection.get_selected()
        target = (model.get_path(row).get_indices()[0] if row else -1) + step
        while 0 <= target < len(model) and model[target][2]:
            target += step
        if 0 <= target < len(model):
            path = Gtk.TreePath.new_from_indices([target])
            self._selection.select_path(path)
            self._view.scroll_to_cell(path, None, False, 0, 0)
