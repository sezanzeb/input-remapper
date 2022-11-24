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

from typing import Dict

import evdev

from inputremapper.input_configuration import InputCombination
from inputremapper.injection.mapping_handlers.mapping_handler import (
    MappingHandler,
    HandlerEnums,
)
from inputremapper.input_event import InputEvent


class NullHandler(MappingHandler):
    """Handler which consumes the event and does nothing."""

    def __str__(self):
        return f"NullHandler for {self.mapping.event_combination}<{id(self)}>"

    @property
    def child(self):
        return "Voids all events"

    def needs_wrapping(self) -> bool:
        return False in [input_.defines_analog_input for input_ in self.input_configs]

    def wrap_with(self) -> Dict[InputCombination, HandlerEnums]:
        return {InputCombination(self.input_configs): HandlerEnums.combination}

    def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice,
        forward: evdev.UInput,
        suppress: bool = False,
    ) -> bool:
        return True

    def reset(self) -> None:
        pass
