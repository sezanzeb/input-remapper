# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2025 sezanzeb <b8x45ygc9@mozmail.com>
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

from typing import Tuple

import evdev
from evdev.ecodes import EV_ABS

from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.configs.mapping import Mapping
from inputremapper.injection.global_uinputs import GlobalUInputs
from inputremapper.injection.mapping_handlers.mapping_handler import (
    MappingHandler,
    InputEventHandler,
)
from inputremapper.input_event import InputEvent, EventActions
from inputremapper.utils import get_evdev_constant_name


class AbsToBtnHandler(MappingHandler):
    """Handler which transforms an EV_ABS to a button event."""

    _input_config: InputConfig
    _active: bool
    _sub_handler: InputEventHandler

    def __init__(
        self,
        combination: InputCombination,
        mapping: Mapping,
        global_uinputs: GlobalUInputs,
        **_,
    ):
        super().__init__(combination, mapping, global_uinputs)

        self._active = False
        self._input_config = combination[0]
        assert self._input_config.analog_threshold
        assert len(combination) == 1

    def __str__(self):
        name = get_evdev_constant_name(*self._input_config.type_and_code)
        return f'AbsToBtnHandler for "{name}" ' f"{self._input_config.type_and_code}"

    def __repr__(self):
        return f"<{str(self)} at {hex(id(self))}>"

    @property
    def child(self):  # used for logging
        return self._sub_handler

    def _trigger_point(self, abs_min: int, abs_max: int) -> Tuple[float, float]:
        """Calculate the axis mid and trigger point."""
        #  TODO: potentially cache this function
        assert self._input_config.analog_threshold
        if abs_min == -1 and abs_max == 1:
            # this is a hat switch
            # return +-1
            return (
                self._input_config.analog_threshold
                // abs(self._input_config.analog_threshold),
                0,
            )

        half_range = (abs_max - abs_min) / 2
        middle = half_range + abs_min
        trigger_offset = half_range * self._input_config.analog_threshold / 100

        # threshold, middle
        return middle + trigger_offset, middle

    def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice,
        suppress: bool = False,
    ) -> bool:
        if event.input_match_hash != self._input_config.input_match_hash:
            return False

        absinfo = {
            entry[0]: entry[1] for entry in source.capabilities(absinfo=True)[EV_ABS]
        }
        threshold, mid_point = self._trigger_point(
            absinfo[event.code].min, absinfo[event.code].max
        )
        value = event.value
        if (value < threshold > mid_point) or (value > threshold < mid_point):
            if self._active:
                event = event.modify(value=0, actions=(EventActions.as_key,))
            else:
                # consume the event.
                # We could return False to forward events
                return True
        else:
            if value >= threshold > mid_point:
                direction = EventActions.positive_trigger
            else:
                direction = EventActions.negative_trigger
            event = event.modify(value=1, actions=(EventActions.as_key, direction))

        self._active = bool(event.value)
        # logger.debug(event.event_tuple, "sending to sub_handler")
        return self._sub_handler.notify(
            event,
            source=source,
            suppress=suppress,
        )

    def reset(self) -> None:
        self._active = False
        self._sub_handler.reset()
