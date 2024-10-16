# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2023 sezanzeb <proxima@sezanzeb.de>
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
from typing import TYPE_CHECKING, Dict, Hashable, Tuple

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
    # the last update we sent to a sub-handler. If this is true, the output key is
    # still being held down.
    _output_active: bool
    _sub_handler: InputEventHandler
    _handled_input_hashes: list[Hashable]
    _requires_a_release: Dict[Tuple[int, int], bool]

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
        self._output_active = False
        self._context = context
        self._requires_a_release = {}

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

        # update the state
        # The value of non-key input should have been changed to either 0 or 1 at this
        # point by other handlers.
        is_pressed = event.value == 1
        self._pressed_keys[event.input_match_hash] = is_pressed
        # maybe this changes the activation status (triggered/not-triggered)
        is_activated = self.is_activated()

        if is_activated == self._output_active:
            # nothing changed
            if is_pressed:
                # If the output is active, a key-down event triggered it, which then
                # did not get forwarded, therefore it doesn't require a release.
                self.require_release_later(not self._output_active, event)
                # output is active: consume the event
                # output inactive: forward the event
                return self._output_active
            else:
                # Else if it is released: Returning `False` means that the event-reader
                # will forward the release.
                return not self.should_release_event(event)

        if is_activated:
            event = event.modify(value=1)
        else:
            # If not activated. All required keys are not yet pressed.
            if self._output_active or self.mapping.is_axis_mapping():
                # we ignore the `suppress` argument for release events
                # otherwise we might end up with stuck keys
                # (test_event_pipeline.test_combination)

                # we also ignore it if the mapping specifies an output axis
                # this will enable us to activate multiple axis with the same button
                suppress = False
            event = event.modify(value=0)

        if not suppress:
            if is_activated:
                # Send key up events to the forwarded uinput if configured to do so.
                self.forward_release()

            logger.debug("Sending %s to sub-handler", self.mapping.input_combination)
            self._output_active = bool(event.value)
            sub_handler_result = self._sub_handler.notify(event, source, suppress)

            if is_pressed:
                # If the sub-handler return True, it handled the event, so the user never
                # sees this key-down event. In that case, we don't require a release event.
                self.require_release_later(not sub_handler_result, event)
                return sub_handler_result
            else:
                # Else if it is released: Returning `False` means that the event-reader
                # will forward the release.
                return not self.should_release_event(event)

        return False

    def should_release_event(self, event: InputEvent) -> bool:
        """Check if the key-up event should be forwarded by the event-reader.

        After this, the release event needs to be injected by someone, otherwise the
        dictionary was modified erroneously. If there is no entry, we assume that there
        was no key-down event to release. Maybe a duplicate event arrived.
        """
        # Ensure that all injected key-down events will get their release event
        # injected eventually.
        # If a key-up event arrives that will inactivate the combination, but
        # for which previously a key-down event was injected (because it was
        # an earlier key in the combination chain), then we need to ensure that its
        # release is injected as well. So we get two release events in that case:
        # one for the key, and one for the output.
        assert event.value == 0
        return self._requires_a_release.pop(event.type_and_code, False)

    def require_release_later(self, require: bool, event: InputEvent) -> None:
        """Remember if this key-down event will need a release event later on."""
        assert event.value == 1
        self._requires_a_release[event.type_and_code] = require

    def reset(self) -> None:
        self._sub_handler.reset()
        for key in self._pressed_keys:
            self._pressed_keys[key] = False
        self._requires_a_release = {}
        self._output_active = False

    def is_activated(self) -> bool:
        """Return if all keys in the keymap are set to True."""
        return False not in self._pressed_keys.values()

    def forward_release(self) -> None:
        """Forward a button release for all keys if this is a combination.

        This might cause duplicate key-up events but those are ignored by evdev anyway
        """
        if len(self._pressed_keys) == 1 or not self.mapping.release_combination_keys:
            return

        keys_to_release = filter(
            lambda cfg: self._pressed_keys.get(cfg.input_match_hash),
            self.mapping.input_combination,
        )

        logger.debug("Forwarding release for %s", self.mapping.input_combination)

        for input_config in keys_to_release:
            if not self._requires_a_release.get(input_config.type_and_code):
                continue

            origin_hash = input_config.origin_hash
            if origin_hash is None:
                logger.error(
                    f"Can't forward due to missing origin_hash in {repr(input_config)}"
                )
                continue

            forward_to = self._context.get_forward_uinput(origin_hash)
            logger.write(input_config, forward_to)
            forward_to.write(*input_config.type_and_code, 0)
            forward_to.syn()

            # We are done with this key, forget about it
            del self._requires_a_release[input_config.type_and_code]

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
