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
"""Functions to assemble the mapping handlers"""
from collections import defaultdict
from typing import Dict, List, Type, Optional, Set, Iterable, Sized, Tuple, Sequence

from evdev.ecodes import (
    EV_KEY,
    EV_ABS,
    EV_REL,
)

from inputremapper.configs.mapping import Mapping
from inputremapper.configs.preset import Preset
from inputremapper.configs.system_mapping import DISABLE_CODE, DISABLE_NAME
from inputremapper.event_combination import EventCombination
from inputremapper.exceptions import MappingParsingError
from inputremapper.injection.macros.parse import is_this_a_macro
from inputremapper.injection.mapping_handlers.abs_to_abs_handler import AbsToAbsHandler
from inputremapper.injection.mapping_handlers.abs_to_btn_handler import AbsToBtnHandler
from inputremapper.injection.mapping_handlers.abs_to_rel_handler import AbsToRelHandler
from inputremapper.injection.mapping_handlers.axis_switch_handler import (
    AxisSwitchHandler,
)
from inputremapper.injection.mapping_handlers.combination_handler import (
    CombinationHandler,
)
from inputremapper.injection.mapping_handlers.hierarchy_handler import HierarchyHandler
from inputremapper.injection.mapping_handlers.key_handler import KeyHandler
from inputremapper.injection.mapping_handlers.macro_handler import MacroHandler
from inputremapper.injection.mapping_handlers.mapping_handler import (
    HandlerEnums,
    MappingHandler,
    ContextProtocol,
    InputEventHandler,
)
from inputremapper.injection.mapping_handlers.null_handler import NullHandler
from inputremapper.injection.mapping_handlers.rel_to_abs_handler import RelToAbsHandler
from inputremapper.injection.mapping_handlers.rel_to_btn_handler import RelToBtnHandler
from inputremapper.input_event import InputEvent
from inputremapper.logger import logger

EventPipelines = Dict[InputEvent, Set[InputEventHandler]]

mapping_handler_classes: Dict[HandlerEnums, Optional[Type[MappingHandler]]] = {
    # all available mapping_handlers
    HandlerEnums.abs2btn: AbsToBtnHandler,
    HandlerEnums.rel2btn: RelToBtnHandler,
    HandlerEnums.macro: MacroHandler,
    HandlerEnums.key: KeyHandler,
    HandlerEnums.btn2rel: None,  # can be a macro
    HandlerEnums.rel2rel: None,
    HandlerEnums.abs2rel: AbsToRelHandler,
    HandlerEnums.btn2abs: None,  # can be a macro
    HandlerEnums.rel2abs: RelToAbsHandler,
    HandlerEnums.abs2abs: AbsToAbsHandler,
    HandlerEnums.combination: CombinationHandler,
    HandlerEnums.hierarchy: HierarchyHandler,
    HandlerEnums.axisswitch: AxisSwitchHandler,
    HandlerEnums.disable: NullHandler,
}


def parse_mappings(preset: Preset, context: ContextProtocol) -> EventPipelines:
    """Create a dict with a list of MappingHandler for each InputEvent."""
    handlers = []
    for mapping in preset:
        # start with the last handler in the chain, each mapping only has one output,
        # but may have multiple inputs, therefore the last handler is a good starting
        # point to assemble the pipeline
        handler_enum = _get_output_handler(mapping)
        constructor = mapping_handler_classes[handler_enum]
        if not constructor:
            logger.warning(
                "a mapping handler '%s' for %s is not implemented",
                handler_enum,
                mapping.name or mapping.event_combination.beautify(),
            )
            continue

        output_handler = constructor(
            mapping.event_combination,
            mapping,
            context=context,
        )

        # layer other handlers on top until the outer handler needs ranking or can
        # directly handle a input event
        handlers.extend(_create_event_pipeline(output_handler, context))

    # figure out which handlers need ranking and wrap them with hierarchy_handlers
    need_ranking = defaultdict(set)
    for handler in handlers.copy():
        if handler.needs_ranking():
            combination = handler.rank_by()
            if not combination:
                raise MappingParsingError(
                    f"{type(handler).__name__} claims to need ranking but does not "
                    f"return a combination to rank by",
                    mapping_handler=handler,
                )
            need_ranking[combination].add(handler)
            handlers.remove(handler)

    # the HierarchyHandler's might not be the starting point of the event pipeline
    # layer other handlers on top again.
    ranked_handlers = _create_hierarchy_handlers(need_ranking)
    for handler in ranked_handlers:
        handlers.extend(_create_event_pipeline(handler, context, ignore_ranking=True))

    # group all handlers by the input events they take care of. One handler might end
    # up in multiple groups if it takes care of multiple InputEvents
    event_pipelines: EventPipelines = defaultdict(set)
    for handler in handlers:
        assert handler.input_events
        for event in handler.input_events:
            logger.debug("event-pipeline with entry point: %s", event.type_and_code)
            logger.debug_mapping_handler(handler)
            event_pipelines[event].add(handler)

    return event_pipelines


def _create_event_pipeline(
    handler: MappingHandler, context: ContextProtocol, ignore_ranking=False
) -> List[MappingHandler]:
    """Recursively wrap a handler with other handlers until the
    outer handler needs ranking or is finished wrapping
    """
    if not handler.needs_wrapping() or (handler.needs_ranking() and not ignore_ranking):
        return [handler]

    handlers = []
    for combination, handler_enum in handler.wrap_with().items():
        constructor = mapping_handler_classes[handler_enum]
        if not constructor:
            raise NotImplementedError(
                f"mapping handler {handler_enum} is not implemented"
            )

        super_handler = constructor(combination, handler.mapping, context=context)
        super_handler.set_sub_handler(handler)
        for event in combination:
            # the handler now has a super_handler which takes care about the events.
            # so we need to hide them on the handler
            handler.occlude_input_event(event)

        handlers.extend(_create_event_pipeline(super_handler, context))

    if handler.input_events:
        # the handler was only partially wrapped,
        # we need to return it as a toplevel handler
        handlers.append(handler)

    return handlers


def _get_output_handler(mapping: Mapping) -> HandlerEnums:
    """Determine the correct output handler
    this is used as a starting point for the mapping parser
    """
    if mapping.output_code == DISABLE_CODE or mapping.output_symbol == DISABLE_NAME:
        return HandlerEnums.disable

    if mapping.output_symbol:
        if is_this_a_macro(mapping.output_symbol):
            return HandlerEnums.macro
        else:
            return HandlerEnums.key

    if mapping.output_type == EV_KEY:
        return HandlerEnums.key

    input_event = _maps_axis(mapping.event_combination)
    if not input_event:
        raise MappingParsingError(
            f"this {mapping = } does not map to an axis, key or macro",
            mapping=Mapping,
        )

    if mapping.output_type == EV_REL:
        if input_event.type == EV_KEY:
            return HandlerEnums.btn2rel
        if input_event.type == EV_REL:
            return HandlerEnums.rel2rel
        if input_event.type == EV_ABS:
            return HandlerEnums.abs2rel

    if mapping.output_type == EV_ABS:
        if input_event.type == EV_KEY:
            return HandlerEnums.btn2abs
        if input_event.type == EV_REL:
            return HandlerEnums.rel2abs
        if input_event.type == EV_ABS:
            return HandlerEnums.abs2abs

    raise MappingParsingError(f"the output of {mapping = } is unknown", mapping=Mapping)


def _maps_axis(combination: EventCombination) -> Optional[InputEvent]:
    """Whether this EventCombination contains an InputEvent that is treated as
    an axis and not a binary (key or button) event.
    """
    for event in combination:
        if event.value == 0:
            return event
    return None


def _create_hierarchy_handlers(
    handlers: Dict[EventCombination, Set[MappingHandler]]
) -> Set[MappingHandler]:
    """Sort handlers by input events and create Hierarchy handlers."""
    sorted_handlers = set()
    all_combinations = handlers.keys()
    events = set()

    # gather all InputEvents from all handlers
    for combination in all_combinations:
        for event in combination:
            events.add(event)

    # create a ranking for each event
    for event in events:
        # find all combinations (from handlers) which contain the event
        combinations_with_event = [
            combination for combination in all_combinations if event in combination
        ]

        if len(combinations_with_event) == 1:
            # there was only one handler containing that event return it as is
            sorted_handlers.update(handlers[combinations_with_event[0]])
            continue

        # there are multiple handler with the same event.
        # rank them and create the HierarchyHandler
        sorted_combinations = _order_combinations(combinations_with_event, event)
        sub_handlers: List[MappingHandler] = []
        for combination in sorted_combinations:
            sub_handlers.append(*handlers[combination])

        sorted_handlers.add(HierarchyHandler(sub_handlers, event))
        for handler in sub_handlers:
            # the handler now has a HierarchyHandler which takes care about this event.
            # so we hide need to hide it on the handler
            handler.occlude_input_event(event)

    return sorted_handlers


def _order_combinations(
    combinations: List[EventCombination], common_event: InputEvent
) -> List[EventCombination]:
    """Reorder the keys according to some rules

    such that a combination a+b+c is in front of a+b which is in front of b
    for a+b+c vs. b+d+e: a+b+c would be in front of b+d+e, because the common key b
    has the higher index in the a+b+c (1), than in the b+c+d (0) list
    in this example b would be the common key
    as for combinations like a+b+c and e+d+c with the common key c: ¯\\_(ツ)_/¯

    Parameters
    ----------
    combinations : List[Key]
        the list which needs ordering
    common_event : InputEvent
        the Key all members of Keys have in common
    """
    combinations.sort(key=len)

    for start, end in ranges_with_constant_length(combinations.copy()):
        sub_list = combinations[start:end]
        sub_list.sort(key=lambda x: x.index(common_event))
        combinations[start:end] = sub_list

    combinations.reverse()
    return combinations


def ranges_with_constant_length(x: Sequence[Sized]) -> Iterable[Tuple[int, int]]:
    """Get all ranges of x for which the elements have constant length

    Parameters
    ----------
    x: Sequence[Sized]
        l must be ordered by increasing length of elements
    """
    start_idx = 0
    last_len = 0
    for idx, y in enumerate(x):
        if len(y) > last_len and idx - start_idx > 1:
            yield start_idx, idx

        if len(y) == last_len and idx + 1 == len(x):
            yield start_idx, idx + 1

        if len(y) > last_len:
            start_idx = idx

        if len(y) < last_len:
            raise MappingParsingError(
                "ranges_with_constant_length " "was called with an unordered list"
            )
        last_len = len(y)
