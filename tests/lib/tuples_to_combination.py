# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2026 sezanzeb <4t1pzast9@mozmail.com>
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

from inputremapper.configs.input_config import InputCombination


def tuples_to_combination(*tuples) -> InputCombination:
    """Construct an InputCombination from (type, code, analog_threshold) tuples."""
    # shorthand for tests.
    dicts = []
    for tuple_ in tuples:
        if len(tuple_) == 3:
            dicts.append(
                {
                    "type": tuple_[0],
                    "code": tuple_[1],
                    "analog_threshold": tuple_[2],
                }
            )
        elif len(tuple_) == 2:
            dicts.append(
                {
                    "type": tuple_[0],
                    "code": tuple_[1],
                }
            )
        else:
            raise TypeError

    return InputCombination(dicts)
