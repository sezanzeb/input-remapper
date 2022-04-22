from gi.repository import Gtk, GtkSource, Gdk, GLib, GObject

from inputremapper.groups import (
    _Groups,
    GAMEPAD,
    KEYBOARD,
    UNKNOWN,
    GRAPHICS_TABLET,
    TOUCHPAD,
    MOUSE,
)
from inputremapper.gui.event_handler import EventHandler, EventEnum
from inputremapper.gui.utils import HandlerDisabled
from inputremapper.logger import logger


ICON_NAMES = {
    GAMEPAD: "input-gaming",
    MOUSE: "input-mouse",
    KEYBOARD: "input-keyboard",
    GRAPHICS_TABLET: "input-tablet",
    TOUCHPAD: "input-touchpad",
    UNKNOWN: None,
}

# sort types that most devices would fall in easily to the right.
ICON_PRIORITIES = [GRAPHICS_TABLET, TOUCHPAD, GAMEPAD, MOUSE, KEYBOARD, UNKNOWN]


class DeviceSelection:
    def __init__(self, event_handler: EventHandler, combobox: Gtk.ComboBox):
        self.event_handler = event_handler
        self.device_store = Gtk.ListStore(str, str, str)
        self.gui = combobox

        # https://python-gtk-3-tutorial.readthedocs.io/en/latest/treeview.html#the-view
        combobox.set_model(self.device_store)
        renderer_icon = Gtk.CellRendererPixbuf()
        renderer_text = Gtk.CellRendererText()
        renderer_text.set_padding(5, 0)
        combobox.pack_start(renderer_icon, False)
        combobox.pack_start(renderer_text, False)
        combobox.add_attribute(renderer_icon, "icon-name", 1)
        combobox.add_attribute(renderer_text, "text", 2)
        combobox.set_id_column(0)

        self.attach_to_events()
        combobox.connect("changed", self.on_select_device)

    def attach_to_events(self):
        self.event_handler.subscribe(EventEnum.groups_changed, self.on_groups_changed)
        self.event_handler.subscribe(EventEnum.group_changed, self.on_group_changed)

    def on_groups_changed(self, groups: _Groups):
        with HandlerDisabled(self.gui, self.on_select_device):
            self.device_store.clear()
            for group in groups.filter(include_inputremapper=False):
                types = group.types
                if len(types) > 0:
                    device_type = sorted(types, key=ICON_PRIORITIES.index)[0]
                    icon_name = ICON_NAMES[device_type]
                else:
                    icon_name = None

                logger.debug(f"adding {group.key} to device dropdown ")
                self.device_store.append([group.key, icon_name, group.key])

    def on_group_changed(self, group_key: str, **kwargs):
        with HandlerDisabled(self.gui, self.on_select_device):
            self.gui.set_active_id(group_key)

    def on_select_device(self, *_, **__):
        group_key = self.gui.get_active_id()
        logger.debug('Selecting device "%s"', group_key)
        self.event_handler.emit(EventEnum.load_group, group_key=group_key)
