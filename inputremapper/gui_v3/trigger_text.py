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


"""Keys of a trigger as text, like "KEY_LEFTCTRL + KEY_A".

A stand-in until the window can record keys from a device.
"""

from __future__ import annotations

from typing import Any

from evdev import ecodes

from inputremapper.gui_v3.document import InputRef

_BY_NAME: dict[str, int] = {
    name: code
    for name, code in ecodes.ecodes.items()
    if name.startswith(("KEY_", "BTN_"))
}


def parse_trigger(text: str) -> tuple[InputRef, ...]:
    """Raises ValueError naming the first key that doesn't exist."""
    inputs: list[InputRef] = []
    for part in text.replace(",", "+").split("+"):
        name = part.strip().upper()
        if not name:
            continue
        if not name.startswith(("KEY_", "BTN_")):
            name = f"KEY_{name}"
        code: Any = _BY_NAME.get(name)
        if code is None:
            raise ValueError(f'Unknown key "{part.strip()}"')
        inputs.append(InputRef(type=ecodes.EV_KEY, code=int(code)))
    return tuple(inputs)


def print_trigger(inputs: tuple[InputRef, ...]) -> str:
    names: list[str] = []
    for ref in inputs:
        name = next(
            (n for n, c in _BY_NAME.items() if c == ref.code and ref.type == 1), None
        )
        names.append(name or f"{ref.type}:{ref.code}")
    return " + ".join(names)
