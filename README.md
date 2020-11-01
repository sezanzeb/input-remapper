# Key Mapper

**Doesn't work yet**

GUI tool to map input buttons to e.g. change the macro keys of a mouse or any keyboard to something
different. It should not be device specific, any input device supported by Linux plug and play will likely
work.

<p align="center">
    <img src="data/screenshot.png"/>
</p>

# Running

```
sudo python3 setup.py install && sudo key-mapper-gtk -d
```

# Dependencies

`evtest`, `libinput`

# Tests

sudo is required because some tests actually read /dev stuff.

```
sudo python3 setup.py install && sudo python3 tests/test.py
```

# Roadmap

- [x] show a dropdown to select an arbitrary device from `xinput list`
- [x] creating presets per device
- [ ] support X, but make it somewhat easy to add wayland to this tool.
- [ ] renaming presets
- [x] show a list that can be extended with a `[+]` button
- [ ] The list shows `[keycode, current key for that keycode -> target]`
- [ ] generate a file for /usr/share/X11/xkb/symbols/ for each preset, (symlink to home .config/?)
- [ ] load that file with `setxkbmap preset1234 -device 13` (on startup?, udev on mouse connect?)
