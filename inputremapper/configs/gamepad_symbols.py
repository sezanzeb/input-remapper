# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings

"""Symbols and mappings for Gamepad Analog Sticks, Triggers and D-Pad."""

from typing import Dict, Tuple, Optional
from evdev.ecodes import (
    ABS_X,
    ABS_Y,
    ABS_RX,
    ABS_RY,
    ABS_Z,
    ABS_RZ,
    ABS_HAT0X,
    ABS_HAT0Y,
)

MIN_ABS = -32768
MAX_ABS = 32767

# Format: SYMBOL_NAME: (axis_code, value)
GAMEPAD_AXIS_DEFINITIONS: Dict[str, Tuple[int, int]] = {
    # Left Stick (Stick Izquierdo)
    "STICK_LEFT_UP": (ABS_Y, MIN_ABS),
    "STICK_LEFT_DOWN": (ABS_Y, MAX_ABS),
    "STICK_LEFT_LEFT": (ABS_X, MIN_ABS),
    "STICK_LEFT_RIGHT": (ABS_X, MAX_ABS),
    "LS_UP": (ABS_Y, MIN_ABS),
    "LS_DOWN": (ABS_Y, MAX_ABS),
    "LS_LEFT": (ABS_X, MIN_ABS),
    "LS_RIGHT": (ABS_X, MAX_ABS),
    # Right Stick (Stick Derecho)
    "STICK_RIGHT_UP": (ABS_RY, MIN_ABS),
    "STICK_RIGHT_DOWN": (ABS_RY, MAX_ABS),
    "STICK_RIGHT_LEFT": (ABS_RX, MIN_ABS),
    "STICK_RIGHT_RIGHT": (ABS_RX, MAX_ABS),
    "RS_UP": (ABS_RY, MIN_ABS),
    "RS_DOWN": (ABS_RY, MAX_ABS),
    "RS_LEFT": (ABS_RX, MIN_ABS),
    "RS_RIGHT": (ABS_RX, MAX_ABS),
    # Analog Triggers (Gatillos LT / RT)
    "TRIGGER_LEFT": (ABS_Z, MAX_ABS),
    "TRIGGER_RIGHT": (ABS_RZ, MAX_ABS),
    "LT": (ABS_Z, MAX_ABS),
    "RT": (ABS_RZ, MAX_ABS),
    # D-Pad Hat Switch
    "DPAD_UP": (ABS_HAT0Y, -1),
    "DPAD_DOWN": (ABS_HAT0Y, 1),
    "DPAD_LEFT": (ABS_HAT0X, -1),
    "DPAD_RIGHT": (ABS_HAT0X, 1),
}


def is_gamepad_axis_symbol(symbol: Optional[str]) -> bool:
    if not symbol:
        return False
    return symbol.upper() in GAMEPAD_AXIS_DEFINITIONS


def get_gamepad_axis_info(symbol: Optional[str]) -> Optional[Tuple[int, int]]:
    if not symbol:
        return None
    return GAMEPAD_AXIS_DEFINITIONS.get(symbol.upper())
