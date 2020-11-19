# Key Mapper

**Almost done**

GUI tool to map input buttons to e.g. change the macro keys of a mouse or
any keyboard to something different. It should not be device specific, any
input device supported by Linux plug and play that reports keyboard events
will likely work.

<p align="center">
    <img src="data/screenshot.png"/>
</p>

# Running

```bash
sudo python3 setup.py install && sudo key-mapper-gtk -d
```

You can also start it via your applications menu.

# Dependencies

`python-evdev`

# Tests

```bash
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
- [ ] make it work on wayland
- [ ] add to the AUR, provide .deb and .appimage files
