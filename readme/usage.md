# Usage

To open the UI to modify the mappings, look into your applications menu
and search for 'Key Mapper' in settings. You can also start it via 
`key-mapper-gtk`. It works with both Wayland and X11.

To change the mapping, you need to use the "Apply Defaults" button, so that
the application can read the original keycode. It would otherwise be
invisible since the daemon maps it independently of the GUI.

For changes to take effect, save the preset first. Otherwise, the daemon
won't be able to know about your changes.

If stuff doesn't work, check the output of `key-mapper-gtk -d` and feel free
to open up an issue here. Make sure to not post any debug logs that were
generated while you entered private information with your device. Debug
logs are quite verbose.

## Macros

It is possible to write timed macros into the center column:
- `k(1).k(2)` 1, 2
- `r(3, k(a).w(500))` a, a, a with 500ms pause
- `m(Control_L, k(a).k(x))` CTRL + a, CTRL + x
- `k(1).h(k(2)).k(3)` writes 1 2 2 ... 2 2 3 while the key is pressed

Documentation:
- `r` repeats the execution of the second parameter
- `w` waits in milliseconds
- `k` writes a single keystroke
- `m` holds a modifier while executing the second parameter
- `h` executes the parameter as long as the key is pressed down
- `.` executes two actions behind each other

Syntax errors are shown in the UI on save. each `k` function adds a short
delay of 10ms between key-down, key-up and ad the end that can be configured
in `~/.config/key-mapper/config`.

Bear in mind that anti-cheat software might detect macros in games.

## Key Names

Check the autocompletion of the GUI for possible values. You can also
obtain a complete list of possiblities using `key-mapper-service --key-names`.
Examples:

- Alphanumeric `a` to `z` and `0` to `9`
- Modifiers `Alt_L` `Control_L` `Control_R` `Shift_L` `Shift_R`
- Mouse buttons `BTN_LEFT` `BTN_RIGHT` `BTN_MIDDLE` `BTN_SIDE` ...
- Multimedia keys `KEY_NEXTSONG` `KEY_PLAYPAUSE` ...

## Gamepads

Joystick movements will be translated to mouse movements, while the second
joystick acts as a mouse wheel. All buttons, triggers and D-Pads can be
mapped to keycodes and macros. The purpose of your joysticks can be
configured in the json files with the `gamepad.joystick.left_purpose` and
`right_purpose` keys. See below for more info.

The D-Pad can be mapped to W, A, S, D for example, to run around in games,
while the joystick turns the view.

Tested with the XBOX 360 Gamepad. On Ubuntu, gamepads worked better in
Wayland than with X11 for me.

## Configuration Files

The default configuration is stored at `~/.config/key-mapper/config.json`.
The current default configuration as of commit `42cb7fe` looks like:

```json
{
    "autoload": {},
    "macros": {
        "keystroke_sleep_ms": 10
    },
    "gamepad": {
        "joystick": {
            "non_linearity": 4,
            "pointer_speed": 80,
            "left_purpose": "mouse",
            "right_purpose": "wheel"
        }
    }
}
```

Anything that is relevant to presets can be overwritten in them as well.
Here is an example configuration for preset "a" for the "gamepad" device:
`~/.config/key-mapper/gamepad/a.json`

```json
{
    "macros": {
        "keystroke_sleep_ms": 100
    },
    "mapping": {
        "1,315,1": "1",
        "1,307,1": "k(2).k(3)"
    }
}
```

Both need to be valid json files, otherwise the parser refuses to work. This
preset maps the EV_KEY down event with code 315 to '1', code 307 to a macro
and sets the time between injected events of macros to 100 ms. Note that
a complete keystroke consists of two events: down and up. Other than that,
it inherits all configurations from `~/.config/key-mapper/config.json`.
If config.json is missing some stuff, it will query the hardcoded default
values.
