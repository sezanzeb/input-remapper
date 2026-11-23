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

"""Which kind of device a key belongs to, for the key search. No GTK."""

from __future__ import annotations

from collections.abc import Iterable

from inputremapper.gui_v3.search import Item

MOUSE_BUTTONS = frozenset(
    {
        "BTN_LEFT",
        "BTN_RIGHT",
        "BTN_MIDDLE",
        "BTN_SIDE",
        "BTN_EXTRA",
        "BTN_FORWARD",
        "BTN_BACK",
        "BTN_TASK",
    }
)
# In the order the search lists them when it has nothing to rank by.
KEY_GROUPS = ("Keyboard", "Mouse", "Gamepad")


def key_group(name: str) -> str:
    """Which kind of device a key or button belongs to."""
    upper = name.upper()
    if upper in MOUSE_BUTTONS:
        return "Mouse"
    if upper.startswith("BTN_"):
        return "Gamepad"
    return "Keyboard"


def key_items(names: Iterable[str]) -> list[Item]:
    """The search items for key names, in the order of `KEY_GROUPS`."""
    items = [Item(name, name, key_group(name)) for name in names]
    return sorted(items, key=lambda item: KEY_GROUPS.index(item.group))
