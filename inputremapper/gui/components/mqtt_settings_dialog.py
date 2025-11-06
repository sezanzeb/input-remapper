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

"""MQTT and Home Assistant settings dialog."""

from __future__ import annotations

import os
import re
from typing import Optional

from gi.repository import Gtk

from inputremapper.logging.logger import logger
from inputremapper.mqtt_client import (
    MQTTConfig,
    get_mqtt_client,
    get_mqtt_config,
    initialize_mqtt_client,
)


class MQTTSettingsDialog:
    """Dialog for editing MQTT and Home Assistant settings."""

    def __init__(self, parent_window: Gtk.Window):
        """Initialize the settings dialog.

        Args:
            parent_window: Parent window for the dialog
        """
        self.parent_window = parent_window
        self.dialog = None
        self.fields = {}
        self.status_label = None

    def show(self):
        """Show the settings dialog."""
        self.dialog = Gtk.Dialog(
            title="MQTT & Home Assistant Settings",
            transient_for=self.parent_window,
            modal=True,
        )
        self.dialog.set_default_size(600, 500)

        # Add buttons
        self.dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        self.dialog.add_button("Test MQTT", Gtk.ResponseType.APPLY)
        self.dialog.add_button("Save", Gtk.ResponseType.OK)

        # Get content area
        content = self.dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_start(18)
        content.set_margin_end(18)
        content.set_margin_top(18)
        content.set_margin_bottom(18)

        # Load current config
        config = get_mqtt_config()
        if not config:
            config = MQTTConfig()  # Use defaults

        # Create form
        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(12)
        content.pack_start(grid, True, True, 0)

        row = 0

        # MQTT Broker Settings
        label = Gtk.Label()
        label.set_markup("<b>MQTT Broker Settings</b>")
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 2, 1)
        row += 1

        # Broker
        self._add_field(grid, row, "Broker:", "broker", config.broker, "MQTT broker IP or hostname")
        row += 1

        # Port
        self._add_field(grid, row, "Port:", "port", str(config.port), "MQTT broker port (usually 1883)")
        row += 1

        # Username
        self._add_field(grid, row, "Username:", "username", config.username, "MQTT username")
        row += 1

        # Password
        self._add_field(grid, row, "Password:", "password", config.password, "MQTT password", is_password=True)
        row += 1

        # Topic
        self._add_field(grid, row, "Topic:", "topic", config.topic, "MQTT topic for events")
        row += 1

        # QoS
        qos_label = Gtk.Label(label="QoS:")
        qos_label.set_halign(Gtk.Align.END)
        grid.attach(qos_label, 0, row, 1, 1)

        qos_spin = Gtk.SpinButton()
        qos_spin.set_range(0, 2)
        qos_spin.set_increments(1, 1)
        qos_spin.set_value(config.qos)
        qos_spin.set_tooltip_text("Quality of Service (0, 1, or 2)")
        grid.attach(qos_spin, 1, row, 1, 1)
        self.fields["qos"] = qos_spin
        row += 1

        # Retain
        retain_label = Gtk.Label(label="Retain:")
        retain_label.set_halign(Gtk.Align.END)
        grid.attach(retain_label, 0, row, 1, 1)

        retain_check = Gtk.CheckButton()
        retain_check.set_active(config.retain)
        retain_check.set_tooltip_text("Retain MQTT messages on broker")
        grid.attach(retain_check, 1, row, 1, 1)
        self.fields["retain"] = retain_check
        row += 1

        # Spacing
        row += 1

        # Device Settings
        label = Gtk.Label()
        label.set_markup("<b>Device Settings</b>")
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 2, 1)
        row += 1

        # Default Device Name
        self._add_field(
            grid,
            row,
            "Default Device Name:",
            "default_device_name",
            config.default_device_name or "",
            "Override auto-detected device names (optional)"
        )
        row += 1

        # Spacing
        row += 1

        # Home Assistant Settings
        label = Gtk.Label()
        label.set_markup("<b>Home Assistant Integration</b>")
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, row, 2, 1)
        row += 1

        # HA URL
        self._add_field(
            grid,
            row,
            "Home Assistant URL:",
            "ha_url",
            config.ha_url or "",
            "Home Assistant URL (e.g., http://192.168.1.160:8123)"
        )
        row += 1

        # Status label
        self.status_label = Gtk.Label()
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.set_line_wrap(True)
        content.pack_start(self.status_label, False, False, 0)

        self.dialog.show_all()

        # Connect response handler
        self.dialog.connect("response", self._on_response)

        self.dialog.run()

    def _add_field(
        self,
        grid: Gtk.Grid,
        row: int,
        label_text: str,
        field_name: str,
        value: str,
        tooltip: str,
        is_password: bool = False
    ):
        """Add a labeled text field to the grid."""
        label = Gtk.Label(label=label_text)
        label.set_halign(Gtk.Align.END)
        grid.attach(label, 0, row, 1, 1)

        entry = Gtk.Entry()
        entry.set_text(value)
        entry.set_tooltip_text(tooltip)
        entry.set_hexpand(True)
        if is_password:
            entry.set_visibility(False)
            entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        grid.attach(entry, 1, row, 1, 1)

        self.fields[field_name] = entry

    def _validate_config(self) -> tuple[bool, Optional[str]]:
        """Validate the configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get values
        broker = self.fields["broker"].get_text().strip()
        port_text = self.fields["port"].get_text().strip()
        username = self.fields["username"].get_text().strip()
        password = self.fields["password"].get_text().strip()
        topic = self.fields["topic"].get_text().strip()
        ha_url = self.fields["ha_url"].get_text().strip()

        # Validate required fields
        if not broker:
            return False, "Broker is required"

        if not port_text:
            return False, "Port is required"

        try:
            port = int(port_text)
            if port < 1 or port > 65535:
                return False, "Port must be between 1 and 65535"
        except ValueError:
            return False, "Port must be a number"

        if not username:
            return False, "Username is required"

        if not password:
            return False, "Password is required"

        if not topic:
            return False, "Topic is required"

        # Validate HA URL if provided
        if ha_url:
            if not re.match(r'^https?://', ha_url):
                return False, "Home Assistant URL must start with http:// or https://"

        return True, None

    def _save_config(self) -> bool:
        """Save the configuration.

        Returns:
            True if save was successful
        """
        # Validate first
        is_valid, error = self._validate_config()
        if not is_valid:
            self._show_error(error)
            return False

        # Get values
        broker = self.fields["broker"].get_text().strip()
        port = int(self.fields["port"].get_text().strip())
        username = self.fields["username"].get_text().strip()
        password = self.fields["password"].get_text().strip()
        topic = self.fields["topic"].get_text().strip()
        qos = int(self.fields["qos"].get_value())
        retain = self.fields["retain"].get_active()
        default_device_name = self.fields["default_device_name"].get_text().strip() or None
        ha_url = self.fields["ha_url"].get_text().strip() or None

        # Create config
        config = MQTTConfig(
            broker=broker,
            port=port,
            username=username,
            password=password,
            topic=topic,
            qos=qos,
            retain=retain,
            default_device_name=default_device_name,
            ha_url=ha_url,
        )

        # Save to file
        try:
            config.save_to_file()
            logger.info("MQTT configuration saved successfully")

            # Reinitialize MQTT client with new config
            initialize_mqtt_client()
            logger.info("MQTT client reinitialized with new configuration")

            self._show_success("Configuration saved successfully! MQTT client reconnected.")
            return True

        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            self._show_error(f"Failed to save configuration: {str(e)}")
            return False

    def _test_mqtt(self):
        """Test MQTT connection and publish a test message."""
        # Validate first
        is_valid, error = self._validate_config()
        if not is_valid:
            self._show_error(f"Configuration invalid: {error}")
            return

        self._show_info("Testing MQTT connection...")

        client = get_mqtt_client()
        if not client:
            self._show_error("MQTT client not initialized. Save configuration first.")
            return

        try:
            # Test connection and publish
            success, message = client.test_connection()

            if success:
                self._show_success(f"✓ {message}")
                logger.info("MQTT test successful")
            else:
                self._show_error(f"✗ {message}")
                logger.error(f"MQTT test failed: {message}")

        except Exception as e:
            logger.error(f"MQTT test exception: {e}")
            self._show_error(f"Test failed: {str(e)}")

    def _on_response(self, dialog, response_id):
        """Handle dialog response."""
        if response_id == Gtk.ResponseType.OK:
            # Save
            if self._save_config():
                dialog.destroy()
        elif response_id == Gtk.ResponseType.APPLY:
            # Test MQTT
            self._test_mqtt()
        else:
            # Cancel
            dialog.destroy()

    def _show_error(self, message: str):
        """Show error message in status label."""
        self.status_label.set_markup(f'<span color="red">✗ {message}</span>')

    def _show_success(self, message: str):
        """Show success message in status label."""
        self.status_label.set_markup(f'<span color="green">{message}</span>')

    def _show_info(self, message: str):
        """Show info message in status label."""
        self.status_label.set_markup(f'<span color="blue">ℹ {message}</span>')
