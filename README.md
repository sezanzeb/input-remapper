<h1 align="center">Key Mapper</h1>

<p align="center">A tool to change and program the mapping of your input device buttons.</p>

<p align="center">
    <a href="#ubuntudebian">Ubuntu/Debian</a> • <a href="#manjaroarch">Manjaro/Arch</a> • <a href="#git">Git</a>
</p>

<p align="center"><img src="readme/pylint.svg"/> <img src="readme/coverage.svg"/></p>

<p align="center"><img src="readme/screenshot.png"/></p>
<br/>

## Usage

After installing, you should log out and back in for the changed user
groups to take effect and for the background service to start.

To open the UI to modify the mappings, look into your applications menu
and search for 'Key Mapper' in settings. You can also start it via 
`key-mapper-gtk`. It works with both Wayland and X11.

## Macros

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

For a list of supported keystrokes and their names, check the output of
`xmodmap -pke`

## Installation

##### Ubuntu/Debian

```bash
sudo dpkg -i $(wget TODO)
sudo usermod -a -G plugdev,input $USER
```

##### Manjaro/Arch

```bash
pacaur -S key-mapper-git
```

##### Git

```bash
git clone https://github.com/sezanzeb/key-mapper.git
sudo pip install key-mapper
sudo usermod -a -G plugdev,input $USER
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
- [ ] add to the AUR, provide .deb file
- [ ] automatically load presets when devices get plugged in after login

## Tests

```bash
pylint keymapper --extension-pkg-whitelist=evdev
sudo pip install . && python3 tests/test.py
```
