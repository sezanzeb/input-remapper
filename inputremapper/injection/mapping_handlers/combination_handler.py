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

from typing import Dict, Tuple

import evdev
from evdev.ecodes import EV_ABS, EV_REL

from inputremapper.configs.mapping import Mapping
from inputremapper.event_combination import EventCombination
from inputremapper.injection.mapping_handlers.mapping_handler import (
    MappingHandler,
    InputEventHandler,
    HandlerEnums,
)
from inputremapper.input_event import InputEvent
from inputremapper.logger import logger


class CombinationHandler(MappingHandler):
    """Keeps track of a combination and notifies a sub handler."""

    # map of (event.type, event.code) -> bool , keep track of the combination state
    _pressed_keys: Dict[Tuple[int, int], bool]
    _output_state: bool  # the last update we sent to a sub-handler
    _sub_handler: InputEventHandler

    def __init__(
        self,
        combination: EventCombination,
        mapping: Mapping,
        **_,
    ) -> None:
        logger.debug(mapping)
        super().__init__(combination, mapping)
        self._pressed_keys = {}
        self._output_state = False

        # prepare a key map for all events with non-zero value
        for event in combination:
            assert event.is_key_event
            self._pressed_keys[event.type_and_code] = False

        assert len(self._pressed_keys) > 0  # no combination handler without a key

    def __str__(self):
        return (
            f'CombinationHandler for "{self.mapping.event_combination}" <{id(self)}>:'
        )

    def __repr__(self):
        return self.__str__()

    @property
    def child(self):  # used for logging
        return self._sub_handler

    def notify(
        self,
        event: InputEvent,
        source: evdev.InputDevice,
        forward: evdev.UInput,
        suppress: bool = False,
    ) -> bool:
        type_code = event.type_and_code
        if type_code not in self._pressed_keys.keys():
            return False  # we are not responsible for the event

        last_state = self.get_active()
        self._pressed_keys[type_code] = event.value == 1

        if self.get_active() == last_state or self.get_active() == self._output_state:
            # nothing changed
            if self._output_state:
                # combination is active, consume the event
                return True
            else:
                # combination inactive, forward the event
                return False

        if self.get_active():
            # send key up events to the forwarded uinput
            self.forward_release(forward)
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

        logger.debug_key(
            self.mapping.event_combination, "triggered: sending to sub-handler"
        )
        self._output_state = bool(event.value)
        return self._sub_handler.notify(event, source, forward, suppress)

    def reset(self) -> None:
        self._sub_handler.reset()
        for key in self._pressed_keys:
            self._pressed_keys[key] = False
        self._output_state = False

    def get_active(self) -> bool:
        """Return if all keys in the keymap are set to True."""
        return False not in self._pressed_keys.values()

    def forward_release(self, forward: evdev.UInput) -> None:
        """Forward a button release for all keys if this is a combination

        this might cause duplicate key-up events but those are ignored by evdev anyway
        """
        if len(self._pressed_keys) == 1 or not self.mapping.release_combination_keys:
            return
        for type_and_code in self._pressed_keys:
            forward.write(*type_and_code, 0)
        forward.syn()

    def needs_ranking(self) -> bool:
        return bool(self.input_events)

    def rank_by(self) -> EventCombination:
        return EventCombination(
            event for event in self.input_events if event.value != 0
        )

    def wrap_with(self) -> Dict[EventCombination, HandlerEnums]:
        return_dict = {}
        for event in self.input_events:
            if event.type == EV_ABS and event.value != 0:
                return_dict[EventCombination(event)] = HandlerEnums.abs2btn

            if event.type == EV_REL and event.value != 0:
                return_dict[EventCombination(event)] = HandlerEnums.rel2btn

        return return_dict
