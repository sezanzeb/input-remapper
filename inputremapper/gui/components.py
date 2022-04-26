from typing import List, Tuple, Optional

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
        combobox.connect("changed", self.on_gtk_select_device)

    def attach_to_events(self):
        self.event_handler.subscribe(EventEnum.groups_changed, self.on_groups_changed)
        self.event_handler.subscribe(EventEnum.group_changed, self.on_group_changed)

    def on_groups_changed(self, groups: List[Tuple[str, Optional[str]]]):
        with HandlerDisabled(self.gui, self.on_gtk_select_device):
            self.device_store.clear()
            for group in groups:
                logger.debug(f"adding {group[0]} to device dropdown ")
                self.device_store.append([group[0], group[1], group[0]])

    def on_group_changed(self, group_key: str, **_):
        with HandlerDisabled(self.gui, self.on_gtk_select_device):
            self.gui.set_active_id(group_key)

    def on_gtk_select_device(self, *_, **__):
        group_key = self.gui.get_active_id()
        logger.debug('Selecting device "%s"', group_key)
        self.event_handler.emit(EventEnum.load_group, group_key=group_key)


class PresetSelection:
    def __init__(self, event_handler: EventHandler, combobox: Gtk.ComboBoxText):
        self.event_handler = event_handler
        self.gui = combobox

        self.attach_to_events()
        combobox.connect("changed", self.on_gtk_select_preset)

    def attach_to_events(self):
        self.event_handler.subscribe(EventEnum.group_changed, self.on_group_changed)
        self.event_handler.subscribe(EventEnum.preset_changed, self.on_preset_changed)

    def on_group_changed(self, group_key: str, presets: List[str]):
        with HandlerDisabled(self.gui, self.on_gtk_select_preset):
            self.gui.remove_all()
            for preset in presets:
                self.gui.append(preset, preset)

    def on_preset_changed(self, name, **_):
        with HandlerDisabled(self.gui, self.on_gtk_select_preset):
            self.gui.set_active_id(name)

    def on_gtk_select_preset(self, *_, **__):
        name = self.gui.get_active_id()
        logger.debug('Selecting preset "%s"', name)
        self.event_handler.emit(EventEnum.load_preset, name=name)
