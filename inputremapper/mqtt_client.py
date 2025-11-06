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

"""MQTT client for publishing input events to Home Assistant."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    mqtt = None

from inputremapper.logging.logger import logger


class MQTTConfig:
    """Configuration for MQTT broker connection."""

    def __init__(
        self,
        broker: str = "192.168.1.160",
        port: int = 1883,
        username: str = "mqttuser",
        password: str = "mqttuser",
        topic: str = "key_remap/events",
        qos: int = 1,
        retain: bool = False,
        default_device_name: Optional[str] = None,
        ha_url: Optional[str] = None,
    ):
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.topic = topic
        self.qos = qos
        self.retain = retain
        self.default_device_name = default_device_name
        self.ha_url = ha_url

    @classmethod
    def load_from_file(cls, config_path: Optional[str] = None) -> MQTTConfig:
        """Load MQTT configuration from file.

        Args:
            config_path: Path to config file. If None, uses ~/mqtt_config.json

        Returns:
            MQTTConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid
        """
        if config_path is None:
            config_path = os.path.expanduser("~/mqtt_config.json")

        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"MQTT config file not found at {config_path}. "
                f"Please create a config file with broker, port, username, and password."
            )

        try:
            with open(config_path, "r") as f:
                config_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in MQTT config file: {e}")

        # Validate required fields
        required_fields = ["broker", "port", "username", "password"]
        missing_fields = [f for f in required_fields if f not in config_data]
        if missing_fields:
            raise ValueError(
                f"Missing required fields in MQTT config: {', '.join(missing_fields)}"
            )

        return cls(
            broker=config_data["broker"],
            port=int(config_data["port"]),
            username=config_data["username"],
            password=config_data["password"],
            topic=config_data.get("topic", "key_remap/events"),
            qos=int(config_data.get("qos", 1)),
            retain=bool(config_data.get("retain", False)),
            default_device_name=config_data.get("default_device_name"),
            ha_url=config_data.get("ha_url"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for saving."""
        return {
            "broker": self.broker,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "topic": self.topic,
            "qos": self.qos,
            "retain": self.retain,
            "default_device_name": self.default_device_name,
            "ha_url": self.ha_url,
        }

    def save_to_file(self, config_path: Optional[str] = None) -> None:
        """Save MQTT configuration to file.

        Args:
            config_path: Path to config file. If None, uses ~/mqtt_config.json
        """
        if config_path is None:
            config_path = os.path.expanduser("~/mqtt_config.json")

        with open(config_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

        logger.info(f"MQTT config saved to {config_path}")


class MQTTClient:
    """MQTT client for publishing input events to Home Assistant.

    This client handles connection, reconnection, and publishing of events
    to an MQTT broker for Home Assistant integration.
    """

    def __init__(self, config: MQTTConfig):
        """Initialize MQTT client.

        Args:
            config: MQTTConfig instance with broker settings
        """
        if not MQTT_AVAILABLE:
            raise ImportError(
                "paho-mqtt is not installed. Please install it with:\n"
                "  System package (recommended): sudo apt install python3-paho-mqtt\n"
                "  or pip: pip3 install paho-mqtt"
            )

        self.config = config
        self._client: Optional[mqtt.Client] = None
        self._connected = False
        self._lock = threading.Lock()
        self._connect_thread: Optional[threading.Thread] = None
        self._should_stop = False

        logger.info(
            f"Initializing MQTT client: broker={config.broker}, "
            f"port={config.port}, topic={config.topic}, QoS={config.qos}"
        )
        # Hide password in logs
        logger.debug(f"MQTT username: {config.username}")

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when client connects to broker."""
        if rc == 0:
            self._connected = True
            logger.info(f"Connected to MQTT broker at {self.config.broker}:{self.config.port}")
        else:
            self._connected = False
            error_messages = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorized",
            }
            error_msg = error_messages.get(rc, f"Unknown error code: {rc}")
            logger.error(f"Failed to connect to MQTT broker: {error_msg}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback when client disconnects from broker."""
        self._connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnect from MQTT broker (code: {rc}). Will attempt to reconnect.")

    def _on_publish(self, client, userdata, mid):
        """Callback when message is published."""
        logger.debug(f"MQTT message published (mid: {mid})")

    def connect(self) -> bool:
        """Connect to MQTT broker.

        Returns:
            True if connection successful, False otherwise
        """
        if self._connected:
            return True

        try:
            with self._lock:
                # Create new client instance
                self._client = mqtt.Client()
                self._client.username_pw_set(self.config.username, self.config.password)
                self._client.on_connect = self._on_connect
                self._client.on_disconnect = self._on_disconnect
                self._client.on_publish = self._on_publish

                # Enable automatic reconnection
                self._client.reconnect_delay_set(min_delay=1, max_delay=120)

                logger.info(f"Connecting to MQTT broker at {self.config.broker}:{self.config.port}...")
                self._client.connect(self.config.broker, self.config.port, keepalive=60)

                # Start network loop in background
                self._client.loop_start()

                # Wait a bit for connection to establish
                timeout = 5
                start_time = time.time()
                while not self._connected and time.time() - start_time < timeout:
                    time.sleep(0.1)

                if self._connected:
                    logger.info("MQTT client connected successfully")
                    return True
                else:
                    logger.error("MQTT connection timeout")
                    return False

        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            import traceback
            logger.debug(f"Connection error traceback:\n{traceback.format_exc()}")
            return False

    def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        self._should_stop = True
        if self._client:
            with self._lock:
                self._client.loop_stop()
                self._client.disconnect()
                self._connected = False
            logger.info("Disconnected from MQTT broker")

    def is_connected(self) -> bool:
        """Check if client is connected to broker.

        Returns:
            True if connected, False otherwise
        """
        return self._connected

    def publish_event(
        self,
        device_name: str,
        pressed_key: str,
        ensure_connected: bool = True
    ) -> bool:
        """Publish input event to MQTT broker.

        Args:
            device_name: Name of the input device
            pressed_key: The string action to publish
            ensure_connected: If True, attempt to connect if not connected

        Returns:
            True if publish successful, False otherwise
        """
        # Ensure we're connected
        if not self._connected and ensure_connected:
            logger.info("Not connected to MQTT broker, attempting to connect...")
            if not self.connect():
                logger.error("Failed to connect to MQTT broker, cannot publish event")
                return False

        if not self._connected:
            logger.error("Cannot publish event: not connected to MQTT broker")
            return False

        # Build payload
        payload = {
            "device_name": device_name,
            "pressed_key": pressed_key
        }

        try:
            payload_json = json.dumps(payload)
            result = self._client.publish(
                self.config.topic,
                payload_json,
                qos=self.config.qos,
                retain=self.config.retain
            )

            # Check if publish was queued successfully
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(
                    f"Published MQTT event - device_name: '{device_name}', "
                    f"pressed_key: '{pressed_key}', topic: '{self.config.topic}'"
                )
                return True
            else:
                logger.error(f"Failed to publish MQTT event: error code {result.rc}")
                return False

        except Exception as e:
            logger.error(f"Exception while publishing MQTT event: {e}")
            import traceback
            logger.debug(f"Publish error traceback:\n{traceback.format_exc()}")
            return False

    def test_connection(self) -> tuple[bool, str]:
        """Test the MQTT connection and publish a test message.

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Try to connect
            if not self.connect():
                return False, "Failed to connect to MQTT broker"

            # Try to publish test message
            if self.publish_event("test_device", "test_action", ensure_connected=False):
                return True, "Successfully connected and published test message"
            else:
                return False, "Connected but failed to publish test message"

        except Exception as e:
            return False, f"Test failed with exception: {str(e)}"


# Global MQTT client instance
_mqtt_client: Optional[MQTTClient] = None
_mqtt_config: Optional[MQTTConfig] = None


def get_mqtt_client() -> Optional[MQTTClient]:
    """Get the global MQTT client instance.

    Returns:
        MQTTClient instance or None if not initialized
    """
    return _mqtt_client


def get_mqtt_config() -> Optional[MQTTConfig]:
    """Get the global MQTT config instance.

    Returns:
        MQTTConfig instance or None if not loaded
    """
    return _mqtt_config


def initialize_mqtt_client(config_path: Optional[str] = None) -> bool:
    """Initialize the global MQTT client.

    Args:
        config_path: Path to MQTT config file. If None, uses ~/mqtt_config.json

    Returns:
        True if initialization successful, False otherwise
    """
    global _mqtt_client, _mqtt_config

    try:
        # Load config
        _mqtt_config = MQTTConfig.load_from_file(config_path)

        # Create client
        _mqtt_client = MQTTClient(_mqtt_config)

        # Connect
        if _mqtt_client.connect():
            logger.info("MQTT client initialized and connected successfully")
            return True
        else:
            logger.warning("MQTT client initialized but connection failed. Will retry on first publish.")
            return True  # Still consider initialization successful

    except FileNotFoundError as e:
        logger.error(str(e))
        logger.error(
            "Please create ~/mqtt_config.json with your MQTT broker settings. "
            "See README for details."
        )
        return False
    except ValueError as e:
        logger.error(f"Invalid MQTT configuration: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize MQTT client: {e}")
        import traceback
        logger.debug(f"Initialization error traceback:\n{traceback.format_exc()}")
        return False


def shutdown_mqtt_client() -> None:
    """Shutdown the global MQTT client."""
    global _mqtt_client

    if _mqtt_client:
        _mqtt_client.disconnect()
        _mqtt_client = None
        logger.info("MQTT client shut down")
