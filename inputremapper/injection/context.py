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


"""Stores injection-process wide information."""

from __future__ import annotations

from collections import defaultdict
from typing import List, Dict, Set, Hashable

import evdev

from inputremapper.configs.input_config import DeviceHash
from inputremapper.input_event import InputEvent
from inputremapper.configs.preset import Preset
from inputremapper.injection.mapping_handlers.mapping_handler import (
    EventListener,
    NotifyCallback,
)
from inputremapper.injection.mapping_handlers.mapping_parser import (
    parse_mappings,
    EventPipelines,
)
from inputremapper.logger import logger


class Context:
    """Stores injection-process wide information.

    In some ways this is a wrapper for the preset that derives some
    information that is specifically important to the injection.

    The information in the context does not change during the injection.

    One Context exists for each injection process, which is shared
    with all coroutines and used objects.

    Benefits of the context:
    - less redundant passing around of parameters
    - easier to add new process wide information without having to adjust
      all function calls in unittests
    - makes the injection class shorter and more specific to a certain task,
      which is actually spinning up the injection.

    Note, that for the reader_service a ContextDummy is used.

    Members
    -------
    preset : Preset
        The preset holds all Mappings for the injection process
    listeners : Set[EventListener]
        A set of callbacks which receive all events
    callbacks : Dict[Tuple[int, int], List[NotifyCallback]]
        All entry points to the event pipeline sorted by InputEvent.type_and_code
    """

    listeners: Set[EventListener]
    _notify_callbacks: Dict[Hashable, List[NotifyCallback]]
    _handlers: EventPipelines
    _forward_devices: Dict[DeviceHash, evdev.UInput]
    _source_devices: Dict[DeviceHash, evdev.InputDevice]

    def __init__(
        self,
        preset: Preset,
        source_devices: Dict[DeviceHash, evdev.InputDevice],
        forward_devices: Dict[DeviceHash, evdev.UInput],
    ):
        if len(forward_devices) == 0:
            logger.warning("Not forward_devices set")

        if len(source_devices) == 0:
            logger.warning("Not source_devices set")

        self.listeners = set()
        self._source_devices = source_devices
        self._forward_devices = forward_devices
        self._notify_callbacks = defaultdict(list)
        self._handlers = parse_mappings(preset, self)

        self._create_callbacks()

    def reset(self) -> None:
        """Call the reset method for each handler in the context."""
        for handlers in self._handlers.values():
            for handler in handlers:
                handler.reset()

    def _create_callbacks(self) -> None:
        """Add the notify method from all _handlers to self.callbacks."""
        for input_config, handler_list in self._handlers.items():
            input_match_hash = input_config.input_match_hash
            logger.info("Adding NotifyCallback for %s", input_match_hash)
            self._notify_callbacks[input_match_hash].extend(
                handler.notify for handler in handler_list
            )

    def get_notify_callbacks(self, input_event: InputEvent) -> List[NotifyCallback]:
        input_match_hash = input_event.input_match_hash
        return self._notify_callbacks[input_match_hash]

    def get_forward_uinput(self, origin_hash: DeviceHash) -> evdev.UInput:
        """Get the "forward" uinput events from the given origin should go into."""
        # TODO test
        return self._forward_devices[origin_hash]

    def get_source(self, key: DeviceHash) -> evdev.InputDevice:
        return self._source_devices[key]
