# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2023 sezanzeb <proxima@hip70890b.de>
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

"""Process that sends stuff to the GUI.

It should be started via input-remapper-control and pkexec.

GUIs should not run as root
https://wiki.archlinux.org/index.php/Running_GUI_applications_as_root

The service shouldn't do that even though it has root rights, because that
would enable key-loggers to just ask input-remapper for all user-input.

Instead, the ReaderService is used, which will be stopped when the gui closes.

Whereas for the reader-service to start a password is needed and it stops whe
the ui closes.

This uses the backend injection.event_reader and mapping_handlers to process all the
different input-events into simple on/off events and sends them to the gui.
"""

from __future__ import annotations

from typing import Tuple

import evdev
from evdev.ecodes import EV_ABS

from inputremapper.configs.input_config import (
    DEFAULT_ANALOG_THRESHOLD_MAGNITUDE,
)
from inputremapper.input_event import InputEvent
from inputremapper.ipc.pipe import Pipe
from inputremapper.logging.logger import logger
from inputremapper.injection.mapping_handlers.mapping_handler import MappingHandler
from inputremapper.injection.mapping_handlers.abs_util import calculate_trigger_point

# received by the reader-service
CMD_TERMINATE = "terminate"
CMD_STOP_READING = "stop-reading"
CMD_REFRESH_GROUPS = "refresh_groups"

# sent by the reader-service to the reader
MSG_GROUPS = "groups"
MSG_EVENT = "event"
MSG_STATUS = "status"


class ForwardToUIHandler(MappingHandler):
    """Implements the MappingHandler protocol. Sends all events into the pipe."""

    def __init__(self, pipe: Pipe):
        self.pipe = pipe
        self._last_event = InputEvent.from_tuple((99, 99, 99))

    def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice,
        suppress: bool = False,
    ) -> bool:
        """Filter duplicates and send into the pipe."""
        if event == self._last_event:
            return True

        # These defaults work with EV_KEY and EV_REL
        pressed = False if event.value == 0 else True
        direction = 1 if event.value >= 0 else -1

        # Because joysticks aren't as precise, they wiggle and their value might not be
        # centered around 0, they need special treatment
        if event.type == EV_ABS:
            threshold, mid_point = calculate_trigger_point(
                event,
                DEFAULT_ANALOG_THRESHOLD_MAGNITUDE,
                source,
            )

            # If within 30% (into each direction) of the mid_point, count as released
            # A large threahold makes it significantly easier to not accidentally
            # record both ABS_X and ABS_Y.
            if abs(event.value - mid_point) < threshold:
                pressed = False

            if event.value < mid_point:
                direction = -1

        self._last_event = event

        logger.debug("Sending %s to frontend", event)
        self.pipe.send(
            {
                "type": MSG_EVENT,
                "message": {
                    "sec": event.sec,
                    "usec": event.usec,
                    "type": event.type,
                    "code": event.code,
                    "value": event.value,
                    "pressed": pressed,
                    "direction": direction,
                    "origin_hash": event.origin_hash,
                },
            }
        )
        return True

    def _trigger_point(
        self,
        analog_threshold: int,
        abs_min: int,
        abs_max: int,
    ) -> Tuple[float, float]:
        """Calculate the axis mid and trigger point."""
        half_range = (abs_max - abs_min) / 2
        middle = half_range + abs_min
        # Nothing configured yet, assume 10% as default, which makes the ui usable.
        # Without a threshold, tiny wiggles of the joystick will already screw the
        # recording up, and releasing the joystick will in many cases not stop the
        # recording, presumably because the last event has a very small value instead of
        # 0 because it's impossible to perfectly center the joystick. Or something.
        # Haven't verified if this is really what's going on.
        trigger_offset = half_range * analog_threshold / 100

        # threshold, middle
        return middle + trigger_offset, middle

    def reset(self):
        pass
