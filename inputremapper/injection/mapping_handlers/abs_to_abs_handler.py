# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2022 sezanzeb <proxima@sezanzeb.de>
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

from typing import Tuple, Optional, Dict

import evdev
from evdev.ecodes import EV_ABS

from inputremapper.configs.input_config import InputCombination, InputConfig
from inputremapper import exceptions
from inputremapper.configs.mapping import Mapping
from inputremapper.injection.global_uinputs import global_uinputs
from inputremapper.injection.mapping_handlers.axis_transform import Transformation
from inputremapper.injection.mapping_handlers.mapping_handler import (
    MappingHandler,
    HandlerEnums,
    InputEventHandler,
)
from inputremapper.input_event import InputEvent, EventActions
from inputremapper.logger import logger
from inputremapper.utils import get_evdev_constant_name


class AbsToAbsHandler(MappingHandler):
    """Handler which transforms EV_ABS to EV_ABS events."""

    _map_axis: InputConfig  # the InputConfig for the axis we map
    _output_axis: Tuple[int, int]  # the (type, code) of the output axis
    _transform: Optional[Transformation]
    _target_absinfo: evdev.AbsInfo

    def __init__(
        self,
        combination: InputCombination,
        mapping: Mapping,
        **_,
    ) -> None:
        super().__init__(combination, mapping)

        # find the input event we are supposed to map. If the input combination is
        # BTN_A + ABS_X + BTN_B, then use the value of ABS_X for the transformation
        assert (map_axis := combination.find_analog_input_config(type_=EV_ABS))
        self._map_axis = map_axis

        assert mapping.output_code is not None
        assert mapping.output_type == EV_ABS
        self._output_axis = (mapping.output_type, mapping.output_code)

        target_uinput = global_uinputs.get_uinput(mapping.target_uinput)
        abs_capabilities = target_uinput.capabilities(absinfo=True)[EV_ABS]
        self._target_absinfo = dict(abs_capabilities)[mapping.output_code]

        self._transform = None

    def __str__(self):
        name = get_evdev_constant_name(*self._map_axis.type_and_code)
        return f'AbsToAbsHandler for "{name}" {self._map_axis}'

    def __repr__(self):
        return f"<{str(self)} at {hex(id(self))}>"

    @property
    def child(self):  # used for logging
        return (
            f"maps to: {self.mapping.get_output_name_constant()} "
            f"{self.mapping.get_output_type_code()} at "
            f"{self.mapping.target_uinput}"
        )

    def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice,
        suppress: bool = False,
    ) -> bool:
        if event.input_match_hash != self._map_axis.input_match_hash:
            return False

        if EventActions.recenter in event.actions:
            self._write(self._scale_to_target(0))
            return True

        if not self._transform:
            absinfo = dict(source.capabilities(absinfo=True)[EV_ABS])[event.code]
            self._transform = Transformation(
                max_=absinfo.max,
                min_=absinfo.min,
                deadzone=self.mapping.deadzone,
                gain=self.mapping.gain,
                expo=self.mapping.expo,
            )

        try:
            self._write(self._scale_to_target(self._transform(event.value)))
            return True
        except (exceptions.UinputNotAvailable, exceptions.EventNotHandled):
            return False

    def reset(self) -> None:
        self._write(self._scale_to_target(0))

    def _scale_to_target(self, x: float) -> int:
        """Scales a x value between -1 and 1 to an integer between
        target_absinfo.min and target_absinfo.max

        input values above 1 or below -1 are clamped to the extreme values
        """
        factor = (self._target_absinfo.max - self._target_absinfo.min) / 2
        offset = self._target_absinfo.min + factor
        y = factor * x + offset
        if y > offset:
            return int(min(self._target_absinfo.max, y))
        else:
            return int(max(self._target_absinfo.min, y))

    def _write(self, value: int):
        """Inject."""
        try:
            global_uinputs.write(
                (*self._output_axis, value), self.mapping.target_uinput
            )
        except OverflowError:
            # screwed up the calculation of the event value
            logger.error("OverflowError (%s, %s, %s)", *self._output_axis, value)

    def needs_wrapping(self) -> bool:
        return len(self.input_configs) > 1

    def set_sub_handler(self, handler: InputEventHandler) -> None:
        assert False  # cannot have a sub-handler

    def wrap_with(self) -> Dict[InputCombination, HandlerEnums]:
        if self.needs_wrapping():
            return {InputCombination(self.input_configs): HandlerEnums.axisswitch}
        return {}
