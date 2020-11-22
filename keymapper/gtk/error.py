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


"""Error dialog."""


import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GLib', '2.0')
from gi.repository import Gtk

from keymapper.data import get_data_path
from keymapper.logger import logger


class ErrorDialog:
    """An Error that closes the application afterwards."""
    def __init__(self, primary, secondary):
        """
        Parameters
        ----------
        primary : string
        secondary : string
        """
        logger.error(secondary)
        gladefile = get_data_path('key-mapper.glade')
        builder = Gtk.Builder()
        builder.add_from_file(gladefile)
        error_dialog = builder.get_object('error_dialog')
        error_dialog.show()
        builder.get_object('primary_error_label').set_text(primary)
        builder.get_object('secondary_error_label').set_text(secondary)
        error_dialog.run()
        error_dialog.hide()
