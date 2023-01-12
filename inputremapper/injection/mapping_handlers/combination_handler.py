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

from __future__ import annotations  # needed for the TYPE_CHECKING import
from typing import TYPE_CHECKING, Dict, Hashable

import evdev
from evdev.ecodes import EV_ABS, EV_REL

from inputremapper.configs.input_config import InputCombination
from inputremapper.configs.mapping import Mapping
from inputremapper.injection.mapping_handlers.mapping_handler import (
    MappingHandler,
    InputEventHandler,
    HandlerEnums,
)
from inputremapper.input_event import InputEvent
from inputremapper.logger import logger

if TYPE_CHECKING:
    from inputremapper.injection.context import Context


class CombinationHandler(MappingHandler):
    """Keeps track of a combination and notifies a sub handler."""

    # map of InputEvent.input_match_hash -> bool , keep track of the combination state
    _pressed_keys: Dict[Hashable, bool]
    _output_state: bool  # the last update we sent to a sub-handler
    _sub_handler: InputEventHandler
    _handled_input_hashes: list[Hashable]

    def __init__(
        self,
        combination: InputCombination,
        mapping: Mapping,
        context: Context,
        **_,
    ) -> None:
        logger.debug(str(mapping))
        super().__init__(combination, mapping)
        self._pressed_keys = {}
        self._output_state = False
        self._context = context

        # prepare a key map for all events with non-zero value
        for input_config in combination:
            assert not input_config.defines_analog_input
            self._pressed_keys[input_config.input_match_hash] = False

        self._handled_input_hashes = [
            input_config.input_match_hash for input_config in combination
        ]

        assert len(self._pressed_keys) > 0  # no combination handler without a key

    def __str__(self):
        return (
            f'CombinationHandler for "{str(self.mapping.input_combination)}" '
            f"{tuple(t for t in self._pressed_keys.keys())}"
        )

    def __repr__(self):
        description = (
            f'CombinationHandler for "{repr(self.mapping.input_combination)}" '
            f"{tuple(t for t in self._pressed_keys.keys())}"
        )
        return f"<{description} at {hex(id(self))}>"

    @property
    def child(self):
        # used for logging
        return self._sub_handler

    def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice,
        suppress: bool = False,
    ) -> bool:
        if event.input_match_hash not in self._handled_input_hashes:
            # we are not responsible for the event
            return False

        was_activated = self.is_activated()

        # update the state
        is_pressed = event.value == 1
        self._pressed_keys[event.input_match_hash] = is_pressed
        # maybe this changes the activation status (triggered/not-triggered)
        is_activated = self.is_activated()

        if is_activated == was_activated or is_activated == self._output_state:
            # nothing changed
            if self._output_state:
                # combination is active, consume the event
                return True
            else:
                # combination inactive, forward the event
                return False

        if is_activated:
            # send key up events to the forwarded uinput
            self.forward_release()
            event = event.modify(value=1)
        else:
            if self._output_state or self.mapping.is_axis_mapping():
                # we ignore the suppress argument for release events
                # otherwise we might end up with stuck keys
                # (test_event_pipeline.test_combination)

                # we also ignore it if the mapping specifies an output axis
                # this will enable us to activate multiple axis with the same button
                suppress = False
            event = event.modify(value=0)

        if suppress:
            return False

        logger.debug("Sending %s to sub-handler", self.mapping.input_combination)
        self._output_state = bool(event.value)
        return self._sub_handler.notify(event, source, suppress)

    def reset(self) -> None:
        self._sub_handler.reset()
        for key in self._pressed_keys:
            self._pressed_keys[key] = False
        self._output_state = False

    def is_activated(self) -> bool:
        """Return if all keys in the keymap are set to True."""
        return False not in self._pressed_keys.values()

    def forward_release(self) -> None:
        """Forward a button release for all keys if this is a combination.

        this might cause duplicate key-up events but those are ignored by evdev anyway
        """
        if len(self._pressed_keys) == 1 or not self.mapping.release_combination_keys:
            return

        keys_to_release = filter(
            lambda cfg: self._pressed_keys.get(cfg.input_match_hash),
            self.mapping.input_combination,
        )

        for input_config in keys_to_release:
            origin_hash = input_config.origin_hash
            if origin_hash is None:
                # TODO test
                logger.error(
                    f"Can't forward due to missing origin_hash in {repr(input_config)}"
                )
                continue

            forward_to = self._context.get_forward_uinput(origin_hash)
            logger.write(input_config, forward_to)
            forward_to.write(*input_config.type_and_code, 0)
            forward_to.syn()

    def needs_ranking(self) -> bool:
        return bool(self.input_configs)

    def rank_by(self) -> InputCombination:
        return InputCombination(
            [event for event in self.input_configs if not event.defines_analog_input]
        )

    def wrap_with(self) -> Dict[InputCombination, HandlerEnums]:
        return_dict = {}
        for config in self.input_configs:
            if config.type == EV_ABS and not config.defines_analog_input:
                return_dict[InputCombination([config])] = HandlerEnums.abs2btn

            if config.type == EV_REL and not config.defines_analog_input:
                return_dict[InputCombination([config])] = HandlerEnums.rel2btn

        return return_dict
