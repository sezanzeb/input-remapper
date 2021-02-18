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
- [x] add "disable" as mapping option
- [x] mapping joystick directions as buttons, making it act like a D-Pad
- [x] mapping mouse wheel events to buttons
- [x] automatically load presets when devices get plugged in after login (udev)
- [x] map keys using a `modifier + modifier + ... + key` syntax
- [ ] injecting keys that aren't available in the systems keyboard layout
- [x] inject in an additional device instead to avoid clashing capabilities
- [ ] ship with a list of all keys known to xkb and validate input in the gui

## Tests

```bash
sudo pip install coverage
pylint keymapper --extension-pkg-whitelist=evdev
sudo pip install . && coverage run tests/test.py
coverage combine && coverage report -m
```

To read events, `evtest` is very helpful. Add `-d` to `key-mapper-gtk`
to get debug output.

Single tests can be executed via

```bash
python3 tests/test.py test_paths.TestPaths.test_mkdir
```

## Releasing

ssh/login into a debian/ubuntu environment

```bash
./scripts/build.sh
```

This will generate `key-mapper/deb/key-mapper-0.6.1.deb`

## Badges

```bash
sudo pip install git+https://github.com/jongracecox/anybadge
./scripts/badges.sh
```

New badges, if needed, will be created in `readme/` and they
just need to be commited.

## Files

**gui**

- `bin/key-mapper-gtk` the executable that starts the gui. It also sends
  messages to the service via dbus if certain buttons are clicked.
- `bin/key-mapper-gtk-pkexec` opens a password promt to grant root rights
  to the GUI, so that it can read from devices
- `data/key-mapper.policy` configures pkexec
- `data/key-mapper.desktop` is the entry in the start menu

**cli**

- `bin/key-mapper-control` is an executable to send messages to the service
  via dbus. It can be used to start and stop injection without a GUI.

**service**

- `bin/key-mapper-service` executable that starts listening for
  commands via dbus and runs the injector when needed. It shouldn't matter how
  it is started as long as it manages to start without throwing errors. It
  usually needs root rights.
- `data/key-mapper.service` starts key-mapper-service automatically on boot
  on distros using systemd.
- `data/keymapper.Control.conf` is needed to connect to dbus services started
  by systemd from other applications.

**autoload**

- `data/key-mapper-autoload.desktop` executes on login and tells the systemd
  service to stop injecting (possibly the presets of another user) and to
  inject the users autoloaded presets instead (if any are configured)
- `data/key-mapper.rules` udev rule that sends a message to the service to
  start injecting for new devices when they are seen for the first time.

**Example system startup**

1. systemd loads `key-mapper.service` on boot
2. on login, `key-mapper-autoload.desktop` is executed, which has knowledge 
   of the current user und doesn't run as root  
   2.1 it sends the users config directory to the service  
   2.2 it makes the service stop all ongoing injectings  
   2.3 it tells the service to start loading all of the configured presets
3. a bluetooth device gets connected, so udev runs `key-mapper.rules` which
   tells the service to start injecting for that device if it has a preset
   assigned. Works because step 2 told the service about the current users
   config.

Communication to the service always happens via `key-mapper-control`

## Unsupported Devices

Either open up an issue or debug it yourself and make a pull request.

You will need to work with the devices capabilities. You can get those using

```
sudo evtest
```

**It tries or doesn't try to map ABS_X/ABS_Y**

Is the device a gamepad? Does the GUI show joystick configurations?

- if yes, no: adjust `is_gamepad` to loosen up the constraints
- if no, yes: adjust `is_gamepad` to tighten up the constraints

Try to do it in such a way that other devices won't break. Also see 
readme/capabilities.md

**It won't offer mapping a button**

Modify `should_map_as_btn`

## Resources

- [Guidelines for device capabilities](https://www.kernel.org/doc/Documentation/input/event-codes.txt)
- [PyGObject API Reference](https://lazka.github.io/pgi-docs/)
- [python-evdev](https://python-evdev.readthedocs.io/en/stable/)
