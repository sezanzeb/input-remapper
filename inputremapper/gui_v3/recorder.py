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


"""Record the keys a user presses, through the reader service.

The reader service is the small root helper that is allowed to read /dev/input and
reports events for one device group. The GUI is never run as root, so this is the
only way to see keys. `ReaderService` is imported for its pipe protocol only.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from evdev import ecodes

from inputremapper.gui.reader_service import (
    CMD_READ_ALL,
    CMD_STOP_READING,
    MSG_EVENT,
    MSG_STATUS,
)
from inputremapper.gui_v3.document import InputRef

# Events that devices send while a key is held but that are no real input.
IGNORED = {(ecodes.EV_KEY, ecodes.BTN_TOOL_DOUBLETAP)}


class RecorderError(Exception):
    """Recording can't start, for example because the reader service won't run."""


class PipeLike(Protocol):
    def poll(self) -> bool: ...

    def recv(self) -> Any: ...

    def send(self, message: Any) -> None: ...


class Accumulator:
    """Turns press and release events into one key combination.

    The combination grows as keys are pressed, and is finished once everything that
    was pressed since recording started has been released again.
    Only keys and buttons are recorded; analog axes are out of scope for now.
    """

    def __init__(self) -> None:
        self.inputs: list[InputRef] = []
        self._held: set[tuple[int, int, str | None]] = set()
        self.finished = False

    def feed(
        self, type_: int, code: int, origin_hash: str | None, pressed: bool
    ) -> bool:
        """Returns True if the combination changed."""
        if self.finished or type_ != ecodes.EV_KEY or (type_, code) in IGNORED:
            return False

        identity = (type_, code, origin_hash)
        if not pressed:
            # Keys that were already down when recording began show up as releases
            # that we never saw the press of. Ignore those.
            if identity in self._held:
                self._held.discard(identity)
                if not self._held:
                    self.finished = True
            return False

        self._held.add(identity)
        ref = InputRef(type=type_, code=code, origin_hash=origin_hash)
        if ref in self.inputs:
            return False
        self.inputs.append(ref)
        return True


class Recorder:
    def __init__(
        self,
        results: PipeLike,
        commands: PipeLike,
        ensure_service: Callable[[], bool] = lambda: False,
    ) -> None:
        self._results = results
        self._commands = commands
        self._ensure_service = ensure_service
        self._accumulator: Accumulator | None = None
        self._on_update: Callable[[tuple[InputRef, ...], str], None] = (
            lambda _keys, _text: None
        )
        self._on_done: Callable[[], None] = lambda: None
        # A freshly started service empties the commands pipe while it starts up,
        # so the device is only sent once it reports being ready.
        self._pending_group: str | None = None
        self._locked_group: str | None = None

    @property
    def recording(self) -> bool:
        return self._accumulator is not None

    def start(
        self,
        group_key: str | None,
        on_update: Callable[[tuple[InputRef, ...], str], None],
        on_done: Callable[[], None],
    ) -> None:
        """Record from one device group, or from all of them if `group_key` is None.

        `on_update` also gets the group the keys were pressed on. When listening to
        all devices, the first key pressed decides the group; the others are ignored.
        """
        started = self._ensure_service()
        self._accumulator = Accumulator()
        self._on_update = on_update
        self._on_done = on_done
        # Drop anything left over from an earlier recording.
        while self._results.poll():
            self._results.recv()
        self._locked_group = group_key
        command = group_key if group_key is not None else CMD_READ_ALL
        if started:
            self._pending_group = command
        else:
            self._commands.send(command)

    def stop(self) -> None:
        self._pending_group = None
        if self._accumulator is None:
            return
        self._accumulator = None
        self._commands.send(CMD_STOP_READING)

    def poll(self) -> None:
        """Handle waiting messages. Call regularly while recording."""
        while self._results.poll():
            message = self._results.recv()
            accumulator = self._accumulator
            if message.get("type") == MSG_STATUS and self._pending_group is not None:
                group, self._pending_group = self._pending_group, None
                self._commands.send(group)
                continue
            if accumulator is None or message.get("type") != MSG_EVENT:
                continue

            body = message["message"]
            group = body.get("group", self._locked_group)
            if self._locked_group is None:
                if not _is_pressed(body) or body["type"] != ecodes.EV_KEY:
                    continue
                self._locked_group = group
            elif group != self._locked_group:
                continue

            changed = accumulator.feed(
                body["type"],
                body["code"],
                body.get("origin_hash"),
                _is_pressed(body),
            )
            if changed:
                self._on_update(tuple(accumulator.inputs), self._locked_group or "")
            if accumulator.finished:
                done = self._on_done
                self.stop()
                done()
                return


def _is_pressed(body: dict[str, Any]) -> bool:
    pressed = body.get("pressed")
    if pressed is not None:
        return bool(pressed)
    return body["value"] != 0
