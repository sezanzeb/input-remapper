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
mapped to keycodes and macros. Configuring the purpose of your joysticks
is currently done in the global configuration at `~/.config/key-mapper/config`.

The D-Pad can be mapped to W, A, S, D for example, to run around in games,
while the joystick turns the view.

Tested with the XBOX 360 Gamepad. On Ubuntu, gamepads worked better in
Wayland than with X11 for me.
