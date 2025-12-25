#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2025 sezanzeb <b8x45ygc9@mozmail.com>
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


def check_dependencies() -> None:
    print("Checking dependencies")
    try:
        import gi

        gi.require_version("Gdk", "3.0")
        gi.require_version("GLib", "2.0")
        gi.require_version("Gst", "1.0")
        gi.require_version("Gtk", "3.0")
        gi.require_version("GtkSource", "4")
        from gi.repository import GObject, Gtk, Gst, Gdk, GLib, Pango, Gio, GtkSource
        import evdev
        import psutil
        import dasbus
        import pygobject
        import pydantic

        print("All required Python modules found")
    except ImportError as e:
        print(f"\033[93mMissing Python module: {e}\033[0m")
    except Exception as e:
        print(f"\033[93mException while checking dependencies: {e}\033[0m")
