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


"""Inject a keycode based on the mapping."""


import itertools
import asyncio
import time

import evdev
from evdev.ecodes import EV_KEY, EV_ABS

import inputremapper.exceptions

from inputremapper.logger import logger
from inputremapper.system_mapping import DISABLE_CODE
from inputremapper import utils
from inputremapper.injection.mapping_handlers.consumer import Consumer
from inputremapper.utils import RELEASE
from inputremapper.groups import classify, GAMEPAD
from inputremapper.injection.global_uinputs import global_uinputs


# this state is shared by all KeycodeMappers of this process

# maps mouse buttons to macro instances that have been executed.
# They may still be running or already be done. Just like unreleased,
# this is a mapping of (type, code). The value is not included in the
# key, because a key release event with a value of 0 needs to be able
# to find the running macro. The downside is that a d-pad cannot
# execute two macros at once, one for each direction.
# Only sequentially.
active_macros = {}


# mapping of future release event (type, code) to an Unreleased object,
# All key-up events have a value of 0, so it is not added to
# the tuple. This is needed in order to release the correct event
# mapped on a D-Pad. Each direction on one D-Pad axis reports the
# same type and code, but different values. There cannot be both at
# the same time, as pressing one side of a D-Pad forces the other
# side to go up. If both sides of a D-Pad are mapped to different
# event-codes, this data structure helps to figure out which of those
# two to release on an event of value 0. Same goes for the Wheel.
# The input event is remembered to make sure no duplicate down-events
# are written. Since wheels report a lot of "down" events that don't
# serve any purpose when mapped to a key, those duplicate down events
# should be removed. If the same type and code arrives but with a
# different value (direction), there must be a way to check if the
# event is actually a duplicate and not a different event.
unreleased = {}


COMBINATION_INCOMPLETE = 1  # not all keys of the combination are pressed
NOT_COMBINED = 2  # this key is not part of a combination


def subsets(combination):
    """Return a list of subsets of the combination.

    If combination is only one element long it returns an empty list,
    because it's not a combination and there is no reason to iterate.

    Includes the complete input as well.

    Parameters
    -----------
    combination : tuple
        tuple of 3-tuples, each being int, int, int (type, code, action)
    """
    combination = list(combination)
    lengths = list(range(2, len(combination) + 1))
    lengths.reverse()
    return list(
        itertools.chain.from_iterable(
            itertools.combinations(combination, length) for length in lengths
        )
    )


class Unreleased:
    """This represents a key that has been pressed but not released yet."""

    __slots__ = (
        "target",
        "input_event_tuple",
        "triggered_key",
    )

    def __init__(self, target, input_event_tuple, triggered_key):
        """
        Parameters
        ----------
        target : 3-tuple
            int type, int code of what was injected or forwarded
            and string target_uinput for injected events,
            None for forwarded events
        input_event_tuple : 3-tuple
            int, int, int / type, code, action
        triggered_key : tuple of 3-tuples
            What was used to index key_to_code or macros when stuff
            was triggered.
            If nothing was triggered and input_event_tuple forwarded,
            insert None.
        """
        self.target = target
        self.input_event_tuple = input_event_tuple
        self.triggered_key = triggered_key

        if not isinstance(input_event_tuple[0], int) or len(input_event_tuple) != 3:
            raise ValueError(
                "Expected input_event_tuple to be a 3-tuple of ints, but "
                f"got {input_event_tuple}"
            )

        unreleased[input_event_tuple[:2]] = self

    def is_mapped(self):
        """If true, the key-down event was written to context.uinput.

        That means the release event should also be injected into that one.
        If this returns false, just forward the release event instead.
        """
        # This should end up being equal to context.is_mapped(key)
        return self.triggered_key is not None

    def __str__(self):
        return (
            "Unreleased("
            f"target{self.target},"
            f"input{self.input_event_tuple},"
            f'key{self.triggered_key or "(None)"}'
            ")"
        )

    def __repr__(self):
        return self.__str__()


def find_by_event(key):
    """Find an unreleased entry by an event.

    If such an entry exists, it was created by an event that is exactly
    like the input parameter (except for the timestamp).

    That doesn't mean it triggered something, only that it was seen before.
    """
    unreleased_entry = unreleased.get(key[:2])
    if unreleased_entry and unreleased_entry.input_event_tuple == key:
        return unreleased_entry

    return None


def find_by_key(key):
    """Find an unreleased entry by a combination of keys.

    If such an entry exist, it was created when a combination of keys
    (which matches the parameter, can also be of len 1 = single key)
    ended up triggering something.

    Parameters
    ----------
    key : tuple of int
        type, code, action
    """
    unreleased_entry = unreleased.get(key[-1][:2])
    if unreleased_entry and unreleased_entry.triggered_key == key:
        return unreleased_entry

    return None


class KeycodeMapper(Consumer):
    """Injects keycodes and starts macros.

    This really is somewhat complicated because it needs to be able to handle
    combinations (which is actually not that trivial because the order of keys
    matters). The nature of some events (D-Pads and Wheels) adds to the
    complexity. Since macros are mapped the same way keys are, this class
    takes care of both.
    """

    def __init__(self, *args, **kwargs):
        """Create a keycode mapper for one virtual device.

        There may be multiple KeycodeMappers for one hardware device. They
        share some state (unreleased and active_macros) with each other.
        """
        super().__init__(*args, **kwargs)

        self._abs_range = None

        if self.context.maps_joystick():
            self._abs_range = utils.get_abs_range(self.source)

        self._gamepad = classify(self.source) == GAMEPAD

        self.debounces = {}

        # some type checking, prevents me from forgetting what that stuff
        # is supposed to be when writing tests.
        for key in self.context.key_to_code:
            for sub_key in key:
                if abs(sub_key[2]) > 1:
                    raise ValueError(
                        f"Expected values to be one of -1, 0 or 1, " f"but got {key}"
                    )

    def is_enabled(self):
        # even if the source does not provide a capability that is used here, it might
        # be important for notifying macros of new events that run on other sources.
        return len(self.context.key_to_code) > 0 or len(self.context.macros) > 0

    def is_handled(self, event):
        return utils.should_map_as_btn(event, self.context.preset, self._gamepad)

    async def run(self):
        """Provide a debouncer to inject wheel releases."""
        start = time.time()
        while True:
            # try to do this as close to 60hz as possible
            time_taken = time.time() - start
            await asyncio.sleep(max(0.0, (1 / 60) - time_taken))
            start = time.time()

            for debounce in self.debounces.values():
                if debounce[2] == -1:
                    # has already been triggered
                    continue
                if debounce[2] == 0:
                    debounce[0](*debounce[1])
                    debounce[2] = -1
                else:
                    debounce[2] -= 1

    def debounce(self, debounce_id, func, args, ticks):
        """Debounce a function call.

        Parameters
        ----------
        debounce_id : hashable
            If this function is called with the same debounce_id again,
            the previous debouncing is overwritten, and therefore restarted.
        func : function
        args : tuple
        ticks : int
            After ticks * 1 / 60 seconds the function will be executed,
            unless debounce is called again with the same debounce_id
        """
        self.debounces[debounce_id] = [func, args, ticks]

    async def notify(self, event):
        """Receive the newest event that should be mapped."""
        action = utils.classify_action(event, self._abs_range)

        for macro, _ in self.context.macros.values():
            macro.notify(event, action)

        will_report_key_up = utils.will_report_key_up(event)
        if not will_report_key_up:
            # simulate a key-up event if no down event arrives anymore.
            # this may release macros, combinations or keycodes.
            release = evdev.InputEvent(0, 0, event.type, event.code, 0)
            self.debounce(
                debounce_id=(event.type, event.code, action),
                func=self.handle_keycode,
                args=(release, RELEASE, False),
                ticks=3,
            )

        async def delayed_handle_keycode():
            # give macros a priority of working on their asyncio iterations
            # first before handle_keycode. This is important for if_single.
            # If if_single injects a modifier to modify the key that canceled
            # its sleep, it needs to inject it before handle_keycode injects
            # anything. This is important for the space cadet shift.
            # 1. key arrives
            # 2. stop if_single
            # 3. make if_single inject `then`
            # 4. inject key
            # But I can't just wait for if_single to do its thing because it might
            # be a macro that sleeps for a few seconds.
            # This appears to me to be incredibly race-conditiony. For that
            # reason wait a few more asyncio ticks before continuing.
            # But a single one also worked. I can't wait for the specific
            # macro task here because it might block forever. I'll just give
            # it a few asyncio iterations advance before continuing here.
            for _ in range(10):
                # Noticable delays caused by this start at 10000 iterations
                # Also see the python docs on asyncio.sleep. Sleeping for 0
                # seconds just iterates the loop once.
                await asyncio.sleep(0)

            self.handle_keycode(event, action)

        await delayed_handle_keycode()

    def macro_write(self, target_uinput):
        def f(ev_type, code, value):
            """Handler for macros."""
            logger.debug(
                f"Macro sending %s to %s", (ev_type, code, value), target_uinput
            )
            global_uinputs.write((ev_type, code, value), target_uinput)

        return f

    def _get_key(self, key):
        """If the event triggers stuff, get the key for that.

        This key can be used to index `key_to_code` and `macros` and it might
        be a combination of keys.

        Otherwise, for unmapped events, returns the input.

        The return format is always a tuple of 3-tuples, each 3-tuple being
        type, code, action (int, int, int)

        Parameters
        ----------
        key : tuple of int
            3-tuple of type, code, action
            Action should be one of -1, 0 or 1
        """
        unreleased_entry = find_by_event(key)

        # The key used to index the mappings `key_to_code` and `macros`.
        # If the key triggers a combination, the returned key will be that one
        # instead
        action = key[2]
        key = (key,)

        if unreleased_entry and unreleased_entry.triggered_key is not None:
            # seen before. If this key triggered a combination,
            # use the combination that was triggered by this as key.
            return unreleased_entry.triggered_key

        if utils.is_key_down(action):
            # get the key/combination that the key-down would trigger

            # the triggering key-down has to be the last element in
            # combination, all others can have any arbitrary order. By
            # checking all unreleased keys, a + b + c takes priority over
            # b + c, if both mappings exist.
            # WARNING! the combination-down triggers, but a single key-up
            # releases. Do not check if key in macros and such, if it is an
            # up event. It's going to be False.
            combination = tuple(
                value.input_event_tuple for value in unreleased.values()
            )
            if key[0] not in combination:  # might be a duplicate-down event
                combination += key

            # find any triggered combination. macros and key_to_code contain
            # every possible equivalent permutation of possible macros. The
            # last key in the combination needs to remain the newest key
            # though.
            for subset in subsets(combination):
                if subset[-1] != key[0]:
                    # only combinations that are completed and triggered by
                    # the newest input are of interest
                    continue

                if self.context.is_mapped(subset):
                    key = subset
                    break
            else:
                # no subset found, just use the key. all indices are tuples of
                # tuples, both for combinations and single keys.
                if len(combination) > 1:
                    logger.debug_key(combination, "unknown combination")

        return key

    def handle_keycode(self, event, action, forward=True):
        """Write mapped keycodes, forward unmapped ones and manage macros.

        As long as the provided event is mapped it will handle it, it won't
        check any type, code or capability anymore. Otherwise it forwards
        it as it is.

        Parameters
        ----------
        action : int
            One of PRESS, PRESS_NEGATIVE or RELEASE
            Just looking at the events value is not enough, because then mapping
            trigger-values that are between 1 and 255 is not possible. They might skip
            the 1 when pressed fast enough.
        event : evdev.InputEvent
        forward : bool
            if False, will not forward the event if it didn't trigger any
            mapping
        """
        assert isinstance(action, int)

        type_and_code = (event.type, event.code)
        active_macro = active_macros.get(type_and_code)
        original_tuple = (event.type, event.code, event.value)
        key = self._get_key((*type_and_code, action))
        is_mapped = self.context.is_mapped(key)

        """Releasing keys and macros"""

        if utils.is_key_up(action):
            if active_macro is not None and active_macro.is_holding():
                # Tell the macro for that keycode that the key is released and
                # let it decide what to do with that information.
                active_macro.release_trigger()
                logger.debug_key(key, "releasing macro")

            if type_and_code in unreleased:
                # figure out what this release event was for
                unreleased_entry = unreleased[type_and_code]
                target_type, target_code, target_uinput = unreleased_entry.target
                del unreleased[type_and_code]

                if target_code == DISABLE_CODE:
                    logger.debug_key(key, "releasing disabled key")
                    return

                if target_code is None:
                    logger.debug_key(key, "releasing key")
                    return

                if unreleased_entry.is_mapped():
                    # release what the input is mapped to
                    try:
                        logger.debug_key(
                            key, "releasing (%s, %s)", target_code, target_uinput
                        )
                        global_uinputs.write(
                            (target_type, target_code, 0), target_uinput
                        )
                        return
                    except inputremapper.exceptions.Error:
                        logger.debug_key(key, "could not map")
                        pass

                if forward:
                    # forward the release event
                    logger.debug_key((original_tuple,), "forwarding release")
                    self.forward(original_tuple)
                else:
                    logger.debug_key(key, "not forwarding release")

                return

            if event.type != EV_ABS:
                # ABS events might be spammed like crazy every time the
                # position slightly changes
                logger.debug_key(key, "unexpected key up")

            # everything that can be released is released now
            return

        """Filtering duplicate key downs"""

        if is_mapped and utils.is_key_down(action):
            # unmapped keys should not be filtered here, they should just
            # be forwarded to populate unreleased and then be written.

            if find_by_key(key) is not None:
                # this key/combination triggered stuff before.
                # duplicate key-down. skip this event. Avoid writing millions
                # of key-down events when a continuous value is reported, for
                # example for gamepad triggers or mouse-wheel-side buttons
                logger.debug_key(key, "duplicate key down")
                return

            # it would start a macro usually
            in_macros = key in self.context.macros
            running = active_macro and active_macro.running
            if in_macros and running:
                # for key-down events and running macros, don't do anything.
                # This avoids spawning a second macro while the first one is
                # not finished, especially since gamepad-triggers report a ton
                # of events with a positive value.
                logger.debug_key(key, "macro already running")
                self.context.macros[key].press_trigger()
                return

        """starting new macros or injecting new keys"""

        if utils.is_key_down(action):
            # also enter this for unmapped keys, as they might end up
            # triggering a combination, so they should be remembered in
            # unreleased

            if key in self.context.macros:
                macro, target_uinput = self.context.macros[key]
                active_macros[type_and_code] = macro
                Unreleased((None, None, None), (*type_and_code, action), key)
                macro.press_trigger()
                logger.debug_key(
                    key, "maps to macro (%s, %s)", macro.code, target_uinput
                )
                asyncio.ensure_future(macro.run(self.macro_write(target_uinput)))
                return

            if key in self.context.key_to_code:
                target_code, target_uinput = self.context.key_to_code[key]
                # remember the key that triggered this
                # (this combination or this single key)
                Unreleased(
                    (EV_KEY, target_code, target_uinput), (*type_and_code, action), key
                )

                if target_code == DISABLE_CODE:
                    logger.debug_key(key, "disabled")
                    return

                try:
                    logger.debug_key(
                        key, "maps to (%s, %s)", target_code, target_uinput
                    )
                    global_uinputs.write((EV_KEY, target_code, 1), target_uinput)
                    return
                except inputremapper.exceptions.Error:
                    logger.debug_key(key, "could not map")
                    pass

            if forward:
                logger.debug_key((original_tuple,), "forwarding")
                self.forward(original_tuple)
            else:
                logger.debug_key(((*type_and_code, action),), "not forwarding")

            # unhandled events may still be important for triggering
            # combinations later, so remember them as well.
            Unreleased((*type_and_code, None), (*type_and_code, action), None)
            return

        logger.error("%s unhandled", key)
