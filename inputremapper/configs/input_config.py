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

from __future__ import annotations

import itertools
from typing import Tuple, Iterable, Union, List, Dict, Optional, Hashable

from evdev import ecodes
from inputremapper.input_event import InputEvent
from pydantic import BaseModel, root_validator, validator

from inputremapper.configs.system_mapping import system_mapping
from inputremapper.gui.messages.message_types import MessageType
from inputremapper.logger import logger

# having shift in combinations modifies the configured output,
# ctrl might not work at all
DIFFICULT_COMBINATIONS = [
    ecodes.KEY_LEFTSHIFT,
    ecodes.KEY_RIGHTSHIFT,
    ecodes.KEY_LEFTCTRL,
    ecodes.KEY_RIGHTCTRL,
    ecodes.KEY_LEFTALT,
    ecodes.KEY_RIGHTALT,
]


class InputConfig(BaseModel):
    """The configuration of a single input to a mapping"""

    message_type = MessageType.selected_event

    type: int
    code: int
    origin: Optional[str] = None
    analog_threshold: Optional[int] = None

    @property
    def input_match_hash(self) -> Hashable:
        """a Hashable object which is intended to match the InputConfig with a
        InputEvent.

        InputConfig itself is hashable, but can not be used to match InputEvent's
        because its hash includes the analog_threshold
        """
        return self.type, self.code, self.origin

    @property
    def defines_analog_input(self) -> bool:
        """Whether this defines an analog input"""
        return not self.analog_threshold and self.type != ecodes.EV_KEY

    @property
    def type_and_code(self) -> Tuple[int, int]:
        """Event type, code."""
        return self.type, self.code

    @classmethod
    def btn_left(cls):
        return cls(type=ecodes.EV_KEY, code=ecodes.BTN_LEFT)

    @classmethod
    def from_input_event(cls, event: InputEvent) -> InputConfig:
        """create an input confing from the given InputEvent, uses the value as
        analog threshold"""
        return cls(
            type=event.type,
            code=event.code,
            origin=event.origin,
            analog_threshold=event.value,
        )

    def description(self, exclude_threshold=False, exclude_direction=False) -> str:
        """Get a human-readable description of the event."""
        return (
            f"{self._get_name()} "
            f"{self._get_direction() if not exclude_direction else ''} "
            f"{self._get_threshold_value() if not exclude_threshold else ''}".strip()
        )

    def _get_name(self) -> Optional[str]:
        """Human-readable name (e.g. KEY_A) of the specified input event."""
        if self.type not in ecodes.bytype:
            logger.warning("Unknown type for %s", self)
            return f"unknown {self.type, self.code}"

        if self.code not in ecodes.bytype[self.type]:
            logger.warning("Unknown code for %s", self)
            return f"unknown {self.type, self.code}"

        key_name = None

        # first try to find the name in xmodmap to not display wrong
        # names due to the keyboard layout
        if self.type == ecodes.EV_KEY:
            key_name = system_mapping.get_name(self.code)

        if key_name is None:
            # if no result, look in the linux combination constants. On a german
            # keyboard for example z and y are switched, which will therefore
            # cause the wrong letter to be displayed.
            key_name = ecodes.bytype[self.type][self.code]
            if isinstance(key_name, list):
                key_name = key_name[0]

        key_name = key_name.replace("ABS_Z", "Trigger Left")
        key_name = key_name.replace("ABS_RZ", "Trigger Right")

        key_name = key_name.replace("ABS_HAT0X", "DPad-X")
        key_name = key_name.replace("ABS_HAT0Y", "DPad-Y")
        key_name = key_name.replace("ABS_HAT1X", "DPad-2-X")
        key_name = key_name.replace("ABS_HAT1Y", "DPad-2-Y")
        key_name = key_name.replace("ABS_HAT2X", "DPad-3-X")
        key_name = key_name.replace("ABS_HAT2Y", "DPad-3-Y")

        key_name = key_name.replace("ABS_X", "Joystick-X")
        key_name = key_name.replace("ABS_Y", "Joystick-Y")
        key_name = key_name.replace("ABS_RX", "Joystick-RX")
        key_name = key_name.replace("ABS_RY", "Joystick-RY")

        key_name = key_name.replace("BTN_", "Button ")
        key_name = key_name.replace("KEY_", "")

        key_name = key_name.replace("REL_", "")
        key_name = key_name.replace("HWHEEL", "Wheel")
        key_name = key_name.replace("WHEEL", "Wheel")

        key_name = key_name.replace("_", " ")
        key_name = key_name.replace("  ", " ")
        return key_name

    def _get_direction(self) -> str:
        """human-readable direction description for the analog_threshold"""
        if self.type == ecodes.EV_KEY or self.defines_analog_input:
            return ""

        assert self.analog_threshold
        return {
            # D-Pad
            (ecodes.ABS_HAT0X, -1): "Left",
            (ecodes.ABS_HAT0X, 1): "Right",
            (ecodes.ABS_HAT0Y, -1): "Up",
            (ecodes.ABS_HAT0Y, 1): "Down",
            (ecodes.ABS_HAT1X, -1): "Left",
            (ecodes.ABS_HAT1X, 1): "Right",
            (ecodes.ABS_HAT1Y, -1): "Up",
            (ecodes.ABS_HAT1Y, 1): "Down",
            (ecodes.ABS_HAT2X, -1): "Left",
            (ecodes.ABS_HAT2X, 1): "Right",
            (ecodes.ABS_HAT2Y, -1): "Up",
            (ecodes.ABS_HAT2Y, 1): "Down",
            # joystick
            (ecodes.ABS_X, 1): "Right",
            (ecodes.ABS_X, -1): "Left",
            (ecodes.ABS_Y, 1): "Down",
            (ecodes.ABS_Y, -1): "Up",
            (ecodes.ABS_RX, 1): "Right",
            (ecodes.ABS_RX, -1): "Left",
            (ecodes.ABS_RY, 1): "Down",
            (ecodes.ABS_RY, -1): "Up",
            # wheel
            (ecodes.REL_WHEEL, -1): "Down",
            (ecodes.REL_WHEEL, 1): "Up",
            (ecodes.REL_HWHEEL, -1): "Left",
            (ecodes.REL_HWHEEL, 1): "Right",
        }.get((self.code, self.analog_threshold)) or (
            "+" if self.analog_threshold > 0 else "-"
        )

    def _get_threshold_value(self) -> str:
        """human-readable value of the analog_threshold e.g. '20%'"""
        if self.analog_threshold is None:
            return ""
        return {
            ecodes.EV_REL: f"{abs(self.analog_threshold)}",
            ecodes.EV_ABS: f"{abs(self.analog_threshold)}%",
        }.get(self.type) or ""

    def modify(
        self,
        type_: Optional[int] = None,
        code: Optional[int] = None,
        origin: Optional[int] = None,
        analog_threshold: Optional[int] = None,
    ) -> InputConfig:
        """Return a new modified event."""
        return InputConfig(
            type=type_ if type_ is not None else self.type,
            code=code if code is not None else self.code,
            origin=origin if origin is not None else self.origin,
            analog_threshold=analog_threshold
            if analog_threshold is not None
            else self.analog_threshold,
        )

    def __hash__(self):
        return hash((self.type, self.code, self.origin, self.analog_threshold))

    @validator("analog_threshold")
    def _ensure_analog_threshold_is_none(cls, analog_threshold):
        """ensure the analog threshold is none, not zero."""
        if analog_threshold:
            return analog_threshold
        return None

    @root_validator
    def _remove_analog_threshold_for_key_input(cls, values):
        """remove the analog threshold if the type is a EV_KEY"""
        type_ = values.get("type")
        if type_ == ecodes.EV_KEY:
            values["analog_threshold"] = None
        return values

    class Config:
        allow_mutation = False
        underscore_attrs_are_private = True


InputCombinationInit = Union[
    InputConfig,
    Iterable[Dict[str, int]],
    Iterable[InputConfig],
]


class InputCombination(Tuple[InputConfig, ...]):
    """One or more InputConfig's used to trigger a mapping"""

    # tuple is immutable, therefore we need to override __new__()
    # https://jfine-python-classes.readthedocs.io/en/latest/subclass-tuple.html
    def __new__(cls, configs: InputCombinationInit) -> InputCombination:
        if isinstance(configs, InputCombination):
            return super().__new__(cls, configs)  # type: ignore
        if isinstance(configs, InputConfig):
            return super().__new__(cls, [configs])  # type: ignore

        validated_configs = []
        for cfg in configs:
            if isinstance(cfg, InputConfig):
                validated_configs.append(cfg)
            else:
                validated_configs.append(InputConfig(**cfg))

        if len(validated_configs) == 0:
            raise ValueError(f"failed to create InputCombination with {configs = }")

        # mypy bug: https://github.com/python/mypy/issues/8957
        # https://github.com/python/mypy/issues/8541
        return super().__new__(cls, validated_configs)  # type: ignore

    def __str__(self):
        return " + ".join(event.description(exclude_threshold=True) for event in self)

    def __repr__(self):
        return f"<InputCombination {', '.join([str((*e.type_and_code, e.analog_threshold)) for e in self])}>"

    @classmethod
    def __get_validators__(cls):
        """Used by pydantic to create InputCombination objects."""
        yield cls.validate

    @classmethod
    def validate(cls, init_arg) -> InputCombination:
        """The only valid option is from_config"""
        if isinstance(init_arg, InputCombination):
            return init_arg
        return cls(init_arg)

    def to_config(self) -> Tuple[Dict[str, int], ...]:
        return tuple(input_config.dict(exclude_defaults=True) for input_config in self)

    @classmethod
    def empty_combination(cls) -> InputCombination:
        """A combination that has default invalid (to evdev) values.

        Useful for the UI to indicate that this combination is not set
        """
        return cls([{"type": 99, "code": 99, "analog_threshold": 99}])

    def is_problematic(self) -> bool:
        """Is this combination going to work properly on all systems?"""
        if len(self) <= 1:
            return False

        for input_config in self:
            if input_config.type != ecodes.EV_KEY:
                continue

            if input_config.code in DIFFICULT_COMBINATIONS:
                return True

        return False

    @property
    def defines_analog_input(self) -> bool:
        """Check if there is any analog input in self."""
        return True in tuple(i.defines_analog_input for i in self)

    def find_analog_input_config(
        self, type_: Optional[int] = None
    ) -> Optional[InputConfig]:
        """Return the first event that defines an analog input"""
        for input_config in self:
            if input_config.defines_analog_input and (
                type_ is None or input_config.type == type_
            ):
                return input_config
        return None

    def get_permutations(self) -> List[InputCombination]:
        """Get a list of EventCombinations representing all possible permutations.

        combining a + b + c should have the same result as b + a + c.
        Only the last combination remains the same in the returned result.
        """
        if len(self) <= 2:
            return [self]

        permutations = []
        for permutation in itertools.permutations(self[:-1]):
            permutations.append(InputCombination((*permutation, self[-1])))

        return permutations

    def beautify(self) -> str:
        """Get a human-readable string representation."""
        if self == InputCombination.empty_combination():
            return "empty_combination"
        return " + ".join(event.description(exclude_threshold=True) for event in self)
