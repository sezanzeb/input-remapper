#!/usr/bin/python3
# -*- coding: utf-8 -*-
# key-mapper - GUI for device specific keyboard mappings
# Copyright (C) 2020 sezanzeb <proxima@hip70890b.de>
#
# This file is part of key-mapper.
#
# key-mapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# key-mapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with key-mapper.  If not, see <https://www.gnu.org/licenses/>.


"""Inject a keycode based on the mapping."""


import itertools
import asyncio

from evdev.ecodes import EV_KEY, EV_ABS

from keymapper.logger import logger
from keymapper.util import sign
from keymapper.dev.ev_abs_mapper import JOYSTICK


# maps mouse buttons to macro instances that have been executed. They may
# still be running or already be done. Just like unreleased, this is a
# mapping of (type, code). The value is not included in the key, because
# a key release event with a value of 0 needs to be able to find the
# running macro. The downside is that a d-pad cannot execute two macros at
# once, one for each direction. Only sequentially.
active_macros = {}

# mapping of future up event (type, code) to (output code, input event)
# This is needed in order to release the correct event mapped on a
# D-Pad. Each direction on one D-Pad axis reports the same type and
# code, but different values. There cannot be both at the same time,
# as pressing one side of a D-Pad forces the other side to go up.
# "I have got this release event, what was this for?"
# It maps to (output_code, input_event) with input_event being the
# same as the key, but with the value of e.g. -1 or 1. The complete
# 3-tuple output event is used to track if a combined button press was done.
# A combination might be desired for D-Pad left, but not D-Pad right.
# (what_will_be_released, what_caused_the_key_down)
unreleased = {}


def should_map_event_as_btn(ev_type, code):
    """Does this event describe a button.

    Especially important for gamepad events, some of the buttons
    require special rules.

    Parameters
    ----------
    ev_type : int
        one of evdev.events
    code : int
        linux keycode
    """
    if ev_type == EV_KEY:
        return True

    if ev_type == EV_ABS:
        is_mousepad = 47 <= code <= 61
        if not is_mousepad and code not in JOYSTICK:
            return True

    return False


def is_key_down(event):
    """Is this event a key press."""
    return event.value != 0


def is_key_up(event):
    """Is this event a key release."""
    return event.value == 0


def write(uinput, key):
    """Shorthand to write stuff."""
    uinput.write(*key)
    uinput.syn()


COMBINATION_INCOMPLETE = 1  # not all keys of the combination are pressed
NOT_COMBINED = 2  # this key is not part of a combination


def subsets(combination):
    """Return a list of subsets of the combination.

    If combination is only one element long it returns an empty list,
    because it's not a combination and there is no reason to iterate.

    Parameters
    -----------
    combination : tuple
        tuple of 3-tuples, each being int, int, int (type, code, value)
    """
    combination = list(combination)
    lengths = list(range(2, len(combination) + 1))
    lengths.reverse()
    return list(itertools.chain.from_iterable(
        itertools.combinations(combination, length)
        for length in lengths
    ))


def handle_keycode(key_to_code, macros, event, uinput):
    """Write mapped keycodes, forward unmapped ones and manage macros.

    Parameters
    ----------
    key_to_code : dict
        mapping of (type, code, value) to linux-keycode
        or multiple of those like ((...), (...), ...) for combinations
        combinations need to be present in every possible valid ordering.
        e.g. shift + alt + a and alt + shift + a
    macros : dict
        mapping of (type, code, value) to _Macro objects.
        Combinations work similar as in key_to_code
    event : evdev.InputEvent
    """
    if event.type == EV_KEY and event.value == 2:
        # button-hold event. Linux creates them on its own for the
        # injection-fake-device if the release event won't appear,
        # no need to forward or map them.
        return

    # normalize event numbers to one of -1, 0, +1. Otherwise mapping
    # trigger values that are between 1 and 255 is not possible, because
    # they might skip the 1 when pressed fast enough.
    # The key used to index the mappings `key_to_code` and `macros`
    key = (event.type, event.code, sign(event.value))

    # the tuple of the actual input event. Used to forward the event if it is
    # not mapped, and to index unreleased and active_macros
    event_tuple = (event.type, event.code, sign(event.value))
    type_code = (event.type, event.code)

    # the triggering key-down has to be the last element in combination, all
    # others can have any arbitrary order. By checking all unreleased keys,
    # a + b + c takes priority over b + c, if both mappings exist.
    # WARNING! the combination-down triggers, but a single key-up releases.
    # Do not check if key in macros and such, if it is an up event. It's
    # going to be False.
    combination = tuple([value[1] for value in unreleased.values()] + [key])
    # find any triggered combination. macros and key_to_code contain
    # every possible equivalent permutation of possible macros. The last
    # key in the combination needs to remain the newest key though.
    for subset in subsets(combination):
        if subset[-1] != key:
            # only combinations that are completed and triggered by the
            # newest input are of interest
            continue

        if subset in macros or subset in key_to_code:
            key = subset
            break
    else:
        # no subset found, just use the key. all indices are tuples of tuples,
        # both for combinations and single keys.
        key = (key,)

    active_macro = active_macros.get(type_code)

    """Releasing keys and macros"""

    if is_key_up(event):
        if active_macro is not None and active_macro.holding:
            # Tell the macro for that keycode that the key is released and
            # let it decide what to do with that information.
            active_macro.release_key()
            logger.spam('%s, releasing macro', key)

        if type_code in unreleased:
            target_type, target_code = unreleased[type_code][0]
            logger.spam('%s, releasing %s', key, target_code)
            del unreleased[type_code]
            write(uinput, (target_type, target_code, 0))
        else:
            logger.spam('%s, unexpected key up', key)

        # everything that can be released is released now
        return

    """Filtering duplicate key downs"""

    if is_key_down(event):
        # it would start a macro usually
        if key in macros and active_macro is not None and active_macro.running:
            # for key-down events and running macros, don't do anything.
            # This avoids spawning a second macro while the first one is not
            # finished, especially since gamepad-triggers report a ton of
            # events with a positive value.
            logger.spam('%s, macro already running', key)
            return

        # it would write a key usually
        if key in key_to_code and type_code in unreleased:
            # duplicate key-down. skip this event. Avoid writing millions of
            # key-down events when a continuous value is reported, for example
            # for gamepad triggers
            logger.spam('%s, duplicate key down', key)
            return

    """starting new macros or injecting new keys"""

    if is_key_down(event):
        if key in macros:
            macro = macros[key]
            active_macros[type_code] = macro
            macro.press_key()
            logger.spam('%s, maps to macro %s', key, macro.code)
            asyncio.ensure_future(macro.run())
            return

        if key in key_to_code:
            target_code = key_to_code[key]
            logger.spam('%s, maps to %s', key, target_code)
            unreleased[type_code] = ((EV_KEY, target_code), event_tuple)
            write(uinput, (EV_KEY, target_code, 1))
            return

        logger.spam('%s, forwarding', key)
        unreleased[type_code] = ((event_tuple[:2]), event_tuple)
        write(uinput, event_tuple)
        return

    logger.error('%s, unhandled. %s %s', key, unreleased, active_macros)
