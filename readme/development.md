# Development

Contributions are very welcome, I will gladly review and discuss any merge
requests.

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
- [x] basic support for gamepads as keyboard and mouse combi
- [x] executing a macro forever while holding down the key using `h`
- [x] mapping D-Pad directions as buttons
- [ ] support for non-GUI TTY environments with a command to stop and start
- [ ] mapping joystick directions as buttons, making it act like a D-Pad
- [ ] configure joystick purpose and speed via the GUI
- [ ] automatically load presets when devices get plugged in after login (udev)
- [ ] mapping a combined button press to a key
- [ ] start the daemon in the input group to not require usermod somehow
- [ ] configure locale for preset to provide a different set of possible keys

## Tests

```bash
pylint keymapper --extension-pkg-whitelist=evdev
sudo pip install . && coverage run tests/test.py
coverage combine && coverage report -m
```

To read events, `evtest` is very helpful. Add `-d` to `key-mapper-gtk`
to get debug output.

## Releasing

ssh/login into a ubuntu machine

```bash
./scripts/build.sh
```

this will generate `key-mapper/deb_dist/python3-key-mapper_0.3.1-1_all.deb`
depending on the version configured in setup.py

## Badges

```bash
sudo pip install git+https://github.com/jongracecox/anybadge
sudo pip install git+https://github.com/dbrgn/coverage-badge
./scripts/badges.sh
```

new badges, if needed, will be created in `readme/` and they
just need to be commited.
