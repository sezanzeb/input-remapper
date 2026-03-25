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

from typing import List

import evdev

from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper.configs.mapping import Mapping
from inputremapper.injection.global_uinputs import GlobalUInputs
from inputremapper.injection.mapping_handlers.abs_util import calculate_trigger_point
from inputremapper.injection.mapping_handlers.mapping_handler import (
    MappingHandler,
)
from inputremapper.input_event import InputEvent, EventActions
from inputremapper.utils import get_evdev_constant_name


class AbsToBtnHandler(MappingHandler):
    """Handler which transforms an EV_ABS to a button event."""

    _input_config: InputConfig
    _active: bool
    _sub_handler: MappingHandler

    def __init__(
        self,
        combination: InputCombination,
        mapping: Mapping,
        global_uinputs: GlobalUInputs,
        **_,
    ) -> None:
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

    def get_children(self) -> List[MappingHandler]:
        return [self._sub_handler]

    def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice,
        suppress: bool = False,
    ) -> bool:
        if event.input_match_hash != self._input_config.input_match_hash:
            return False

        analog_threshold = self._input_config.analog_threshold
        assert analog_threshold is not None

        # TODO: potentially cache this function
        threshold, mid_point = calculate_trigger_point(
            event,
            analog_threshold,
            source,
        )

        value = event.value

        if analog_threshold > 0:
            # Movement of the joystick into positive direction triggers an output
            pressed = value >= threshold
            direction = 1
        else:
            pressed = value <= threshold
            direction = -1

        if not pressed and not self._active:
            # Noise from the joystick or a movement in the opposite direction
            #
            # Return True ("This handler knows this event, and took care of it", to
            # avoid forwarding it), if it is a positive movement for a positive mapping.
            #
            # Otherwise, a negative movement for a positive mapping, means the joystick
            # moves into a direction that is not mapped to anything here. So it should
            # allow other handlers to handle it or the event reader to forward it.
            #
            # If self._active is True, we'd want to make sure the release is sent to
            # the sub_handler. So only do this if self._active is False.
            want_negative_is_negative = analog_threshold < 0 and value <= mid_point
            want_positive_is_positive = analog_threshold > 0 and value >= mid_point
            # Checking for <= mid_point and >= mid_point means that a value of exactly
            # the mid_point belongs to the mapping. So even if only one direction is
            # mapped, there is no resting point for the joystick that is being
            # forwarded anymore. The resting point belongs to the mapping now. However,
            # checking for < and > means that even if both directions are mapped, the
            # resting point will be forwarded.
            return want_negative_is_negative or want_positive_is_positive

        self._active = pressed

        event = event.modify(
            pressed=pressed,
            direction=direction,
            actions=(EventActions.as_key,),
        )

        return self._sub_handler.notify(
            event,
            source=source,
            suppress=suppress,
        )

    def reset(self) -> None:
        self._active = False
        self._sub_handler.reset()
