# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings

from __future__ import annotations
from typing import Tuple, Dict, List
from collections import defaultdict

from evdev.ecodes import (
    EV_ABS,
    ABS_HAT0X,
    ABS_HAT0Y,
)

from inputremapper import exceptions
from inputremapper.configs.input_config import InputCombination
from inputremapper.configs.mapping import Mapping
from inputremapper.configs.gamepad_symbols import get_gamepad_axis_info
from inputremapper.exceptions import MappingParsingError
from inputremapper.injection.global_uinputs import GlobalUInputs
from inputremapper.injection.mapping_handlers.mapping_handler import (
    HandlerEnums,
    MappingHandler,
)
from inputremapper.input_event import InputEvent
from inputremapper.logging.logger import logger
from inputremapper.utils import get_evdev_constant_name


# Track active presses across all handlers for each (target_uinput, axis_code)
# Dict[(target_uinput, axis_code), Dict[handler_id, target_value]]
_ACTIVE_AXIS_PRESSES: Dict[Tuple[str, int], Dict[int, int]] = defaultdict(dict)


class BtnToAbsHandler(MappingHandler):
    """Maps a button/key press to an analog axis position (Stick or Trigger).
    
    Supports simultaneous axis movement (e.g. diagonal movement: W + D)
    and smoothly transitions when one key is released.
    """

    _axis_code: int
    _target_value: int
    _is_active: bool

    def __init__(
        self,
        combination: InputCombination,
        mapping: Mapping,
        global_uinputs: GlobalUInputs,
        **_,
    ):
        super().__init__(combination, mapping, global_uinputs)

        axis_info = get_gamepad_axis_info(mapping.output_symbol)
        if axis_info:
            self._axis_code, self._target_value = axis_info
        elif mapping.output_code is not None:
            self._axis_code = mapping.output_code
            self._target_value = 32767
        else:
            raise MappingParsingError(
                f"Unable to determine axis for BtnToAbsHandler from {mapping}",
                mapping=mapping,
            )

        self._is_active = False

    def __str__(self):
        name = get_evdev_constant_name(EV_ABS, self._axis_code)
        return f"BtnToAbsHandler to {name}={self._target_value} on {self.mapping.target_uinput}"

    def __repr__(self):
        return f"<{str(self)} at {hex(id(self))}>"

    def get_children(self) -> List[MappingHandler]:
        return []

    def notify(self, event: InputEvent, *_, **__) -> bool:
        """Inject the calculated axis position when key is pressed or released."""
        target_uinput = self.mapping.target_uinput
        key = (target_uinput, self._axis_code)
        handler_id = id(self)

        is_pressed = event.is_pressed()
        if is_pressed:
            _ACTIVE_AXIS_PRESSES[key][handler_id] = self._target_value
            self._is_active = True
        else:
            _ACTIVE_AXIS_PRESSES[key].pop(handler_id, None)
            self._is_active = False

        # Calculate net axis value
        presses = _ACTIVE_AXIS_PRESSES[key]
        if presses:
            net_val = sum(presses.values())
            if self._axis_code in (ABS_HAT0X, ABS_HAT0Y):
                net_val = max(-1, min(1, net_val))
            else:
                net_val = max(-32768, min(32767, net_val))
        else:
            net_val = 0

        event_tuple = (EV_ABS, self._axis_code, net_val)
        try:
            self.global_uinputs.write(event_tuple, target_uinput)
            return True
        except exceptions.Error:
            return False

    def reset(self) -> None:
        logger.debug("resetting btn_to_abs_handler")
        target_uinput = self.mapping.target_uinput
        key = (target_uinput, self._axis_code)
        handler_id = id(self)

        _ACTIVE_AXIS_PRESSES[key].pop(handler_id, None)
        if self._is_active:
            self._is_active = False
            presses = _ACTIVE_AXIS_PRESSES[key]
            net_val = sum(presses.values()) if presses else 0
            event_tuple = (EV_ABS, self._axis_code, net_val)
            try:
                self.global_uinputs.write(event_tuple, target_uinput)
            except exceptions.Error:
                pass

    def needs_wrapping(self) -> bool:
        return True

    def wrap_with(self) -> Dict[InputCombination, HandlerEnums]:
        return {InputCombination(self.input_configs): HandlerEnums.combination}
