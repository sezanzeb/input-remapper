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

import os.path
import gettext
import locale
from inputremapper.configs.data import get_data_path
from argparse import ArgumentParser

APP_NAME = "input-remapper"
LOCALE_DIR = os.path.join(get_data_path(), "lang")

locale.bindtextdomain(APP_NAME, LOCALE_DIR)
locale.textdomain(APP_NAME)

translate = gettext.translation(APP_NAME, LOCALE_DIR, fallback=True)
_ = translate.gettext
