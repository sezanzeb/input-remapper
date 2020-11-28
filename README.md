<h1 align="center">Key Mapper</h1>

<p align="center">A Linux tool to change and program the mapping of your input device buttons.</p>

<p align="center"><img src="readme/pylint.svg"/> <img src="readme/coverage.svg"/></p>

<p align="center">
<img src="readme/screenshot.png"/>
</p>
<br/>

## Usage

To open the UI to modify the mappings, use:

```bash
key-mapper-gtk
```

You can also start it via your applications menu.

To keep injecting the mapping after closing the window, the daemon needs to
be running. If it doesn't already after logging in, you can use:

```bash
key-mapper-service
```

## Macros

It is possible to write timed macros into the center column:
- `k(1)` 1
- `k(1).w(10).k(2)` 12
- `r(3, k(a).w(10))` aaa
- `r(2, k(a).k(-)).k(b)` a-a-b
- `w(1000).m(SHIFT_L, r(2, k(a))).w(10, 20).k(b)` AAb

Documentation:
- `r` repeats
- `w` waits in ms (randomly with 2 parameters)
- `k` writes a keystroke
- `m` modifies
- `.` executes two actions behind each other

For a list of supported keystrokes and their names, check the output of `xmodmap -pke`

## Git Installation

```bash
git clone https://github.com/sezanzeb/key-mapper.git
cd key-mapper
sudo python3 setup.py install
usermod -a -G input $USER
usermod -a -G plugdev $USER
```

Depending on how those packages are called in your distro,
you need the following dependencies:

`python3-distutils-extra` `python3-evdev` `python3-dbus`

It works with both Wayland and X11.

## Tests

```bash
pylint keymapper --extension-pkg-whitelist=evdev
sudo python3 setup.py install && python3 tests/test.py
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
- [ ] support timed macros, maybe using some sort of syntax
- [ ] add to the AUR, provide .deb and .appimage files
- [ ] automatically load presets when devices get plugged in after login
