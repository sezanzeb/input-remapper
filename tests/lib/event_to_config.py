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

"""Migration functions.

Only write changes to disk, if there actually are changes. Otherwise, file-modification
dates are destroyed.
"""

from inputremapper.configs.input_config import (
    InputConfig,
    DEFAULT_ABS_ANALOG_THRESHOLD_MAGNITUDE,
)


def event_to_config(event: InputEvent) -> InputConfig:
    """create an input confing from the given InputEvent."""
    sign = 1 if event.value > 0 else -1
    return InputConfig(
        type=event.type,
        code=event.code,
        origin_hash=event.origin_hash,
        analog_threshold=DEFAULT_ABS_ANALOG_THRESHOLD_MAGNITUDE * sign,
    )
