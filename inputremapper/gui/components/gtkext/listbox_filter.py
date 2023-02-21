# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2023 sezanzeb <proxima@sezanzeb.de>
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

from gi.repository import Gtk

from typing import Iterator


class ListBoxFilter:
    """Implements UI-side filtering of list widgets.

    The following example creates a new ``ListBoxFilter`` for a given ``Gtk.ListBox``.
    It also sets all optional arguments to override some default behavior.

    >>> filter = ListBoxFilter(
    >>>     my_listbox,                  # Gtk.ListBox to be managed
    >>>     get_row_name=MyRow.get_name  # custom row name getter
    >>> )

    To apply a filter use `set_filter` as follows.

    >>> filter.set_filter("some text")
    >>> filter.set_filter("More Text", case_sensitive=True)

    """

    MAX_WIDGET_TREE_TEXT_SEARCH_DEPTH = 10

    def __init__(
        self,
        listbox: Gtk.ListBox,
        get_row_name=None,
        filter_value="",
        case_sensitive=False,
    ):
        self._controlled_listbox: Gtk.ListBox = listbox
        self._get_row_name = get_row_name or self.get_row_name
        self._filter_value : str = filter_value
        self._case_sensitive = case_sensitive

    @classmethod
    def get_row_name(T, row: Gtk.ListBoxRow) -> str:
        """
        Returns the visible text of a Gtk.ListBoxRow from both the row's `name`
        attribute or the row's text in the UI.
        """
        text = getattr(row, "name", "")

        # find and join all text in the ListBoxRow
        text += " ".join(v for v in T.get_widget_tree_text(row) if v != "")

        return text.strip()

    @classmethod
    def get_widget_tree_text(T, widget: Gtk.Widget, level=0) -> Iterator[str]:
        """
        Recursively traverses the tree of child widgets starting from the given
        widget, and yields the text of all text-containing widgets.
        """
        if level > T.MAX_WIDGET_TREE_TEXT_SEARCH_DEPTH:
            return

        if hasattr(widget, "get_label"):
            yield (widget.get_label() or "").strip()
        if hasattr(widget, "get_text"):
            yield (widget.get_text() or "").strip()
        if isinstance(widget, Gtk.Container):
            for t in widget.get_children():
                yield from T.get_widget_tree_text(t, level=level + 1)

    @property
    def filter_value(self):
        return self._filter_value

    @property
    def case_sensitive(self):
        return self._case_sensitive

    # matches the current filter_value and filter_options with the given value
    def match_filter(self, value: str):
        value = (value or "").strip()

        # if filter is not set, all rows need to match
        if self._filter_value == "":
            return True

        if self._case_sensitive:
            return self._filter_value in value
        else:
            return self._filter_value.lower() in value.lower()

    # set and apply filter
    def set_filter(self, filter_value: str, case_sensitive=False):
        self._filter_value = str(filter_value)
        self._case_sensitive = bool(case_sensitive)
        self._gtk_apply_filter_to_listbox_children()

    # apply filter to widget tree
    def _gtk_apply_filter_to_listbox_children(self):
        value = self._filter_value.lower()
        selected: Gtk.ListBoxRow = None
        row: Gtk.ListBoxRow = None
        for row in self._controlled_listbox.get_children():
            if self.match_filter(self._get_row_name(row)):
                # show matching rows, then select the first row
                row.show()
                if selected is None:
                    selected = row
                    self._controlled_listbox.select_row(selected)
            else:
                # hide non-matching rows
                row.hide()
