<h1 align="center">Key Mapper</h1>

<p align="center">A tool to change and program the mapping of your input device buttons.</p>

<p align="center"><img src="readme/pylint.svg"/> <img src="readme/coverage.svg"/></p>

<p align="center"><img src="readme/screenshot.png"/></p>
<br/>

## Usage

To open the UI to modify the mappings, look into your applications menu
and search for 'Key Mapper' in settings. You can also start it via 
`key-mapper-gtk`. It works with both Wayland and X11.

If stuff doesn't work, check the output of `key-mapper-gtk -d` and feel free
to open up an issue here.

##### Macros

It is possible to write timed macros into the center column:
- `k(1).k(2)` 1, 2
- `r(3, k(a).w(500))` a, a, a with 500ms pause
- `m(Control_L, k(a).k(x))` CTRL + a, CTRL + x

Documentation:
- `r` repeats the execution of the second parameter
- `w` waits in milliseconds
- `k` writes a single keystroke
- `m` holds a modifier while executing the second parameter
- `.` executes two actions behind each other

##### Names

For a list of supported keystrokes and their names for the middle column,
check the output of `xmodmap -pke`

- Alphanumeric `a` to `z` and `0` to `9`
- Modifiers `Alt_L` `Control_L` `Control_R` `Shift_L` `Shift_R`

If you can't find what you need, consult
[linux/input-event-codes.h](https://github.com/torvalds/linux/blob/master/include/uapi/linux/input-event-codes.h)

- Mouse buttons `BTN_LEFT` `BTN_RIGHT` `BTN_MIDDLE` `BTN_SIDE`
- Multimedia keys `KEY_NEXTSONG`, `KEY_PLAYPAUSE`, ...
- Macro special keys `KEY_MACRO1` `KEY_MACRO2` ...

##### Gamepads

Tested with the XBOX 360 Gamepad. Joystick movements will be translated
to mouse movements. Buttons can be mapped to keycodes or macros. D-Pad
only works as two buttons - horizontal and vertical.

## Installation

After your installation, independent of the method, you should add yourself
to the `input` and `plugdev` groups so that you can read information from your
devices. You have to start the application via sudo otherwise.

```bash
sudo usermod -a -G plugdev,input $USER
# log out and back in or restart, the two groups should be visible with:
groups
```

##### Manjaro/Arch

```bash
pacaur -S key-mapper-git
```

##### Ubuntu/Debian

```bash
wget "https://github.com/sezanzeb/key-mapper/releases/"\
"download/0.1.0/python3-key-mapper_0.1.0-1_all.deb"
sudo dpkg -i python3-key-mapper_0.1.0-1_all.deb
```

##### Git/pip

```bash
# you may need to use --force to overwrite an existing source installation
sudo pip install git+https://github.com/sezanzeb/key-mapper.git
# or
git clone https://github.com/sezanzeb/key-mapper.git
cd key-mapper && sudo python3 setup.py install
```

## Roadmap

- [x] show a dropdown to select valid devices
- [x] creating presets per device
- [x] renaming presets
- [x] show a mapping table
- [x] make that list extend itself automatically
- [x] read keycodes with evdev
- [x] inject the mapping
- [x] keep the system defaults for unmapped buttons
- [x] button to stop mapping and using system defaults
- [x] highlight changes and alert before discarding unsaved changes
- [x] automatically load presets on login for plugged in devices
- [x] make sure it works on wayland
- [x] support timed macros, maybe using some sort of syntax
- [x] add to the AUR, provide .deb file
- [x] support gamepads as keyboard and mouse combi
- [ ] automatically load presets when devices get plugged in after login

## Tests

```bash
pylint keymapper --extension-pkg-whitelist=evdev
sudo pip install . && coverage run tests/test.py
coverage combine && coverage report -m
```

To read events, `evtest` is very helpful.
