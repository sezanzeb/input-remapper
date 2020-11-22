# Key Mapper

Tool to change the mapping of your input device buttons.

<p align="center">
    <img src="data/screenshot.png"/>
</p>

# Running

```bash
sudo python3 setup.py install && sudo key-mapper-gtk -d
```

You can also start it via your applications menu.

# Dependencies

Depending on how those packages are called in your distro:

`python3-distutils-extra` `python3-evdev` `python3-dbus`

It works with both Wayland and X11.

# Tests

```bash
pylint keymapper --extension-pkg-whitelist=evdev
sudo python3 setup.py install && python3 tests/test.py
```

# Roadmap

- [x] show a dropdown to select an arbitrary device from `xinput list`
- [x] creating presets per device
- [x] renaming presets
- [x] show a list for mappings `[keycode -> target]`
- [x] make that list extend itself automatically
- [x] read keycodes with evdev
- [x] inject the mapping
- [x] keep the system defaults for unmapped buttons
- [x] button to stop mapping and using system defaults
- [x] highlight changes and alert before discarding unsaved changes
- [ ] automatically load presets on login for plugged in devices
- [ ] automatically load presets when devices get plugged in after login
- [x] ask for administrator permissions using polkit
- [x] make sure it works on wayland
- [ ] add to the AUR, provide .deb and .appimage files
- [ ] support timed macros, maybe using some sort of syntax
