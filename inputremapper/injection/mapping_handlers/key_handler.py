# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2024 sezanzeb <b8x45ygc9@mozmail.com>
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

from typing import Tuple, Dict

from inputremapper import exceptions
from inputremapper.configs.input_config import InputCombination
from inputremapper.configs.mapping import Mapping
from inputremapper.exceptions import MappingParsingError
from inputremapper.injection.global_uinputs import global_uinputs
from inputremapper.injection.mapping_handlers.mapping_handler import (
    MappingHandler,
    HandlerEnums,
)
from inputremapper.input_event import InputEvent
from inputremapper.logging.logger import logger
from inputremapper.utils import get_evdev_constant_name


class KeyHandler(MappingHandler):
    """Injects the target key if notified."""

    _active: bool
    _maps_to: Tuple[int, int]

    def __init__(
        self,
        combination: InputCombination,
        mapping: Mapping,
        **_,
    ):
        super().__init__(combination, mapping)
        maps_to = mapping.get_output_type_code()
        if not maps_to:
            raise MappingParsingError(
                "Unable to create key handler from mapping", mapping=mapping
            )

        self._maps_to = maps_to
        self._active = False

    def __str__(self):
        return f"KeyHandler to {self._maps_to}"

    def __repr__(self):
        return f"<{str(self)} at {hex(id(self))}>"

    @property
    def child(self):  # used for logging
        name = get_evdev_constant_name(*self._maps_to)
        return f"maps to: {name} {self._maps_to} on {self.mapping.target_uinput}"

    def notify(self, event: InputEvent, *_, **__) -> bool:
        """Inject event.value to the target key."""

        event_tuple = (*self._maps_to, event.value)
        try:
            global_uinputs.write(event_tuple, self.mapping.target_uinput)
            self._active = bool(event.value)
            return True
        except exceptions.Error:
            return False

    def reset(self) -> None:
        logger.debug("resetting key_handler")
        if self._active:
            event_tuple = (*self._maps_to, 0)
            global_uinputs.write(event_tuple, self.mapping.target_uinput)
            self._active = False

    def needs_wrapping(self) -> bool:
        return True

    def wrap_with(self) -> Dict[InputCombination, HandlerEnums]:
        return {InputCombination(self.input_configs): HandlerEnums.combination}
