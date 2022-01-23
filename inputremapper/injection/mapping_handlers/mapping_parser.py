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
from typing import Dict, List, Type, Optional

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
from inputremapper.key import Key
from inputremapper.injection.mapping_handlers.mapping_handler import (
    MappingHandler,
    CombinationHandler,
    ContextProtocol,
    HierarchyHandler,
    AbsToBtnHandler,
    RelToBtnHandler,
    AbsToRelHandler,
)
from inputremapper.preset import Preset
from inputremapper.exceptions import Error

MappingHandlers = Dict[Key, List[MappingHandler]]

mapping_handler_classes: Dict[str, Type[MappingHandler]] = {
    # all available mapping_handlers
    "combination": CombinationHandler,
    "abs_to_rel": AbsToRelHandler,
}


def parse_mapping(preset: Preset, context: ContextProtocol) -> MappingHandlers:
    """create dict with a list of MappingHandlers for each key

    Key is of len 1
    """

    # create a handler for each mapping
    combination_handlers = {}
    normal_handlers = {}

    for key, mapping in preset:
        config = _create_new_config(key, mapping)
        if config is None:
            continue

        _key = Key(config["key"])
        handler_type = config["type"]
        if handler_type == "combination":
            handler = _create_handler(config, context)
            if handler:
                combination_handlers[_key] = handler
        else:
            assert _key not in normal_handlers.keys()
            handler = _create_handler(config, context)
            if handler:
                normal_handlers[_key] = handler

    # TODO: remove this for loop when Preset is done
    for config in _create_abs_to_rel_configs(preset):
        _key = Key(config["key"])
        handler_type = config["type"]
        assert handler_type == "abs_to_rel"
        assert _key not in normal_handlers.keys()
        handler = _create_handler(config, context)
        if handler:
            normal_handlers[_key] = handler

    # combine all combination handlers such that there is only one handler per single key
    # if multiple handlers contain the same key, a Hierarchy handler will be created
    hierarchy_handlers = _create_hierarchy_handlers(combination_handlers)
    handlers = {}
    for key, handler in hierarchy_handlers.items():
        assert len(key) == 1
        if key[0][0] == EV_KEY:
            logger.debug("created mapping handler:")
            logger.debug_mapping_handler(handler)
            handlers[key] = [handler]
            continue
        if key[0][0] == EV_ABS:
            handler = AbsToBtnHandler(handler, trigger_percent=key[0][2], key=key)
            logger.debug("created mapping handler:")
            logger.debug_mapping_handler(handler)
            handlers[key] = [handler]
            continue
        if key[0][0] == EV_REL:
            handler = RelToBtnHandler(handler, trigger_point=key[0][2], key=key)
            logger.debug("created mapping handler:")
            logger.debug_mapping_handler(handler)
            handlers[key] = [handler]
            continue

    for key, handler in normal_handlers.items():
        assert len(key) == 1
        if key in handlers.keys():
            logger.debug("created mapping handler:")
            logger.debug_mapping_handler(handler)
            handlers[key].append(handler)
        else:
            logger.debug("created mapping handler:")
            logger.debug_mapping_handler(handler)
            handlers[key] = [handler]

    return handlers


def _create_handler(config: Dict[str, any], context) -> Optional[MappingHandler]:
    """return the MappingHandler"""
    try:
        return mapping_handler_classes[config["type"]](config, context)
    except Error as error:  # only catch inputremapper.exceptions
        logger.error(f"{error.__class__.__name__}: {str(error)}")
        logger.debug("".join(traceback.format_tb(error.__traceback__)).strip())
        return None


def _create_hierarchy_handlers(handlers: Dict[Key, MappingHandler]) -> Dict[Key, MappingHandler]:
    """sort handlers by sub_keys and create Hierarchy handlers"""
    # gather all single keys in all mappings
    sorted_handlers = {}
    all_keys = handlers.keys()
    keys = set()  # set of keys with len 1
    for key in all_keys:
        for sub_key in key:
            keys.add(sub_key)

    for single_key in keys:
        # find all original keys (from handlers) which contain the key
        containing_keys = [
            og_key for og_key in all_keys if og_key.contains_key(single_key)
        ]
        assert len(containing_keys) != 0
        if len(containing_keys) == 1:
            # there was only one handler containing that key
            sorted_handlers[Key(single_key)] = handlers[containing_keys[0]]
            continue

        keys_to_sort = []
        for og_key in containing_keys:
            keys_to_sort.append(og_key)

        assert len(keys_to_sort) > 1
        # rank the keys and create the HierarchyHandler
        sorted_keys = _order_keys(keys_to_sort, single_key)
        sub_handlers = []
        for og_key in sorted_keys:
            sub_handlers.append(handlers[og_key])

        hierarchy_handler = HierarchyHandler(sub_handlers, single_key[:2])
        sorted_handlers[Key(single_key)] = hierarchy_handler
    return sorted_handlers


def _order_keys(keys: List[Key], common_key: Key) -> List[Key]:
    """reorder the keys according to some rules

    such that a combination a+b+c is in front of a+b which is in front of b
    for a+b+c vs. b+d+e: a+b+c would be in front of b+d+e, because the common key b
    has the higher index in the a+b+c (1), than in the b+c+d (0) list
    in this example b would be the common key
    as for combinations like a+b+c and e+d+c with the common key c: ¯\_(ツ)_/¯

    Parameters
    ----------
    keys : List[Key]
        the list which needs ordering
    common_key : Key
        the Key all members of Keys have in common
    """
    keys.sort(key=len, reverse=True)  # sort by descending length

    def idx_of_common_key(_key: Key) -> int:
        """get the index of the common key in _key"""
        for j, sub_key in enumerate(_key):
            if sub_key == common_key:
                return j

    last_key = keys[0]
    last_idx = 0
    for i, key in enumerate([*keys[1:], ((None, None, None),)]):
        i += 1
        if len(key) == len(last_key):
            last_key = key
            continue

        assert len(key) < len(last_key)
        sub_list = keys[last_idx:i]
        sub_list.sort(key=idx_of_common_key, reverse=True)
        keys[last_idx:i] = sub_list

    return keys


def _create_new_config(key, symbol_and_target) -> Dict:
    # TODO: make this obsolete by migrating to new config structure
    sub_keys = []
    for sub_key in key:
        if sub_key[0] != EV_ABS:
            sub_keys.append(sub_key)
            continue
        if sub_key[2] == 1:
            sub_keys.append((*sub_key[:2], 10))  # trigger point at 10%
        else:
            assert sub_key[2] == -1
            sub_keys.append((*sub_key[:2], -10))  # trigger point at -10%
    new_key = Key(*sub_keys)

    config = {
        "key": new_key,
        "symbol": symbol_and_target[0],
        "target": symbol_and_target[1],
        "type": "combination"
    }
    return config


def _create_abs_to_rel_configs(preset: Preset) -> list[Dict[str, any]]:
    # TODO: make this obsolete by migrating to new config structure
    """ return a list of configs with the keys:
    config : Dict = {
        "key": str
        "output": int
        "target": str
        "deadzone" : int
        "output" : int
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
        "key": None,
        "target": "mouse",
        "deadzone": 0.1,
        "output": REL_X,
        "gain": pointer_speed,
        "expo": 0,
        "rate": 100,
        "type": "abs_to_rel"
    }
    mouse_y_config = {
        "key": None,
        "target": "mouse",
        "deadzone": 0.1,
        "output": REL_Y,
        "gain": pointer_speed,
        "expo": 0,
        "rate": 100,
        "type": "abs_to_rel"
    }
    wheel_x_config = {
        "key": None,
        "target": "mouse",
        "deadzone": 0.1,
        "output": REL_HWHEEL_HI_RES,
        "gain": 1,
        "expo": 0.5,
        "rate": 100,
        "type": "abs_to_rel"
    }
    wheel_y_config = {
        "key": None,
        "target": "mouse",
        "deadzone": 0.1,
        "output": REL_WHEEL_HI_RES,
        "gain": 1,
        "expo": 0.5,
        "rate": 100,
        "type": "abs_to_rel"
    }
    configs = []

    if left_purpose == "mouse":
        x_config = mouse_x_config.copy()
        y_config = mouse_y_config.copy()
        x_config["key"] = Key((EV_ABS, ABS_X, 0))
        y_config["key"] = Key((EV_ABS, ABS_Y, 0))
        configs.extend([x_config, y_config])

    if left_purpose == "wheel":
        w_x_config = wheel_x_config.copy()
        w_y_config = wheel_y_config.copy()
        w_x_config["key"] = Key((EV_ABS, ABS_X, 0))
        w_y_config["key"] = Key((EV_ABS, ABS_Y, 0))
        configs.extend([w_x_config, w_y_config])

    if right_purpose == "mouse":
        x_config = mouse_x_config.copy()
        y_config = mouse_y_config.copy()
        x_config["key"] = Key((EV_ABS, ABS_RX, 0))
        y_config["key"] = Key((EV_ABS, ABS_RY, 0))
        configs.extend([x_config, y_config])

    if right_purpose == "wheel":
        w_x_config = wheel_x_config.copy()
        w_y_config = wheel_y_config.copy()
        w_x_config["key"] = Key((EV_ABS, ABS_RX, 0))
        w_y_config["key"] = Key((EV_ABS, ABS_RY, 0))
        configs.extend([w_x_config, w_y_config])

    return configs
