# Capabilities

A list of example capabilities for reference.

- [Gamepads](#Gamepads)
- [Graphics Tablets](#Graphics-tablets)
- [Touchpads](#Touchpads)

Feel free to extend this list with more devices that are not keyboards
and not mice.

```bash
sudo python3
```

```py
import evdev
evdev.InputDevice('/dev/input/event12').capabilities(verbose=True)
```

## Gamepads

#### Microsoft X-Box 360 pad

```py
{
    ('EV_SYN', 0): [('SYN_REPORT', 0), ('SYN_CONFIG', 1), ('SYN_DROPPED', 3), ('?', 21)],
    ('EV_KEY', 1): [
        (['BTN_A', 'BTN_GAMEPAD', 'BTN_SOUTH'], 304),
        (['BTN_B', 'BTN_EAST'], 305), (['BTN_NORTH', 'BTN_X'], 307),
        (['BTN_WEST', 'BTN_Y'], 308), ('BTN_TL', 310), ('BTN_TR', 311),
        ('BTN_SELECT', 314), ('BTN_START', 315), ('BTN_MODE', 316),
        ('BTN_THUMBL', 317), ('BTN_THUMBR', 318)
    ],
    ('EV_ABS', 3): [
        (('ABS_X', 0), AbsInfo(value=1476, min=-32768, max=32767, fuzz=16, flat=128, resolution=0)),
        (('ABS_Y', 1), AbsInfo(value=366, min=-32768, max=32767, fuzz=16, flat=128, resolution=0)),
        (('ABS_Z', 2), AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)),
        (('ABS_RX', 3), AbsInfo(value=-2950, min=-32768, max=32767, fuzz=16, flat=128, resolution=0)),
        (('ABS_RY', 4), AbsInfo(value=1973, min=-32768, max=32767, fuzz=16, flat=128, resolution=0)),
        (('ABS_RZ', 5), AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)),
        (('ABS_HAT0X', 16), AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)),
        (('ABS_HAT0Y', 17), AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0))
    ],
    ('EV_FF', 21): [
        (['FF_EFFECT_MIN', 'FF_RUMBLE'], 80), ('FF_PERIODIC', 81),
        (['FF_SQUARE', 'FF_WAVEFORM_MIN'], 88), ('FF_TRIANGLE', 89),
        ('FF_SINE', 90), (['FF_GAIN', 'FF_MAX_EFFECTS'], 96)
    ]
}
```

## Graphics tablets

#### Wacom Intuos 5 M

Pen

```py
{
    ('EV_SYN', 0): [
        ('SYN_REPORT', 0), ('SYN_CONFIG', 1),
        ('SYN_MT_REPORT', 2), ('SYN_DROPPED', 3), ('?', 4)
    ],
    ('EV_KEY', 1): [
        (['BTN_LEFT', 'BTN_MOUSE'], 272), ('BTN_RIGHT', 273), ('BTN_MIDDLE', 274),
        ('BTN_SIDE', 275), ('BTN_EXTRA', 276), (['BTN_DIGI', 'BTN_TOOL_PEN'], 320),
        ('BTN_TOOL_RUBBER', 321), ('BTN_TOOL_BRUSH', 322), ('BTN_TOOL_PENCIL', 323),
        ('BTN_TOOL_AIRBRUSH', 324), ('BTN_TOOL_MOUSE', 326), ('BTN_TOOL_LENS', 327),
        ('BTN_TOUCH', 330), ('BTN_STYLUS', 331), ('BTN_STYLUS2', 332)
    ],
    ('EV_REL', 2): [('REL_WHEEL', 8)],
    ('EV_ABS', 3): [
        (('ABS_X', 0), AbsInfo(value=0, min=0, max=44704, fuzz=4, flat=0, resolution=200)),
        (('ABS_Y', 1), AbsInfo(value=0, min=0, max=27940, fuzz=4, flat=0, resolution=200)),
        (('ABS_Z', 2), AbsInfo(value=0, min=-900, max=899, fuzz=0, flat=0, resolution=287)),
        (('ABS_RZ', 5), AbsInfo(value=0, min=-900, max=899, fuzz=0, flat=0, resolution=287)),
        (('ABS_THROTTLE', 6), AbsInfo(value=0, min=-1023, max=1023, fuzz=0, flat=0, resolution=0)),
        (('ABS_WHEEL', 8), AbsInfo(value=0, min=0, max=1023, fuzz=0, flat=0, resolution=0)),
        (('ABS_PRESSURE', 24), AbsInfo(value=0, min=0, max=2047, fuzz=0, flat=0, resolution=0)),
        (('ABS_DISTANCE', 25), AbsInfo(value=0, min=0, max=63, fuzz=1, flat=0, resolution=0)),
        (('ABS_TILT_X', 26), AbsInfo(value=0, min=-64, max=63, fuzz=1, flat=0, resolution=57)),
        (('ABS_TILT_Y', 27), AbsInfo(value=0, min=-64, max=63, fuzz=1, flat=0, resolution=57)),
        (('ABS_MISC', 40), AbsInfo(value=0, min=0, max=0, fuzz=0, flat=0, resolution=0))
    ],
    ('EV_MSC', 4): [('MSC_SERIAL', 0)]
}
```

Pad

```py
{
    ('EV_SYN', 0): [('SYN_REPORT', 0), ('SYN_CONFIG', 1), ('SYN_DROPPED', 3)],
    ('EV_KEY', 1): [
        (['BTN_0', 'BTN_MISC'], 256), ('BTN_1', 257), ('BTN_2', 258),
        ('BTN_3', 259), ('BTN_4', 260), ('BTN_5', 261), ('BTN_6', 262),
        ('BTN_7', 263), ('BTN_8', 264), ('BTN_STYLUS', 331)],
    ('EV_ABS', 3): [
        (('ABS_X', 0), AbsInfo(value=0, min=0, max=1, fuzz=0, flat=0, resolution=0)),
        (('ABS_Y', 1), AbsInfo(value=0, min=0, max=1, fuzz=0, flat=0, resolution=0)),
        (('ABS_WHEEL', 8), AbsInfo(value=0, min=0, max=71, fuzz=0, flat=0, resolution=0)),
        (('ABS_MISC', 40), AbsInfo(value=0, min=0, max=0, fuzz=0, flat=0, resolution=0))
    ]
}
```

#### 10 inch PenTablet

```py
{
    ('EV_SYN', 0): [('SYN_REPORT', 0), ('SYN_CONFIG', 1), ('SYN_DROPPED', 3), ('?', 4)],
    ('EV_KEY', 1): [(['BTN_DIGI', 'BTN_TOOL_PEN'], 320), ('BTN_TOUCH', 330), ('BTN_STYLUS', 331)],
    ('EV_ABS', 3): [
        (('ABS_X', 0), AbsInfo(value=41927, min=0, max=50794, fuzz=0, flat=0, resolution=200)),
        (('ABS_Y', 1), AbsInfo(value=11518, min=0, max=30474, fuzz=0, flat=0, resolution=200)),
        (('ABS_PRESSURE', 24), AbsInfo(value=0, min=0, max=8191, fuzz=0, flat=0, resolution=0)),
        (('ABS_TILT_X', 26), AbsInfo(value=0, min=-127, max=127, fuzz=0, flat=0, resolution=0)),
        (('ABS_TILT_Y', 27), AbsInfo(value=0, min=-127, max=127, fuzz=0, flat=0, resolution=0))
    ],
    ('EV_MSC', 4): [('MSC_SCAN', 4)]
}
```

10 inch PenTablet Mouse

```py
{
    ('EV_SYN', 0): [
        ('SYN_REPORT', 0), ('SYN_CONFIG', 1), ('SYN_MT_REPORT', 2),
        ('SYN_DROPPED', 3), ('?', 4)
    ],
    ('EV_KEY', 1): [
        (['BTN_LEFT', 'BTN_MOUSE'], 272), ('BTN_RIGHT', 273),
        ('BTN_MIDDLE', 274), ('BTN_SIDE', 275), ('BTN_EXTRA', 276),
        ('BTN_TOUCH', 330)
    ],
    ('EV_REL', 2): [
        ('REL_X', 0), ('REL_Y', 1), ('REL_HWHEEL', 6), ('REL_WHEEL', 8),
        ('REL_WHEEL_HI_RES', 11), ('REL_HWHEEL_HI_RES', 12)
    ],
    ('EV_ABS', 3): [
        (('ABS_X', 0), AbsInfo(value=0, min=0, max=32767, fuzz=0, flat=0, resolution=0)),
        (('ABS_Y', 1), AbsInfo(value=0, min=0, max=32767, fuzz=0, flat=0, resolution=0)),
        (('ABS_PRESSURE', 24), AbsInfo(value=0, min=0, max=2047, fuzz=0, flat=0, resolution=0))
    ],
    ('EV_MSC', 4): [('MSC_SCAN', 4)]
}
```

## Touchpads

#### ThinkPad E590 SynPS/2 Synaptics TouchPad

```py
{
    ('EV_SYN', 0): [('SYN_REPORT', 0), ('SYN_CONFIG', 1), ('SYN_DROPPED', 3)],
    ('EV_KEY', 1): [
        (['BTN_LEFT', 'BTN_MOUSE'], 272), ('BTN_TOOL_FINGER', 325),
        ('BTN_TOOL_QUINTTAP', 328), ('BTN_TOUCH', 330),
        ('BTN_TOOL_DOUBLETAP', 333), ('BTN_TOOL_TRIPLETAP', 334),
        ('BTN_TOOL_QUADTAP', 335)
    ],
    ('EV_ABS', 3): [
        (('ABS_X', 0), AbsInfo(value=3111, min=1266, max=5678, fuzz=0, flat=0, resolution=0)),
        (('ABS_Y', 1), AbsInfo(value=2120, min=1162, max=4694, fuzz=0, flat=0, resolution=0)),
        (('ABS_PRESSURE', 24), AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)),
        (('ABS_TOOL_WIDTH', 28), AbsInfo(value=0, min=0, max=15, fuzz=0, flat=0, resolution=0)),
        (('ABS_MT_SLOT', 47), AbsInfo(value=0, min=0, max=1, fuzz=0, flat=0, resolution=0)),
        (('ABS_MT_POSITION_X', 53), AbsInfo(value=0, min=1266, max=5678, fuzz=0, flat=0, resolution=0)),
        (('ABS_MT_POSITION_Y', 54), AbsInfo(value=0, min=1162, max=4694, fuzz=0, flat=0, resolution=0)),
        (('ABS_MT_TRACKING_ID', 57), AbsInfo(value=0, min=0, max=65535, fuzz=0, flat=0, resolution=0)),
        (('ABS_MT_PRESSURE', 58), AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0))
    ]
}
```
