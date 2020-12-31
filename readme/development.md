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
- [x] configure joystick purpose and speed via the GUI
- [x] support for non-GUI TTY environments with a command to stop and start
- [x] start the daemon in such a way to not require usermod
- [x] mapping a combined button press to a key
- [ ] mapping joystick directions as buttons, making it act like a D-Pad
- [ ] automatically load presets when devices get plugged in after login (udev)
- [ ] configure locale for preset to provide a different set of possible keys
- [ ] user-friendly way to map btn_left
- [ ] add "disable" as mapping option

## Tests

```bash
pylint keymapper --extension-pkg-whitelist=evdev
sudo pip install . && coverage run tests/test.py
coverage combine && coverage report -m
```

To read events, `evtest` is very helpful. Add `-d` to `key-mapper-gtk`
to get debug output.

## Releasing

Install dpkg or ssh/login into a debian/ubuntu environment

```bash
./scripts/build.sh
```

This will generate `key-mapper/deb/key-mapper-0.4.0.deb`

## Badges

```bash
sudo pip install git+https://github.com/jongracecox/anybadge
./scripts/badges.sh
```

New badges, if needed, will be created in `readme/` and they
just need to be commited.

## Files

**service**

- `bin/key-mapper-service` executable that starts listening over dbus for
commands and runs the injector when needed. It shouldn't matter how it is
started as long as it manages to start without throwing errors.

**gui**

- `bin/key-mapper-gtk` the executable that starts the gui. It also sends
messages to the service via dbus
- `data/key-mapper.policy` is needed to show a password promt when starting
the gui for sudo rights
- `data/key-mapper.desktop` is the entry in the start menu

**cli**

- `bin/key-mapper-control` is an executable to send messages to the service
via dbus. It can be used to start and stop injection without a gui.

**systemd**

- `data/key-mapper.service` starts key-mapper-service automatically on boot,
systemctl commands are possible.
- `data/keymapper.Control.conf` is needed to connect to dbus services started
by systemd from other applications

**user stuff**

- `key-mapper-autoload.desktop` executes on login and tells the systemd
service to stop injecting (possible the presets of another user) and to
inject the users autoloaded presets instead (if any are configured)

## Resources

[PyGObject API Reference](https://lazka.github.io/pgi-docs/)
[python-evdev](https://python-evdev.readthedocs.io/en/stable/)
