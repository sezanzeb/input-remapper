#!/usr/bin/env python3

import sys


def check_dependencies() -> None:
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
        print(f"Missing Python module: {e}")
