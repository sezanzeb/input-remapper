# Key Mapper

**Almost done**

GUI tool to map input buttons to e.g. change the macro keys of a mouse or any keyboard to something
different. It should not be device specific, any input device supported by Linux plug and play will likely
work.

<p align="center">
    <img src="data/screenshot.png"/>
</p>

# Running

```bash
sudo python3 setup.py install && sudo key-mapper-gtk -d
```

# Dependencies

No idea which one are relevant at the moment

`evtest`, `libinput`, `python-evdev`

# Tests

```bash
sudo python3 setup.py install && python3 tests/test.py
```

# Roadmap

- [x] show a dropdown to select an arbitrary device from `xinput list`
- [x] creating presets per device
- [x] renaming presets
- [x] show a list for mappings `[keycode -> target]`
- [x] make that list extend itself automatically
- [x] read keycodes with evdev
- [x] generate a file for /usr/share/X11/xkb/symbols/ for each preset
- [x] load that file with `setxkbmap`
- [x] keep the system defaults for unmapped buttons
- [ ] highlight changes and alert before discarding unsaved changes
- [ ] automatically load the preset (on startup?, udev on mouse connect?)
- [ ] make it work on wayland
- [ ] add to the AUR, provide .deb and .appimage files
