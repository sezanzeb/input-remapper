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

from __future__ import annotations

import itertools
from typing import Tuple, Iterable, Union, List, Dict, Optional, Hashable

from evdev import ecodes
from inputremapper.configs.paths import PathUtils
from inputremapper.input_event import InputEvent

try:
    from pydantic.v1 import BaseModel, root_validator, validator
except ImportError:
    from pydantic import BaseModel, root_validator, validator

from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.gui.messages.message_types import MessageType
from inputremapper.logging.logger import logger
from inputremapper.utils import get_evdev_constant_name, DeviceHash

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

EMPTY_TYPE = 99


class InputConfig(BaseModel):
    """Describes a single input within a combination, to configure mappings."""

    message_type = MessageType.selected_event

    type: int
    code: int

    # origin_hash is a hash to identify a specific /dev/input/eventXX device.
    # This solves a number of bugs when multiple devices have overlapping capabilities.
    # see utils.get_device_hash for the exact hashing function
    origin_hash: Optional[DeviceHash] = None

    # At which point is an analog input treated as "pressed"
    analog_threshold: Optional[int] = None

    def __str__(self):
        return f"InputConfig {get_evdev_constant_name(self.type, self.code)}"

    def __repr__(self):
        return (
            f"<InputConfig {self.type_and_code} "
            f"{get_evdev_constant_name(*self.type_and_code)}, "
            f"{self.analog_threshold}, "
            f"{self.origin_hash}, "
            f"at {hex(id(self))}>"
        )

    @property
    def input_match_hash(self) -> Hashable:
        """a Hashable object which is intended to match the InputConfig with a
        InputEvent.

        InputConfig itself is hashable, but can not be used to match InputEvent's
        because its hash includes the analog_threshold
        """
        return self.type, self.code, self.origin_hash

    @property
    def is_empty(self) -> bool:
        return self.type == EMPTY_TYPE

    @property
    def defines_analog_input(self) -> bool:
        """Whether this defines an analog input."""
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
            origin_hash=event.origin_hash,
            analog_threshold=event.value,
        )

    def description(self, exclude_threshold=False, exclude_direction=False) -> str:
        """Get a human-readable description of the event."""
        return (
            f"{self._get_name()} "
            f"{self._get_direction() if not exclude_direction else ''} "
            f"{self._get_threshold_value() if not exclude_threshold else ''}".strip()
        )

    def _get_mouse_button_name(self) -> Optional[str]:
        """Get a human-readable description of a mouse-button. Only the first 7
        mouse buttons are in evdev and they often have misleading names there
        (eg it calls buttons 6 & 7 forward/back but usually that's buttons 5 & 4).
        Returns None if not a mouse button."""

        if self.type == ecodes.EV_KEY:
            if ecodes.BTN_MOUSE <= self.code <= ecodes.BTN_MIDDLE:
                # button is left/right/middle button
                key_name: str = get_evdev_constant_name(self.type, self.code)
                return key_name.replace(
                    "BTN_", "Mouse Button "
                )  # eg "Mouse Button LEFT"
            elif ecodes.BTN_MIDDLE < self.code < ecodes.BTN_JOYSTICK:
                # button is a higher-number mouse button like side-buttons.
                # This calculation assumes left mouse button is button 1, so side buttons start at 4.
                button_number: int = self.code - ecodes.BTN_MOUSE + 1
                return f"Mouse Button {button_number}"  # eg "Mouse Button 7"

        return None

    def _get_name(self) -> Optional[str]:
        """Human-readable name (e.g. KEY_A) of the specified input event."""

        # prevent logging warnings for new/empty configs
        if self.is_empty:
            return None

        # must check if it's a mouse button *before* ecodes
        # because not all mouse buttons are in ecodes.
        mouse_button_name: Optional[str] = self._get_mouse_button_name()
        if mouse_button_name != None:
            return mouse_button_name

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
            key_name = keyboard_layout.get_name(self.code)

        if key_name is None:
            # if no result, look in the linux combination constants. On a german
            # keyboard for example z and y are switched, which will therefore
            # cause the wrong letter to be displayed.
            key_name = get_evdev_constant_name(self.type, self.code)

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
        threshold_direction = self.analog_threshold // abs(self.analog_threshold)
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
        }.get((self.code, threshold_direction)) or (
            "+" if threshold_direction > 0 else "-"
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
        origin_hash: Optional[str] = None,
        analog_threshold: Optional[int] = None,
    ) -> InputConfig:
        """Return a new modified event."""
        return InputConfig(
            type=type_ if type_ is not None else self.type,
            code=code if code is not None else self.code,
            origin_hash=origin_hash if origin_hash is not None else self.origin_hash,
            analog_threshold=(
                analog_threshold
                if analog_threshold is not None
                else self.analog_threshold
            ),
        )

    def __hash__(self):
        return hash((self.type, self.code, self.origin_hash, self.analog_threshold))

    @validator("analog_threshold")
    def _ensure_analog_threshold_is_none(cls, analog_threshold):
        """ensure the analog threshold is none, not zero."""
        if analog_threshold == 0 or analog_threshold is None:
            return None

        return analog_threshold

    @root_validator
    def _remove_analog_threshold_for_key_input(cls, values):
        """remove the analog threshold if the type is a EV_KEY"""
        type_ = values.get("type")
        if type_ == ecodes.EV_KEY:
            values["analog_threshold"] = None
        return values

    @root_validator(pre=True)
    def validate_origin_hash(cls, values):
        origin_hash = values.get("origin_hash")
        if origin_hash is None:
            # For new presets, origin_hash should be set. For old ones, it can
            # be still missing. A lot of tests didn't set an origin_hash.
            if values.get("type") != EMPTY_TYPE:
                logger.warning("No origin_hash set for %s", values)

            return values

        values["origin_hash"] = origin_hash.lower()
        return values

    class Config:
        allow_mutation = False
        underscore_attrs_are_private = True


InputCombinationInit = Union[
    Iterable[Dict[str, Union[str, int]]],
    Iterable[InputConfig],
]


class InputCombination(Tuple[InputConfig, ...]):
    """One or more InputConfigs used to trigger a mapping."""

    # tuple is immutable, therefore we need to override __new__()
    # https://jfine-python-classes.readthedocs.io/en/latest/subclass-tuple.html
    def __new__(cls, configs: InputCombinationInit) -> InputCombination:
        """Create a new InputCombination.

        Examples
        --------
            InputCombination([InputConfig, ...])
            InputCombination([{type: ..., code: ..., value: ...}, ...])
        """
        if not isinstance(configs, Iterable):
            raise TypeError("InputCombination requires a list of InputConfigs.")

        if isinstance(configs, InputConfig):
            # wrap the argument in square brackets
            raise TypeError("InputCombination requires a list of InputConfigs.")

        validated_configs = []
        for config in configs:
            if isinstance(configs, InputEvent):
                raise TypeError("InputCombinations require InputConfigs, not Events.")

            if isinstance(config, InputConfig):
                validated_configs.append(config)
            elif isinstance(config, dict):
                validated_configs.append(InputConfig(**config))
            else:
                raise TypeError(f'Can\'t handle "{config}"')

        if len(validated_configs) == 0:
            raise ValueError(f"failed to create InputCombination with {configs = }")

        # mypy bug: https://github.com/python/mypy/issues/8957
        # https://github.com/python/mypy/issues/8541
        return super().__new__(cls, validated_configs)  # type: ignore

    def __str__(self):
        return f'Combination ({" + ".join(str(event) for event in self)})'

    def __repr__(self):
        combination = ", ".join(repr(event) for event in self)
        return f"<InputCombination ({combination}) at {hex(id(self))}>"

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
        """Turn the object into a tuple of dicts."""
        return tuple(input_config.dict(exclude_defaults=True) for input_config in self)

    @classmethod
    def empty_combination(cls) -> InputCombination:
        """A combination that has default invalid (to evdev) values.

        Useful for the UI to indicate that this combination is not set
        """
        return cls([{"type": EMPTY_TYPE, "code": 99, "analog_threshold": 99}])

    @classmethod
    def from_tuples(cls, *tuples):
        """Construct an InputCombination from (type, code, analog_threshold) tuples."""
        dicts = []
        for tuple_ in tuples:
            if len(tuple_) == 3:
                dicts.append(
                    {
                        "type": tuple_[0],
                        "code": tuple_[1],
                        "analog_threshold": tuple_[2],
                    }
                )
            elif len(tuple_) == 2:
                dicts.append(
                    {
                        "type": tuple_[0],
                        "code": tuple_[1],
                    }
                )
            else:
                raise TypeError

        return cls(dicts)

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
        """Return the first event that defines an analog input."""
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

        if len(self) > 6:
            logger.warning(
                "Your input combination has a length of %d. Long combinations might "
                'freeze the process. Edit the configuration files in "%s" to fix it.',
                len(self),
                PathUtils.get_config_path(),
            )

        permutations = []
        for permutation in itertools.permutations(self[:-1]):
            permutations.append(InputCombination((*permutation, self[-1])))

        return permutations

    def beautify(self) -> str:
        """Get a human-readable string representation."""
        if self == InputCombination.empty_combination():
            return "empty_combination"
        return " + ".join(event.description(exclude_threshold=True) for event in self)
