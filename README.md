<h1 align="center">Key Mapper</h1>

<p align="center">A Linux tool to change the mapping of your input device buttons.</p>

<p align="center"><img src="data/pylint.svg"/> <img src="data/coverage.svg"/></p>

<p align="center">
<img src="data/screenshot.png"/>
</p>

## Table of Contents

- [Packages](#Packages)
- [Usage](#Packages)
- [Git Installation](#Git_Installation)
- [Tests](#Tests)
- [Roadmap](#Roadmap)

## Packages

TODO

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
- [ ] automatically load presets on login for plugged in devices
- [ ] automatically load presets when devices get plugged in after login
- [x] make sure it works on wayland
- [ ] add to the AUR, provide .deb and .appimage files
- [ ] support timed macros, maybe using some sort of syntax
