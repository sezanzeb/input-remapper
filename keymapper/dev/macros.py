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


"""Executes more complex patterns of keystrokes.

To keep it short on the UI, the available functions are one-letter long.

The global functions actually perform the stuff and always return macro
instances that can then be further chained.

the outermost macro (in the examples below the one created by 'r',
'r' and 'w') will be started, which triggers a chain reaction to execute
all of the configured stuff.

Examples
--------
r(3, k('a').w(10)): 'a' <10ms> 'a' <10ms> 'a'
r(2, k('a').k('-').k('b'): 'a' '-' 'a' '-' 'b'
w(1000).m('SHIFT_L', r(2, k('a'))).w(10).k('b'): <1s> 'A' 'A' <10ms> 'b'
"""


import time
import random


# TODO parse securely


def m(*args):
    return Macro().m(*args)


def r(*args):
    return Macro().r(*args)


def k(*args):
    return Macro().k(*args)


def w(*args):
    return Macro().w(*args)


class Macro:
    """Supports chaining and preparing actions."""
    def __init__(self):
        self.tasks = []

    def run(self):
        """Run the macro"""
        for task in self.tasks:
            task()

    def m(self, modifier, macro):
        """Do stuff while a modifier is activated.

        Parameters
        ----------
        modifier : str
        macro : Macro
        """
        # TODO press modifier down
        self.tasks.append(macro.run)
        # TODO release modifier
        return self

    def r(self, repeats, macro):
        """Repeat actions.

        Parameters
        ----------
        repeats : int
        macro : Macro
        """
        for _ in range(repeats):
            self.tasks.append(macro.run)
        return self

    def k(self, character, value=None):
        """Write the character.

        Parameters
        ----------
        """
        # TODO write character
        self.tasks.append(lambda: print(character))
        return self

    def w(self, min, max=None):
        """Wait a random time in milliseconds"""
        # TODO random
        self.tasks.append(lambda: time.sleep(min / 1000))
        return self


# TODO make these into tests

print()
r(3, k('a').w(200)).run()

print()
r(2, k('a').k('-')).k('b').run()

print()
w(400).m('SHIFT_L', r(2, k('a'))).w(10).k('b').run()

print()
