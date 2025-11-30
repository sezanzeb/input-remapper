# noqa: F401


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
        print(f"\033[93mMissing Python module: {e}\033[0m")
    except Exception as e:
        print(f"\033[93mException while checking dependencies: {e}\033[0m")
