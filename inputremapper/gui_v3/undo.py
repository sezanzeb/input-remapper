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


"""Linear undo and redo by snapshot.

Every state is an immutable value, so a snapshot is just a reference. No commands
to apply or invert.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Hashable
from typing import Generic, TypeVar

T = TypeVar("T")


class History(Generic[T]):
    def __init__(
        self,
        initial: T,
        limit: int = 200,
        coalesce_seconds: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._states: list[T] = [initial]
        self._index = 0
        self._limit = limit
        self._coalesce_seconds = coalesce_seconds
        self._clock = clock
        self._last_key: Hashable | None = None
        self._last_time = 0.0

    @property
    def current(self) -> T:
        return self._states[self._index]

    @property
    def can_undo(self) -> bool:
        return self._index > 0

    @property
    def can_redo(self) -> bool:
        return self._index < len(self._states) - 1

    def commit(self, state: T, merge_key: Hashable | None = None) -> bool:
        """Record a new state. Returns False if nothing changed.

        Commits with the same `merge_key` within `coalesce_seconds` of each other
        replace one another, so typing a name is a single undo step.
        """
        if state == self.current:
            return False

        now = self._clock()
        merge = (
            merge_key is not None
            and merge_key == self._last_key
            and now - self._last_time <= self._coalesce_seconds
            and self._index > 0
        )
        self._last_key = merge_key
        self._last_time = now

        if merge:
            # Redo can't exist here: the previous commit cleared it, and undo
            # resets the merge key.
            self._states[self._index] = state
            return True

        del self._states[self._index + 1 :]
        self._states.append(state)
        self._index += 1
        if len(self._states) > self._limit:
            del self._states[0]
            self._index -= 1
        return True

    def undo(self) -> T:
        if self.can_undo:
            self._index -= 1
            self._last_key = None
        return self.current

    def redo(self) -> T:
        if self.can_redo:
            self._index += 1
            self._last_key = None
        return self.current
