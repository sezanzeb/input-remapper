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

from typing import Dict, List, Optional, Type
from evdev.ecodes import EV_KEY

from inputremapper.logger import logger
from inputremapper.key import Key
from inputremapper.injection.consumers.mapping_handler import (
    MappingHandler,
    CombinationHandler,
    ContextProtocol,
    HierarchyHandler,
    )
from inputremapper.mapping import Mapping

MappingHandlers = Dict[Key, List[MappingHandler]]

mapping_handler_classes: Dict[str, Type[MappingHandler]] = {
    # all available mapping_handlers
    "combination": CombinationHandler,
}


def parse_mapping(mapping: Mapping, context: ContextProtocol) -> MappingHandlers:
    """create dict with a list of MappingHandlers for each key

    Key is of len 1
    """

    # create a handler for each mapping
    combination_handlers = {}
    normal_handlers = {}

    for key, sub_mapping in mapping:
        config = _create_new_config(key, sub_mapping)
        if config is None:
            continue

        _key = Key(config["key"])
        handler_type = config["type"]
        if handler_type == "combination":
            combination_handlers[_key] = _create_handler(config, context)
        else:
            assert _key not in normal_handlers.keys()
            normal_handlers[_key] = _create_handler(config, context)

    # create handlers for each key
    handlers = _create_hierarchy_handlers(combination_handlers)
    for key, handler in normal_handlers.items():
        assert len(key) == 1
        if key in handlers.keys():
            handlers[key].append(handler)
        else:
            handlers[key] = [handler]

    return handlers


def _create_handler(config: Dict[str, any], context) -> MappingHandler:
    """return the MappingHandler"""
    return mapping_handler_classes[config['type']](config, context)


def _create_hierarchy_handlers(handlers: Dict[Key, MappingHandler]) -> MappingHandlers:
    """sort handlers by sub_keys and create Hierarchy handlers"""
    # gather all single keys in all mappings
    sorted_handlers = {}
    all_keys = handlers.keys()
    keys = set()  # set of keys with len 1
    for key in all_keys:
        for sub_key in key:
            keys.add(sub_key)

    for single_key in keys:
        # find all original keys (from _original_handlers) which contain the key
        containing_keys = [og_key for og_key in all_keys if og_key.contains_event(*single_key[:2])]
        assert len(containing_keys) != 0
        if len(containing_keys) == 1:
            # there was only one handler containing that key
            sorted_handlers[single_key] = [handlers[containing_keys[0]]]
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

        hierarchy_handler = HierarchyHandler(sub_handlers)
        sorted_handlers[single_key] = [hierarchy_handler]
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
            logger.debug(f"idx: {j}, sub_key: {sub_key}")
            if sub_key == common_key:
                logger.debug(f"return: {j}")
                return j

    last_key = keys[0]
    last_idx = 0
    for i, key in enumerate([*keys[1:], ((None, None, None),)]):
        i += 1
        if len(key) == len(last_key):
            last_key = key
            continue

        assert len(key) < len(last_key)
        sub_list = keys[last_idx: i]
        sub_list.sort(key=idx_of_common_key, reverse=True)
        keys[last_idx: i] = sub_list

    return keys


def _create_new_config(key, symbol_and_target) -> Dict:
    # TODO: make this obsolete by migrating to new config structure
    config = {
        "key": key,
        "symbol": symbol_and_target[0],
        "target": symbol_and_target[1],
    }
    handler_type = _classify_config(config)
    if handler_type:
        config["type"] = handler_type
        return config


def _classify_config(config: Dict[str, any]) -> Optional[str]:
    """return the mapping_handler type"""
    # TODO: make this obsolete by including the type in the config
    key = Key(config["key"])
    for sub_key in key:
        if sub_key[0] is not EV_KEY:  # handler not yet implemented
            return

    return "combination"
