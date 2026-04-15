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
    _configured_direction_was_pressed: bool
    _sub_handler: MappingHandler

    def __init__(
        self,
        combination: InputCombination,
        mapping: Mapping,
        global_uinputs: GlobalUInputs,
        **_,
    ) -> None:
        super().__init__(combination, mapping, global_uinputs)

        self._configured_direction_was_pressed = False
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

        threshold, mid_point = calculate_trigger_point(
            event,
            analog_threshold,
            source,
        )

        value = event.value

        direction = 1 if value > mid_point else -1

        want_positive = analog_threshold > 0
        want_negative = analog_threshold < 0

        '''print(f"""abs_to_btn
            {pressed=}
            {value=}
            {want_positive=}
            {want_negative=}
            {direction=}
            {threshold=}
            {mid_point=}
            {analog_threshold=}
            {self._configured_direction_was_pressed=}"""
        )'''

        # dpad-right to a:
        # dpad moves right: a down
        # dpad returns: a up
        # dpad goes left: dpad -1
        # dpad returns: dpad 0
        # There are two "dpad returns" cases that have different outcomes

        # joystick-right to a:
        # joystick moves to +1234: ignore (If the architecture could do it, forward 0)
        # joystick moves over threshold: a down
        # joystick returns below threshold: a up
        # joystick moves -1234: forward -1234
        # joystick goes to 0: forward 0
        # (In many cases it won't exactly return to 0, but to +1 or something, because
        # they aren't 100% precise. But the positive direction is mapped, so turn
        # this into 0. Unfortunately there is currently no way to do this in our
        # architecture.)

        if not self._configured_direction_was_pressed:
            # these needs to be <= and >= mid point, to forward the dpad release for
            # the unmapped direction
            if want_positive and value <= mid_point:
                return False
            if want_negative and value >= mid_point:
                return False

        # if it was pressed, then we first need to deal with releasing the sub-handler.

        # For dpads, the threshold is 1, but so is the max value. So <= and >= it is.
        # If this is dumb, change the threhsold to be a float.
        pressed = value >= threshold if want_positive else value <= threshold

        self._configured_direction_was_pressed = pressed

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
        self._configured_direction_was_pressed = False
        self._sub_handler.reset()
