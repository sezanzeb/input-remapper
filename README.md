# Key Mapper

GUI tool to map input buttons to e.g. change the macro keys of a mouse or
any keyboard to something different.

Tested on **X11/Manjaro** and **Wayland/Ubuntu**

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

`python3-distutils-extra` `python3-evdev`

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
- [x] read keycodes with evdev
- [x] make that list extend itself automatically
- [x] load that file with `setxkbmap` on button press
- [x] keep the system defaults for unmapped buttons
- [x] button to stop mapping and using system defaults
- [x] highlight changes and alert before discarding unsaved changes
- [ ] automatically load the preset when the mouse connects
- [x] ask for administrator permissions using polkit
- [x] make sure it works on wayland
- [ ] add to the AUR, provide .deb and .appimage files
- [ ] support timed macros, maybe using some sort of syntax
