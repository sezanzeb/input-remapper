#!/usr/bin/python3
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
"""functions to assemble the mapping handlers"""

import traceback
from typing import Dict, List, Type, Optional, Tuple

from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    EV_REL,
    ABS_X,
    ABS_Y,
    ABS_RX,
    ABS_RY,
    REL_X,
    REL_Y,
    REL_WHEEL_HI_RES,
    REL_HWHEEL_HI_RES,
)

from inputremapper.logger import logger
from inputremapper.event_combination import EventCombination
from inputremapper.input_event import InputEvent
from inputremapper.injection.mapping_handlers.mapping_handler import (
    MappingHandler,
    ContextProtocol,
)
from inputremapper.injection.mapping_handlers.combination_handler import (
    CombinationHandler,
)
from inputremapper.injection.mapping_handlers.hierarchy_handler import HierarchyHandler
from inputremapper.injection.mapping_handlers.abs_to_btn_handler import AbsToBtnHandler
from inputremapper.injection.mapping_handlers.rel_to_btn_handler import RelToBtnHandler
from inputremapper.injection.mapping_handlers.abs_to_rel_handler import AbsToRelHandler
from inputremapper.configs.preset import Preset
from inputremapper.exceptions import Error

MappingHandlers = Dict[InputEvent, List[MappingHandler]]

mapping_handler_classes: Dict[str, Type[MappingHandler]] = {
    # all available mapping_handlers
    "combination": CombinationHandler,
    "abs_to_rel": AbsToRelHandler,
}


def parse_mapping(preset: Preset, context: ContextProtocol) -> MappingHandlers:
    """create dict with a list of MappingHandlers for each InputEvent

    EventCombination is of len 1
    """

    # create a handler for each mapping
    combination_handlers: Dict[EventCombination, MappingHandler] = {}
    normal_handlers: Dict[EventCombination, MappingHandler] = {}

    for event, mapping in preset:
        config = _create_new_config(event, mapping)
        if config is None:
            continue

        combination = EventCombination.from_string(config["combination"])
        handler_type = config["type"]
        if handler_type == "combination":
            handler = _create_handler(config, context)
            if handler:
                combination_handlers[combination] = handler
        else:
            assert combination not in normal_handlers.keys()
            handler = _create_handler(config, context)
            if handler:
                normal_handlers[combination] = handler

    # TODO: remove this for loop when Preset is done
    for config in _create_abs_to_rel_configs(preset):
        combination = EventCombination.from_string(config["combination"])
        handler_type = config["type"]
        assert handler_type == "abs_to_rel"
        assert combination not in normal_handlers.keys()
        handler = _create_handler(config, context)
        if handler:
            normal_handlers[combination] = handler

    # combine all combination-handlers such that there is only one handler per event
    # if multiple handlers contain the same event, a Hierarchy handler will be created
    hierarchy_handlers = _create_hierarchy_handlers(combination_handlers)
    handlers = {}
    for event, handler in hierarchy_handlers.items():
        if event.type == EV_KEY:
            logger.debug("created mapping handler:")
            logger.debug_mapping_handler(handler)
            handlers[event] = [handler]
            continue
        if event.type == EV_ABS:
            # wrap the hierarchy handler in a AbsToBtnHandler
            handler = AbsToBtnHandler(handler, trigger_percent=event.value, event=event)
            logger.debug("created mapping handler:")
            logger.debug_mapping_handler(handler)
            handlers[event] = [handler]
            continue
        if event.type == EV_REL:
            # wrap the hierarchy handler in a RelToBtnHandler
            handler = RelToBtnHandler(handler, trigger_point=event.value, event=event)
            logger.debug("created mapping handler:")
            logger.debug_mapping_handler(handler)
            handlers[event] = [handler]
            continue

    # add all other handlers to the handlers dict,
    # once for each event the handler cares about
    for combination, handler in normal_handlers.items():
        for event in combination:
            if event in handlers.keys():
                logger.debug("created mapping handler:")
                logger.debug_mapping_handler(handler)
                handlers[event].append(handler)
            else:
                logger.debug("created mapping handler:")
                logger.debug_mapping_handler(handler)
                handlers[event] = [handler]

    return handlers


def _create_handler(config: Dict[str, any], context) -> Optional[MappingHandler]:
    """return the MappingHandler"""
    try:
        return mapping_handler_classes[config["type"]](config, context)
    except Error as error:  # only catch inputremapper.exceptions
        logger.error(f"{error.__class__.__name__}: {str(error)}")
        logger.debug("".join(traceback.format_tb(error.__traceback__)).strip())
        return None


def _create_hierarchy_handlers(
    handlers: Dict[EventCombination, MappingHandler]
) -> Dict[InputEvent, MappingHandler]:
    """sort handlers by sub_keys and create Hierarchy handlers"""
    # gather all InputEvents from all mappings
    sorted_handlers = {}
    all_combinations = handlers.keys()
    events = set()  # set of keys with len 1
    for combination in all_combinations:
        for event in combination:
            events.add(event)

    for event in events:
        # find all combinations (from handlers) which contain the event
        combinations_with_event = [
            combination for combination in all_combinations if event in combination
        ]
        assert len(combinations_with_event) != 0
        if len(combinations_with_event) == 1:
            # there was only one handler containing that event
            sorted_handlers[event] = handlers[combinations_with_event[0]]
            continue

        # there are multiple handler with the same event.
        # rank them and create the HierarchyHandler
        sorted_combinations = _order_combinations(combinations_with_event, event)
        sub_handlers = []
        for combination in sorted_combinations:
            sub_handlers.append(handlers[combination])

        hierarchy_handler = HierarchyHandler(sub_handlers, event)
        sorted_handlers[event] = hierarchy_handler
    return sorted_handlers


def _order_combinations(
    combinations: List[EventCombination], common_event: InputEvent
) -> List[EventCombination]:
    """reorder the keys according to some rules

    such that a combination a+b+c is in front of a+b which is in front of b
    for a+b+c vs. b+d+e: a+b+c would be in front of b+d+e, because the common key b
    has the higher index in the a+b+c (1), than in the b+c+d (0) list
    in this example b would be the common key
    as for combinations like a+b+c and e+d+c with the common key c: ¯\_(ツ)_/¯

    Parameters
    ----------
    combinations : List[Key]
        the list which needs ordering
    common_event : InputEvent
        the Key all members of Keys have in common
    """
    combinations.sort(key=len, reverse=True)  # sort by descending length

    def idx_of_common_event(_combination: EventCombination) -> int:
        """get the index of the common event in _combination"""
        for j, event in enumerate(_combination):
            if event == common_event:
                return j

    last_combination = combinations[0]
    last_idx = 0
    for i, combination in enumerate([*combinations[1:], ((None, None, None),)]):
        i += 1
        if len(combination) == len(last_combination):
            last_combination = combination
            continue

        assert len(combination) < len(last_combination)
        sub_list = combinations[last_idx:i]
        sub_list.sort(key=idx_of_common_event, reverse=True)
        combinations[last_idx:i] = sub_list

    return combinations


def _create_new_config(
    combination: EventCombination, symbol_and_target: Tuple[str, str]
) -> Dict:
    # TODO: make this obsolete by migrating to new config structure
    events = []
    for event in combination:
        if event.type != EV_ABS:
            events.append(event)
            continue

        if event.value == 1:
            events.append(event.modify(value=10))  # trigger point at 10%
        else:
            assert event.value == -1
            events.append(event.modify(value=-10))  # trigger point at -10%
    combination = EventCombination.from_events(events)

    config = {
        "combination": combination.json_str(),
        "symbol": symbol_and_target[0],
        "target": symbol_and_target[1],
        "type": "combination",
    }
    return config


def _create_abs_to_rel_configs(preset: Preset) -> list[Dict[str, any]]:
    # TODO: make this obsolete by migrating to new config structure
    """return a list of configs with the keys:
    config : Dict = {
        "combination": str
        "output": int
        "target": str
        "deadzone" : float
        "expo" : float
        "gain" : float
        "rate" : int
    }
    """
    left_purpose = preset.get("gamepad.joystick.left_purpose")
    right_purpose = preset.get("gamepad.joystick.right_purpose")
    pointer_speed = preset.get("gamepad.joystick.pointer_speed") / 100
    non_linearity = preset.get("gamepad.joystick.non_linearity")
    x_scroll_speed = preset.get("gamepad.joystick.x_scroll_speed")
    y_scroll_speed = preset.get("gamepad.joystick.y_scroll_speed")

    mouse_x_config = {
        "combination": None,
        "target": "mouse",
        "deadzone": 0.1,
        "output": REL_X,
        "gain": pointer_speed,
        "expo": 0,
        "rate": 100,
        "type": "abs_to_rel",
    }
    mouse_y_config = {
        "combination": None,
        "target": "mouse",
        "deadzone": 0.1,
        "output": REL_Y,
        "gain": pointer_speed,
        "expo": 0,
        "rate": 100,
        "type": "abs_to_rel",
    }
    wheel_x_config = {
        "combination": None,
        "target": "mouse",
        "deadzone": 0.1,
        "output": REL_HWHEEL_HI_RES,
        "gain": 1,
        "expo": 0.5,
        "rate": 100,
        "type": "abs_to_rel",
    }
    wheel_y_config = {
        "combination": None,
        "target": "mouse",
        "deadzone": 0.1,
        "output": REL_WHEEL_HI_RES,
        "gain": 1,
        "expo": 0.5,
        "rate": 100,
        "type": "abs_to_rel",
    }
    configs = []

    if left_purpose == "mouse":
        x_config = mouse_x_config.copy()
        y_config = mouse_y_config.copy()
        x_config["combination"] = ",".join((str(EV_ABS), str(ABS_X), "0"))
        y_config["combination"] = ",".join((str(EV_ABS), str(ABS_Y), "0"))
        configs.extend([x_config, y_config])

    if left_purpose == "wheel":
        w_x_config = wheel_x_config.copy()
        w_y_config = wheel_y_config.copy()
        w_x_config["combination"] = ",".join((str(EV_ABS), str(ABS_X), "0"))
        w_y_config["combination"] = ",".join((str(EV_ABS), str(ABS_Y), "0"))
        configs.extend([w_x_config, w_y_config])

    if right_purpose == "mouse":
        x_config = mouse_x_config.copy()
        y_config = mouse_y_config.copy()
        x_config["combination"] = ",".join((str(EV_ABS), str(ABS_RX), "0"))
        y_config["combination"] = ",".join((str(EV_ABS), str(ABS_RY), "0"))
        configs.extend([x_config, y_config])

    if right_purpose == "wheel":
        w_x_config = wheel_x_config.copy()
        w_y_config = wheel_y_config.copy()
        w_x_config["combination"] = ",".join((str(EV_ABS), str(ABS_RX), "0"))
        w_y_config["combination"] = ",".join((str(EV_ABS), str(ABS_RY), "0"))
        configs.extend([w_x_config, w_y_config])

    return configs
