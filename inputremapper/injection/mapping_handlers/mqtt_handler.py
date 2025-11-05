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

"""MQTT handler for publishing input events to Home Assistant."""

from typing import Dict

from inputremapper.configs.input_config import InputCombination
from inputremapper.configs.mapping import Mapping
from inputremapper.exceptions import MappingParsingError
from inputremapper.injection.mapping_handlers.mapping_handler import (
    MappingHandler,
    HandlerEnums,
)
from inputremapper.input_event import InputEvent
from inputremapper.logging.logger import logger
from inputremapper.mqtt_client import get_mqtt_client, get_mqtt_config


class MQTTHandler(MappingHandler):
    """Publishes MQTT messages when notified of input events."""

    _active: bool
    _mqtt_action: str
    _device_name: str

    def __init__(
        self,
        combination: InputCombination,
        mapping: Mapping,
        context=None,
        **_,
    ):
        # Note: We don't need global_uinputs since we're not injecting keys
        super().__init__(combination, mapping, None)

        # Get the MQTT action string from the mapping's output_symbol
        if not mapping.output_symbol:
            raise MappingParsingError(
                "Unable to create MQTT handler: no MQTT action string defined",
                mapping=mapping
            )

        self._mqtt_action = mapping.output_symbol
        self._active = False

        # Get device name from context, config, or use a default
        if context and hasattr(context, 'device_name'):
            self._device_name = context.device_name
        else:
            mqtt_config = get_mqtt_config()
            if mqtt_config and mqtt_config.default_device_name:
                self._device_name = mqtt_config.default_device_name
            else:
                self._device_name = "unknown_device"

    def __str__(self):
        return f"MQTTHandler for '{self._mqtt_action}'"

    def __repr__(self):
        return f"<{str(self)} at {hex(id(self))}>"

    @property
    def child(self):  # used for logging
        return f"publishes MQTT: device='{self._device_name}', action='{self._mqtt_action}'"

    def set_device_name(self, device_name: str):
        """Set the device name for MQTT publishing.

        This should be called by the injector or context to set the actual device name.
        """
        self._device_name = device_name

    def notify(self, event: InputEvent, *_, **__) -> bool:
        """Publish MQTT message when key is pressed.

        Only publishes on press (value > 0), not on release (value == 0).
        """
        # Only publish on press events (value > 0), not release
        if event.value <= 0:
            self._active = False
            return True

        # Get MQTT client
        mqtt_client = get_mqtt_client()
        if not mqtt_client:
            logger.error("MQTT client not initialized, cannot publish event")
            return False

        # Publish the event
        try:
            success = mqtt_client.publish_event(
                device_name=self._device_name,
                pressed_key=self._mqtt_action,
                ensure_connected=True
            )

            if success:
                self._active = True
                logger.debug(
                    f"MQTT event published successfully: "
                    f"device='{self._device_name}', action='{self._mqtt_action}'"
                )
            else:
                logger.error(
                    f"Failed to publish MQTT event: "
                    f"device='{self._device_name}', action='{self._mqtt_action}'"
                )

            return success

        except Exception as e:
            logger.error(f"Exception in MQTT handler: {e}")
            import traceback
            logger.debug(f"MQTT handler exception traceback:\n{traceback.format_exc()}")
            return False

    def reset(self) -> None:
        """Reset handler state.

        For MQTT, we don't need to send a release event since we only publish on press.
        """
        logger.debug("resetting mqtt_handler")
        self._active = False

    def needs_wrapping(self) -> bool:
        """Whether this handler needs to be wrapped in a combination handler."""
        return True

    def wrap_with(self) -> Dict[InputCombination, HandlerEnums]:
        """Return the handler type to wrap this handler with."""
        return {InputCombination(self.input_configs): HandlerEnums.combination}
