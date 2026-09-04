# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings

"""Visual Xbox Gamepad mapping interface following input-remapper standards with PES layout and interactive SVG controller."""

from __future__ import annotations
import os
import subprocess
from typing import Dict, Optional, Tuple

from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango

from inputremapper.configs.data import get_data_path
from inputremapper.configs.mapping import Mapping
from inputremapper.configs.keyboard_layout import keyboard_layout
from inputremapper.gui.controller import Controller
from inputremapper.gui.messages.message_broker import MessageBroker, MessageType
from inputremapper.gui.components.common import Breadcrumbs
from inputremapper.gui.components.editor import AutoloadSwitch
from inputremapper.gui.messages.message_data import DoStackSwitch
from inputremapper.injection.injector import InjectorState
from inputremapper.logging.logger import logger
from inputremapper.utils import get_device_hash


KEY_NAMES: Dict[int, str] = {
    1: "ESC",
    2: "1", 3: "2", 4: "3", 5: "4", 6: "5", 7: "6", 8: "7", 9: "8", 10: "9", 11: "0",
    14: "BACKSPACE",
    15: "TAB",
    16: "Q", 17: "W", 18: "E", 19: "R", 20: "T", 21: "Y", 22: "U", 23: "I", 24: "O", 25: "P",
    28: "ENTER",
    29: "CTRL IZQ",
    30: "A", 31: "S", 32: "D", 33: "F", 34: "G", 35: "H", 36: "J", 37: "K", 38: "L",
    42: "SHIFT IZQ",
    44: "Z", 45: "X", 46: "C", 47: "V", 48: "B", 49: "N", 50: "M",
    54: "SHIFT DER",
    56: "ALT IZQ",
    57: "ESPACIO",
    58: "BLOQ MAYUS",
    59: "F1", 60: "F2", 61: "F3", 62: "F4", 63: "F5", 64: "F6",
    65: "F7", 66: "F8", 67: "F9", 68: "F10", 87: "F11", 88: "F12",
    97: "CTRL DER",
    100: "ALT GR",
    103: "🡹 ARRIBA",
    105: "🡸 IZQUIERDA",
    106: "🡺 DERECHA",
    108: "🡻 ABAJO",
    110: "INSERT",
    111: "SUPR",
}


def format_key_name(code: int) -> str:
    """Returns a user-friendly, clean uppercase key label."""
    if code in KEY_NAMES:
        return KEY_NAMES[code]
    name = keyboard_layout.get_name(code)
    if name:
        name = name.upper()
        if name.startswith("KEY_"):
            name = name[4:]
        return name
    return f"#{code}"


class XboxVisualMapper:
    """Standard-compliant Xbox Gamepad interface with PES columns and interactive touchable SVG controller."""

    SVG_W = 744.0
    SVG_H = 500.0
    DISP_W = 520
    DISP_H = 349

    def __init__(
        self,
        message_broker: MessageBroker,
        controller: Controller,
        parent_box: Gtk.Box,
        window: Gtk.Window,
        main_stack: Optional[Gtk.Stack] = None,
    ):
        self._message_broker = message_broker
        self._controller = controller
        self._parent_box = parent_box
        self._window = window
        self._main_stack = main_stack

        self._active_recording_target: Optional[str] = None
        self._key_listener_id: Optional[int] = None

        # Left column items: (id, name, badge_text, badge_class, symbol)
        self._left_controls = [
            ("lt", "Left Trigger (LT)", "LT", "pes-badge-trigger", "TRIGGER_LEFT"),
            ("lb", "Left Bumper (LB)", "LB", "pes-badge-bumper", "BTN_TL"),
            ("dpad_up", "D-Pad Up", "▲", "pes-badge-dpad", "DPAD_UP"),
            ("dpad_left", "D-Pad Left", "◄", "pes-badge-dpad", "DPAD_LEFT"),
            ("dpad_down", "D-Pad Down", "▼", "pes-badge-dpad", "DPAD_DOWN"),
            ("dpad_right", "D-Pad Right", "►", "pes-badge-dpad", "DPAD_RIGHT"),
            ("ls_up", "Left Stick Up", "L▲", "pes-badge-ls", "STICK_LEFT_UP"),
            ("ls_left", "Left Stick Left", "L◄", "pes-badge-ls", "STICK_LEFT_LEFT"),
            ("ls_down", "Left Stick Down", "L▼", "pes-badge-ls", "STICK_LEFT_DOWN"),
            ("ls_right", "Left Stick Right", "L►", "pes-badge-ls", "STICK_LEFT_RIGHT"),
            ("ls_click", "Left Stick Click (L3)", "L3", "pes-badge-ls", "BTN_THUMBL"),
            ("back", "View / Back Button", "⧉", "pes-badge-menu", "BTN_SELECT"),
        ]

        # Right column items: (id, name, badge_text, badge_class, symbol)
        self._right_controls = [
            ("rt", "Right Trigger (RT)", "RT", "pes-badge-trigger", "TRIGGER_RIGHT"),
            ("rb", "Right Bumper (RB)", "RB", "pes-badge-bumper", "BTN_TR"),
            ("btn_y", "Y Button", "Y", "pes-badge-y", "BTN_Y"),
            ("btn_x", "X Button", "X", "pes-badge-x", "BTN_X"),
            ("btn_a", "A Button", "A", "pes-badge-a", "BTN_A"),
            ("btn_b", "B Button", "B", "pes-badge-b", "BTN_B"),
            ("rs_up", "Right Stick Up", "R▲", "pes-badge-rs", "STICK_RIGHT_UP"),
            ("rs_left", "Right Stick Left", "R◄", "pes-badge-rs", "STICK_RIGHT_LEFT"),
            ("rs_down", "Right Stick Down", "R▼", "pes-badge-rs", "STICK_RIGHT_DOWN"),
            ("rs_right", "Right Stick Right", "R►", "pes-badge-rs", "STICK_RIGHT_RIGHT"),
            ("rs_click", "Right Stick Click (R3)", "R3", "pes-badge-rs", "BTN_THUMBR"),
            ("start", "Menu / Start Button", "≡", "pes-badge-menu", "BTN_START"),
        ]

        # Hotspots placed directly over the controller image:
        self._hotspot_defs = {
            "lt": ("TRIGGER_LEFT", 185, 68, 48, 48, True),
            "lb": ("BTN_TL", 172, 110, 56, 28, True),
            "rt": ("TRIGGER_RIGHT", 558, 68, 48, 48, True),
            "rb": ("BTN_TR", 572, 110, 56, 28, True),
            "guide": ("BTN_MODE", 372, 246, 44, 44, False),
            "back": ("BTN_SELECT", 296, 250, 36, 36, False),
            "start": ("BTN_START", 448, 250, 36, 36, False),
            "btn_y": ("BTN_Y", 580, 202, 38, 38, False),
            "btn_x": ("BTN_X", 522, 248, 38, 38, False),
            "btn_b": ("BTN_B", 632, 244, 38, 38, False),
            "btn_a": ("BTN_A", 573, 290, 38, 38, False),
            "ls_click": ("BTN_THUMBL", 163, 263, 38, 38, False),
            "ls_up": ("STICK_LEFT_UP", 163, 222, 30, 30, False),
            "ls_down": ("STICK_LEFT_DOWN", 163, 304, 30, 30, False),
            "ls_left": ("STICK_LEFT_LEFT", 122, 263, 30, 30, False),
            "ls_right": ("STICK_LEFT_RIGHT", 204, 263, 30, 30, False),
            "dpad_up": ("DPAD_UP", 266, 318, 32, 32, False),
            "dpad_down": ("DPAD_DOWN", 266, 392, 32, 32, False),
            "dpad_left": ("DPAD_LEFT", 228, 355, 32, 32, False),
            "dpad_right": ("DPAD_RIGHT", 304, 355, 32, 32, False),
            "rs_click": ("BTN_THUMBR", 467, 360, 38, 38, False),
            "rs_up": ("STICK_RIGHT_UP", 467, 319, 30, 30, False),
            "rs_down": ("STICK_RIGHT_DOWN", 467, 401, 30, 30, False),
            "rs_left": ("STICK_RIGHT_LEFT", 426, 360, 30, 30, False),
            "rs_right": ("STICK_RIGHT_RIGHT", 508, 360, 30, 30, False),
        }

        self._entry_buttons: Dict[str, Gtk.Button] = {}
        self._hotspot_buttons: Dict[str, Gtk.Button] = {}

        self._build_ui()

        self._message_broker.subscribe(MessageType.preset, self._on_preset_changed)
        self._message_broker.subscribe(MessageType.groups, self._on_groups_changed)
        self._message_broker.subscribe(MessageType.injector_state, self._on_injector_state)

    def _get_image_path(self) -> str:
        """Finds the SVG controller image."""
        path = get_data_path("xbox_controller.svg")
        if os.path.exists(path):
            return path
        local_path = os.path.abspath("data/xbox_controller.svg")
        if os.path.exists(local_path):
            return local_path
        ws_path = "/home/vic/PROYECTOS/keyboard_as_xbox/input-remapper/data/xbox_controller.svg"
        if os.path.exists(ws_path):
            return ws_path
        return ""

    def _build_ui(self):
        """Constructs the standard-compliant PES configuration view."""
        self._parent_box.get_style_context().add_class("pes-container")

        # Top Section: Standard Header matching the Editor page (Breadcrumbs + Grid)
        top_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        top_box.set_halign(Gtk.Align.CENTER)

        # 1. Breadcrumbs (Preset Name Header)
        self._breadcrumbs_label = Gtk.Label()
        self._breadcrumbs_label.set_margin_top(14)
        self._breadcrumbs_label.set_margin_bottom(14)
        attrs = Pango.AttrList()
        attrs.insert(Pango.attr_weight_new(Pango.Weight.BOLD))
        self._breadcrumbs_label.set_attributes(attrs)
        Breadcrumbs(
            self._message_broker,
            self._breadcrumbs_label,
            show_device_group=True,
            show_preset=True,
        )
        top_box.pack_start(self._breadcrumbs_label, False, False, 0)

        # 2. Standard Grid matching original Editor tab
        grid = Gtk.Grid()
        grid.set_halign(Gtk.Align.CENTER)
        grid.set_row_spacing(6)
        grid.set_column_spacing(12)
        grid.set_margin_bottom(10)

        # Row 0: Action Buttons Box (homogeneous, spacing=6, width-request=463)
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_box.set_size_request(463, -1)
        btn_box.set_homogeneous(True)

        # Apply button
        self._btn_apply = Gtk.Button(label="Apply")
        img_apply = Gtk.Image.new_from_icon_name("media-playback-start", Gtk.IconSize.BUTTON)
        self._btn_apply.set_image(img_apply)
        self._btn_apply.set_always_show_image(True)
        self._btn_apply.set_tooltip_text("Start injecting")
        self._btn_apply.connect("clicked", lambda _: self._controller.start_injecting())
        btn_box.pack_start(self._btn_apply, True, True, 0)

        # Stop button
        self._btn_stop = Gtk.Button(label="Stop")
        img_stop = Gtk.Image.new_from_icon_name("media-playback-stop", Gtk.IconSize.BUTTON)
        self._btn_stop.set_image(img_stop)
        self._btn_stop.set_always_show_image(True)
        self._btn_stop.set_sensitive(False)
        self._btn_stop.set_tooltip_text("Stop injecting")
        self._btn_stop.connect("clicked", lambda _: self._controller.stop_injecting())
        btn_box.pack_start(self._btn_stop, True, True, 0)

        # Copy button
        btn_copy = Gtk.Button(label="Copy")
        img_copy = Gtk.Image.new_from_icon_name("edit-copy", Gtk.IconSize.BUTTON)
        btn_copy.set_image(img_copy)
        btn_copy.set_always_show_image(True)
        btn_copy.set_tooltip_text("Duplicate this preset")
        btn_copy.connect("clicked", lambda _: self._controller.copy_preset())
        btn_box.pack_start(btn_copy, True, True, 0)

        # Delete button
        btn_delete = Gtk.Button(label="Delete")
        img_delete = Gtk.Image.new_from_icon_name("edit-delete", Gtk.IconSize.BUTTON)
        btn_delete.set_image(img_delete)
        btn_delete.set_always_show_image(True)
        btn_delete.set_tooltip_text("Delete this preset")
        btn_delete.connect("clicked", lambda _: self._controller.delete_preset())
        btn_box.pack_start(btn_delete, True, True, 0)

        # Test button (jstest-gtk)
        btn_test = Gtk.Button(label="Test")
        btn_test.set_tooltip_text("Open gamepad tester (jstest-gtk)")
        btn_test.connect("clicked", lambda _: subprocess.Popen(["jstest-gtk"]))
        btn_box.pack_start(btn_test, True, True, 0)

        grid.attach(btn_box, 1, 0, 1, 1)

        # Row 1: Rename (Col 0: Label, Col 1: Entry + Save Button)
        rename_label = Gtk.Label(label="Rename")
        rename_label.set_size_request(100, -1)
        rename_label.set_width_chars(13)
        rename_label.set_opacity(0.5)
        rename_label.set_xalign(1.0)
        grid.attach(rename_label, 0, 1, 1, 1)

        rename_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._rename_input = Gtk.Entry()
        self._rename_input.set_tooltip_text("Type a new name for this preset")
        self._rename_input.connect("activate", lambda _: self._on_rename_clicked())
        rename_box.pack_start(self._rename_input, True, True, 0)

        btn_rename = Gtk.Button()
        img_save = Gtk.Image.new_from_icon_name("document-save", Gtk.IconSize.BUTTON)
        btn_rename.set_image(img_save)
        btn_rename.set_always_show_image(True)
        btn_rename.set_tooltip_text("Save the entered name")
        btn_rename.connect("clicked", lambda _: self._on_rename_clicked())
        rename_box.pack_start(btn_rename, False, False, 0)

        grid.attach(rename_box, 1, 1, 1, 1)

        # Row 2: Autoload (Col 0: Label, Col 1: Switch + status indicator)
        autoload_label = Gtk.Label(label="Autoload")
        autoload_label.set_size_request(100, -1)
        autoload_label.set_width_chars(13)
        autoload_label.set_opacity(0.5)
        autoload_label.set_xalign(1.0)
        autoload_label.set_margin_top(6)
        autoload_label.set_margin_bottom(7)
        grid.attach(autoload_label, 0, 2, 1, 1)

        autoload_content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self._autoload_switch = Gtk.Switch()
        self._autoload_switch.set_halign(Gtk.Align.START)
        self._autoload_switch.set_valign(Gtk.Align.CENTER)
        self._autoload_switch.set_tooltip_text("Activate this to load the preset next time the device connects or when logging in")
        AutoloadSwitch(self._message_broker, self._controller, self._autoload_switch)
        autoload_content_box.pack_start(self._autoload_switch, False, False, 0)

        self._status_label = Gtk.Label(label="⚪ Inactive")
        self._status_label.set_valign(Gtk.Align.CENTER)
        autoload_content_box.pack_start(self._status_label, False, False, 0)

        grid.attach(autoload_content_box, 1, 2, 1, 1)

        # Row 3: Block unmapped keys (Col 0: Label, Col 1: Switch + status indicator)
        block_label = Gtk.Label(label="Unmapped")
        block_label.set_size_request(100, -1)
        block_label.set_width_chars(13)
        block_label.set_opacity(0.5)
        block_label.set_xalign(1.0)
        block_label.set_margin_top(4)
        block_label.set_margin_bottom(4)
        grid.attach(block_label, 0, 3, 1, 1)

        block_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        self._block_switch = Gtk.Switch()
        self._block_switch.set_halign(Gtk.Align.START)
        self._block_switch.set_valign(Gtk.Align.CENTER)
        self._block_switch.set_tooltip_text(
            "Deactivate all keyboard keys not mapped to the gamepad"
        )
        self._block_switch.connect("notify::active", self._on_block_switch_toggled)
        block_box.pack_start(self._block_switch, False, False, 0)

        self._block_status_label = Gtk.Label(label="🟢 Deactivated")
        self._block_status_label.set_valign(Gtk.Align.CENTER)
        block_box.pack_start(self._block_status_label, False, False, 0)

        grid.attach(block_box, 1, 3, 1, 1)

        # Row 4: Mode Switcher (Col 0: Label, Col 1: Linked Buttons)
        mode_label = Gtk.Label(label="View")
        mode_label.set_size_request(100, -1)
        mode_label.set_width_chars(13)
        mode_label.set_opacity(0.5)
        mode_label.set_xalign(1.0)
        grid.attach(mode_label, 0, 4, 1, 1)

        mode_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        mode_box.get_style_context().add_class("linked")
        mode_box.set_halign(Gtk.Align.START)

        btn_mode_editor = Gtk.Button(label="Editor")
        btn_mode_editor.set_tooltip_text("Switch to classic table editor")
        btn_mode_editor.connect("clicked", lambda _: self._switch_to_editor())
        mode_box.pack_start(btn_mode_editor, False, False, 0)

        btn_mode_xbox = Gtk.Button(label="Xbox Gamepad")
        btn_mode_xbox.get_style_context().add_class("suggested-action")
        btn_mode_xbox.set_tooltip_text("Currently viewing Xbox Gamepad mapper")
        mode_box.pack_start(btn_mode_xbox, False, False, 0)

        grid.attach(mode_box, 1, 4, 1, 1)

        top_box.pack_start(grid, False, False, 0)

        # Subtitle / instructions
        self._subtitle = Gtk.Label()
        self._subtitle.set_markup(
            "<small><i>Click on any controller button or box to assign a key. Right-click to clear.</i></small>"
        )
        self._subtitle.set_margin_top(2)
        top_box.pack_start(self._subtitle, False, False, 0)

        self._parent_box.pack_start(top_box, False, False, 0)

        # Separator line
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(6)
        sep.set_margin_bottom(6)
        self._parent_box.pack_start(sep, False, False, 0)

        # PES Main Three-Column Layout
        main_grid = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        main_grid.set_halign(Gtk.Align.CENTER)

        # 1. Left Column
        left_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        left_col.get_style_context().add_class("pes-column")
        for ctrl_id, name, badge_txt, badge_cls, symbol in self._left_controls:
            row = self._create_pes_row(name, badge_txt, badge_cls, symbol)
            left_col.pack_start(row, False, False, 0)
        main_grid.pack_start(left_col, False, False, 0)

        # 2. Center Column: Touchable Controller Overlay + "Opciones predeterminadas"
        center_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        center_col.set_halign(Gtk.Align.CENTER)

        overlay = Gtk.Overlay()
        overlay.set_size_request(self.DISP_W, self.DISP_H)

        img_path = self._get_image_path()
        if img_path:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                img_path, self.DISP_W, self.DISP_H, True
            )
            bg_image = Gtk.Image.new_from_pixbuf(pixbuf)
        else:
            bg_image = Gtk.Image()

        overlay.add(bg_image)

        # Fixed layout for touchable hotspots on top of the controller
        fixed = Gtk.Fixed()
        scale_x = float(self.DISP_W) / self.SVG_W
        scale_y = float(self.DISP_H) / self.SVG_H

        for ctrl_id, (symbol, cx, cy, w, h, is_rect) in self._hotspot_defs.items():
            hotspot = Gtk.Button()
            hotspot.get_style_context().add_class("xbox-touch-hotspot")
            if is_rect:
                hotspot.get_style_context().add_class("xbox-touch-hotspot-rect")
            hotspot.set_can_focus(False)

            btn_w = int(w * scale_x)
            btn_h = int(h * scale_y)
            btn_x = int(cx * scale_x - btn_w / 2.0)
            btn_y = int(cy * scale_y - btn_h / 2.0)

            hotspot.set_size_request(btn_w, btn_h)
            hotspot.set_tooltip_text(f"Click to assign: {symbol}")
            hotspot.connect("clicked", lambda _, s=symbol: self._start_recording(s))

            self._hotspot_buttons[symbol] = hotspot
            fixed.put(hotspot, btn_x, btn_y)

        overlay.add_overlay(fixed)
        overlay.show_all()
        center_col.pack_start(overlay, False, False, 0)

        # Default Options Button
        btn_defaults = Gtk.Button(label="Default Options")
        btn_defaults.get_style_context().add_class("pes-default-btn")
        btn_defaults.set_size_request(self.DISP_W, 36)
        btn_defaults.set_tooltip_text("Reset controls to recommended gaming defaults (WASD, Space, etc.)")
        btn_defaults.connect("clicked", self._on_default_options_clicked)
        center_col.pack_start(btn_defaults, False, False, 0)

        main_grid.pack_start(center_col, False, False, 0)

        # 3. Right Column
        right_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        right_col.get_style_context().add_class("pes-column")
        for ctrl_id, name, badge_txt, badge_cls, symbol in self._right_controls:
            row = self._create_pes_row(name, badge_txt, badge_cls, symbol)
            right_col.pack_start(row, False, False, 0)
        main_grid.pack_start(right_col, False, False, 0)

        self._parent_box.pack_start(main_grid, True, True, 0)
        self._parent_box.show_all()

        GLib.idle_add(self._refresh_labels_from_preset)

    def _on_rename_clicked(self):
        """Renames the active preset."""
        new_name = self._rename_input.get_text().strip()
        if new_name:
            self._controller.rename_preset(new_name)
            self._rename_input.set_text("")

    def _switch_to_editor(self):
        """Switches main stack view to classic editor."""
        if self._main_stack:
            self._main_stack.set_visible_child_name("Editor")
        else:
            self._message_broker.publish(DoStackSwitch(2))

    def _create_pes_row(
        self, name: str, badge_text: str, badge_class: str, symbol: str
    ) -> Gtk.Box:
        """Creates a PES row containing a circular badge button and a compact entry button."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.get_style_context().add_class("pes-row")

        # Circular Badge Button (interactive on click)
        event_box = Gtk.EventBox()
        event_box.set_visible_window(False)
        badge = Gtk.Label()
        badge.set_xalign(0.5)
        badge.set_yalign(0.5)
        badge.get_style_context().add_class("pes-badge")
        badge.get_style_context().add_class(badge_class)
        badge.set_markup(f"<b>{badge_text}</b>")
        event_box.add(badge)
        event_box.set_tooltip_text(f"{name}\nClick to assign key")
        event_box.connect("button-press-event", lambda _, ev, s=symbol: self._on_entry_btn_press(ev, s))
        row.pack_start(event_box, False, False, 0)

        # Compact Entry Button (Key display)
        entry_btn = Gtk.Button(label="...")
        entry_btn.get_style_context().add_class("pes-entry-btn")
        entry_btn.set_can_focus(False)
        entry_btn.set_size_request(88, 22)
        entry_btn.set_tooltip_text(f"{name}\nClick to change. Right-click to clear.")
        entry_btn.connect("button-press-event", lambda _, ev, s=symbol: self._on_entry_btn_press(ev, s))

        self._entry_buttons[symbol] = entry_btn
        row.pack_start(entry_btn, False, False, 0)

        return row

    def _on_entry_btn_press(self, event: Gdk.EventButton, symbol: str) -> bool:
        if event.button == 1:
            self._start_recording(symbol)
            return True
        elif event.button == 3:
            self._clear_mapping(symbol)
            return True
        return False

    def _start_recording(self, symbol: str):
        """Activates listening mode on both the list entry and controller hotspot."""
        if self._active_recording_target is not None:
            self._cancel_recording()

        self._active_recording_target = symbol

        btn = self._entry_buttons.get(symbol)
        if btn:
            btn.get_style_context().add_class("pes-entry-recording")
            btn.set_label("▶ Press key...")

        hotspot = self._hotspot_buttons.get(symbol)
        if hotspot:
            hotspot.get_style_context().add_class("xbox-touch-hotspot-recording")

        self._subtitle.set_markup(
            f"<span color='#ff3366'><b>▶ Press a key on your keyboard to assign '{symbol}' (or Escape to cancel)...</b></span>"
        )

        self._key_listener_id = self._window.connect("key-press-event", self._on_window_key_press)

    def _cancel_recording(self):
        """Cancels listening mode."""
        if self._key_listener_id is not None:
            self._window.disconnect(self._key_listener_id)
            self._key_listener_id = None

        if self._active_recording_target is not None:
            btn = self._entry_buttons.get(self._active_recording_target)
            if btn:
                btn.get_style_context().remove_class("pes-entry-recording")

            hotspot = self._hotspot_buttons.get(self._active_recording_target)
            if hotspot:
                hotspot.get_style_context().remove_class("xbox-touch-hotspot-recording")

            self._active_recording_target = None
            self._subtitle.set_markup(
                "<small><i>Click on any controller button or box to assign a key. Right-click to clear.</i></small>"
            )
            self._refresh_labels_from_preset()

    def _on_window_key_press(self, _, event: Gdk.EventKey) -> bool:
        """Captures pressed key and assigns it."""
        if self._active_recording_target is None:
            return False

        if event.keyval == Gdk.KEY_Escape:
            self._cancel_recording()
            return True

        evdev_code = event.hardware_keycode - 8
        if evdev_code <= 0:
            return False

        target_symbol = self._active_recording_target
        self._assign_key(target_symbol, evdev_code)
        self._cancel_recording()
        return True

    def _get_origin_hash(self) -> Optional[str]:
        """Safely gets device origin hash from existing mappings or active group."""
        dm = self._controller.data_manager
        preset = dm.active_preset
        if preset:
            for m in preset:
                if m.input_combination:
                    for cfg in m.input_combination:
                        orig = getattr(cfg, "origin_hash", None)
                        if orig:
                            return orig

        active_group = dm.active_group
        if active_group:
            try:
                devices = active_group.get_devices()
                if devices:
                    return get_device_hash(devices[0])
            except Exception as e:
                logger.warning("Could not compute device hash: %s", e)

        return None

    def _clear_mapping(self, symbol: str):
        """Clears the mapping for the given symbol."""
        dm = self._controller.data_manager
        preset = dm.active_preset
        if preset is None:
            return
        to_remove = [
            m.input_combination
            for m in preset
            if getattr(m, "output_symbol", None) == symbol and m.input_combination
        ]
        for comb in to_remove:
            preset.remove(comb)
        preset.save()
        dm.publish_preset()
        self._refresh_labels_from_preset()

    def _assign_key(self, target_symbol: str, key_code: int):
        """Saves the key mapping to the active preset."""
        dm = self._controller.data_manager
        preset = dm.active_preset
        if preset is None:
            logger.error("No active preset selected")
            return

        origin_hash = self._get_origin_hash()

        # Remove existing mapping for this symbol
        to_remove = [
            m.input_combination
            for m in preset
            if getattr(m, "output_symbol", None) == target_symbol and m.input_combination
        ]
        for comb in to_remove:
            preset.remove(comb)

        # Remove any existing mapping using the same key code to avoid conflicts
        for m in list(preset):
            if m.input_combination and len(m.input_combination) == 1:
                cfg = list(m.input_combination)[0]
                if cfg.code == key_code:
                    preset.remove(m.input_combination)

        comb_cfg = {"type": 1, "code": key_code}
        if origin_hash:
            comb_cfg["origin_hash"] = origin_hash

        mapping_cls = getattr(preset, "_mapping_factory", Mapping)
        new_mapping = mapping_cls(
            input_combination=[comb_cfg],
            target_uinput="gamepad",
            output_symbol=target_symbol,
        )
        preset.add(new_mapping)
        preset.save()
        dm.publish_preset()
        self._refresh_labels_from_preset()

    def _on_default_options_clicked(self, _):
        """Restores standard gaming default mappings."""
        dm = self._controller.data_manager
        preset = dm.active_preset
        if preset is None:
            logger.error("No active preset for defaults")
            return

        origin_hash = self._get_origin_hash()

        defaults = {
            # Left Stick (Movement WASD)
            "STICK_LEFT_UP": 17,       # W
            "STICK_LEFT_LEFT": 30,     # A
            "STICK_LEFT_DOWN": 31,     # S
            "STICK_LEFT_RIGHT": 32,    # D
            "BTN_THUMBL": 42,          # Left Shift

            # D-Pad (Arrows)
            "DPAD_UP": 103,            # Up
            "DPAD_LEFT": 105,          # Left
            "DPAD_DOWN": 108,          # Down
            "DPAD_RIGHT": 106,         # Right

            # Face Buttons (Space, C, X, Z)
            "BTN_A": 57,               # Space
            "BTN_B": 46,               # C
            "BTN_X": 45,               # X
            "BTN_Y": 44,               # Z

            # Shoulders & Triggers
            "BTN_TL": 16,              # Q (LB)
            "BTN_TR": 18,              # E (RB)
            "TRIGGER_LEFT": 2,         # 1 (LT)
            "TRIGGER_RIGHT": 3,        # 2 (RT)

            # Right Stick (I, J, K, L, R)
            "STICK_RIGHT_UP": 23,      # I
            "STICK_RIGHT_LEFT": 36,    # J
            "STICK_RIGHT_DOWN": 37,    # K
            "STICK_RIGHT_RIGHT": 38,   # L
            "BTN_THUMBR": 19,          # R

            # Menu & Guide
            "BTN_SELECT": 15,          # Tab (Back)
            "BTN_START": 28,           # Enter (Start)
            "BTN_MODE": 59,            # F1 (Guide)
        }

        preset.empty()
        mapping_cls = getattr(preset, "_mapping_factory", Mapping)
        for symbol, code in defaults.items():
            comb_cfg = {"type": 1, "code": code}
            if origin_hash:
                comb_cfg["origin_hash"] = origin_hash

            mapping = mapping_cls(
                input_combination=[comb_cfg],
                target_uinput="gamepad",
                output_symbol=symbol,
            )
            preset.add(mapping)

        preset.save()
        dm.publish_preset()
        self._refresh_labels_from_preset()

    def _refresh_labels_from_preset(self):
        """Displays currently mapped keys in the PES entry boxes and tooltips."""
        preset = self._controller.data_manager.active_preset
        if not preset:
            for btn in self._entry_buttons.values():
                btn.set_label("...")
                btn.get_style_context().remove_class("pes-entry-mapped")
            return

        mapped_symbols = {}
        for m in preset:
            sym = getattr(m, "output_symbol", None)
            if sym and m.input_combination and len(m.input_combination) == 1:
                cfg = list(m.input_combination)[0]
                mapped_symbols[sym] = (cfg.code, format_key_name(cfg.code))

        for sym, btn in self._entry_buttons.items():
            if sym in mapped_symbols:
                code, key_name = mapped_symbols[sym]
                btn.set_label(key_name)
                btn.get_style_context().add_class("pes-entry-mapped")
            else:
                btn.set_label("...")
                btn.get_style_context().remove_class("pes-entry-mapped")

        # Update hotspot tooltips
        for sym, hotspot in self._hotspot_buttons.items():
            if sym in mapped_symbols:
                code, key_name = mapped_symbols[sym]
                hotspot.set_tooltip_text(f"{sym}\nMapped to: [{key_name}]\nClick to change")
            else:
                hotspot.set_tooltip_text(f"{sym}\nUnassigned\nClick to assign key")

        # Update block unmapped keys switch
        is_blocked = getattr(preset, "block_unmapped_keys", True)
        self._block_switch.handler_block_by_func(self._on_block_switch_toggled)
        self._block_switch.set_active(is_blocked)
        self._block_switch.handler_unblock_by_func(self._on_block_switch_toggled)
        self._update_block_status_label(is_blocked)

    def _on_block_switch_toggled(self, switch, _gparam):
        preset = self._controller.data_manager.active_preset
        if not preset:
            return
        is_blocked = switch.get_active()
        preset.block_unmapped_keys = is_blocked
        preset.save()
        self._update_block_status_label(is_blocked)

    def _update_block_status_label(self, is_blocked: bool):
        if is_blocked:
            self._block_status_label.set_markup(
                "<span color='#107c10'><b>🟢 Deactivated</b></span>"
            )
        else:
            self._block_status_label.set_markup(
                "<span color='#888888'>⚪ Allowed</span>"
            )

    def _on_preset_changed(self, _):
        GLib.idle_add(self._refresh_labels_from_preset)

    def _on_groups_changed(self, _):
        GLib.idle_add(self._refresh_labels_from_preset)

    def _on_injector_state(self, msg):
        """Updates live status and button text."""
        is_running = msg.state in (InjectorState.RUNNING, "RUNNING")
        if is_running:
            self._status_label.set_markup("<span color='#107c10'><b>🟢 Active</b></span>")
            self._btn_apply.set_sensitive(False)
            self._btn_stop.set_sensitive(True)
        else:
            self._status_label.set_markup("⚪ Inactive")
            self._btn_apply.set_sensitive(True)
            self._btn_stop.set_sensitive(False)
