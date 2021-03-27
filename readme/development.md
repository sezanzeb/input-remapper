# Development

Contributions are very welcome, I will gladly review and discuss any merge
requests. If you have questions about the code and architecture, feel free
to [open an issue](https://github.com/sezanzeb/key-mapper/issues). This
file should give an overview about some internals of key-mapper.

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
- [x] inject in an additional device instead to avoid clashing capabilities
- [x] don't run any GUI code as root for improved wayland compatibility
- [ ] injecting keys that aren't available in the systems keyboard layout
- [ ] getting it into the official debian repo

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

This will generate `key-mapper/deb/key-mapper-0.8.0.deb`

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
- `bin/key-mapper-helper` provides information to the gui that requires
  root rights. Is stopped when the gui closes.
- `data/key-mapper.policy` configures pkexec. By using auth_admin_keep
  the user is not asked multiple times for each task that needs elevated
  rights. This is done instead of granting the whole application root rights
  because it is [considered problematic](https://wiki.archlinux.org/index.php/Running_GUI_applications_as_root).
- `data/key-mapper.desktop` is the entry in the start menu

**cli**

- `bin/key-mapper-control` is an executable to send messages to the service
  via dbus. It can be used to start and stop injection without a GUI.
  The gui also uses it to run the service (if not already running) and
  helper, because by using one single command for both the polkit rules file
  remembers not to ask for a password again.

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

## Permissions

**gui**

The gui process starts without root rights. It makes sure the daemon and
helper are running via pkexec.

**daemon**

The daemon exists to keep injections alive beyond the lifetime of the
user interface. Runs via root. Communicates via dbus. Either started
via systemd or pkexec.

**helper**

The helper provides information to the user interface like events and
devices. Communicates via pipes. It should not exceed the lifetime of
the user interface because it exposes all the input events. Starts via
pkexec.

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

If `sudo evtest` shows an event for the button, try to
modify `should_map_as_btn`. If not, the button cannot be mapped.

## How it works

It uses evdev. The links below point to older code in 0.7.0 so that their
line numbers remain valid.

1. It grabs a device (e.g. /dev/input/event3), so that the key events won't
   reach X11/Wayland anymore
   [source](https://github.com/sezanzeb/key-mapper/blob/0.7.0/keymapper/injection/injector.py#L182)
2. Reads the events from it (`evtest` can do it, you can also do
   `cat /dev/input/event3` which yields binary stuff)
   [source](https://github.com/sezanzeb/key-mapper/blob/0.7.0/keymapper/injection/injector.py#L413)
3. Looks up the mapping if that event maps to anything
   [source](https://github.com/sezanzeb/key-mapper/blob/0.7.0/keymapper/injection/keycode_mapper.py#L421)
4. Injects the output event in a new device that key-mapper created (another
   new path in /dev/input, device name is suffixed by "mapped")
   [source](https://github.com/sezanzeb/key-mapper/blob/0.7.0/keymapper/injection/keycode_mapper.py#L227),
   [new device](https://github.com/sezanzeb/key-mapper/blob/0.7.0/keymapper/injection/injector.py#L324)
5. Forwards any events that should not be mapped to anything in another new
   device (device name is suffixed by "forwarded")
   [source](https://github.com/sezanzeb/key-mapper/blob/0.7.0/keymapper/injection/keycode_mapper.py#L232),
   [new device](https://github.com/sezanzeb/key-mapper/blob/0.7.0/keymapper/injection/injector.py#L342)

This stuff is going on as a daemon in the background

## Resources

- [Guidelines for device capabilities](https://www.kernel.org/doc/Documentation/input/event-codes.txt)
- [PyGObject API Reference](https://lazka.github.io/pgi-docs/)
- [python-evdev](https://python-evdev.readthedocs.io/en/stable/)
- [Python Unix Domain Sockets](https://pymotw.com/2/socket/uds.html)
- [GNOME HIG](https://developer.gnome.org/hig/stable/)
