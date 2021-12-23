# Development

Contributions are very welcome, I will gladly review and discuss any merge
requests. If you have questions about the code and architecture, feel free
to [open an issue](https://github.com/sezanzeb/input-remapper/issues). This
file should give an overview about some internals of input-remapper.

All pull requests will at some point require unittests (see below for more
info), the code coverage may only be improved, not decreased. It also has to
be mostly compliant with pylint.

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
- [ ] macro editor with easier to read function names
- [ ] plugin support
- [x] getting it into the official debian repo

## Tests

```bash
sudo pip install coverage
pylint inputremapper --extension-pkg-whitelist=evdev
sudo pkill -f input-remapper
sudo pip install . && coverage run tests/test.py
coverage combine && coverage report -m
```

To read events, `evtest` is very helpful. Add `-d` to `input-remapper-gtk`
to get debug output.

Single tests can be executed via

```bash
python3 tests/test.py test_paths.TestPaths.test_mkdir
```

Don't use your computer during integration tests to avoid interacting
with the gui, which might make tests fail.

## Writing Tests

Tests are in https://github.com/sezanzeb/input-remapper/tree/main/tests

https://github.com/sezanzeb/input-remapper/blob/main/tests/test.py patches some modules and runs tests. The tests need
patches because every environment that runs them will be different. By using patches they all look the same to the
individual tests. Some patches also allow to make some handy assertions, like the `write_history` of `UInput`.

Test files are usually named after the module they are in.

In the tearDown functions, usually one of `quick_cleanup` or `cleanup` should be called. This avoids making a test
fail that comes after your new test, because some state variables might still be modified by yours.

## Releasing

ssh/login into a debian/ubuntu environment

```bash
./scripts/build.sh
```

This will generate `input-remapper/deb/input-remapper-1.2.2.deb`

## Badges

```bash
sudo pip install git+https://github.com/jongracecox/anybadge
./scripts/badges.sh
```

New badges, if needed, will be created in `readme/` and they
just need to be commited.

## Files

**gui**

- `bin/input-remapper-gtk` the executable that starts the gui. It also sends
  messages to the service via dbus if certain buttons are clicked.
- `bin/input-remapper-helper` provides information to the gui that requires
  root rights. Is stopped when the gui closes.
- `data/input-remapper.policy` configures pkexec. By using auth_admin_keep
  the user is not asked multiple times for each task that needs elevated
  rights. This is done instead of granting the whole application root rights
  because it is [considered problematic](https://wiki.archlinux.org/index.php/Running_GUI_applications_as_root).
- `data/input-remapper.desktop` is the entry in the start menu

**cli**

- `bin/input-remapper-control` is an executable to send messages to the service
  via dbus. It can be used to start and stop injection without a GUI.
  The gui also uses it to run the service (if not already running) and
  helper, because by using one single command for both the polkit rules file
  remembers not to ask for a password again.

**service**

- `bin/input-remapper-service` executable that starts listening for
  commands via dbus and runs the injector when needed. It shouldn't matter how
  it is started as long as it manages to start without throwing errors. It
  usually needs root rights.
- `data/input-remapper.service` starts input-remapper-service automatically on boot
  on distros using systemd.
- `data/inputremapper.Control.conf` is needed to connect to dbus services started
  by systemd from other applications.

**autoload**

- `data/input-remapper-autoload.desktop` executes on login and tells the systemd
  service to stop injecting (possibly the presets of another user) and to
  inject the users autoloaded presets instead (if any are configured)
- `data/input-remapper.rules` udev rule that sends a message to the service to
  start injecting for new devices when they are seen for the first time.

**Example system startup**

1. systemd loads `input-remapper.service` on boot
2. on login, `input-remapper-autoload.desktop` is executed, which has knowledge 
   of the current user und doesn't run as root  
   2.1 it sends the users config directory to the service  
   2.2 it makes the service stop all ongoing injectings  
   2.3 it tells the service to start loading all of the configured presets
3. a bluetooth device gets connected, so udev runs `input-remapper.rules` which
   tells the service to start injecting for that device if it has a preset
   assigned. Works because step 2 told the service about the current users
   config.

Communication to the service always happens via `input-remapper-control`

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

It uses evdev. The links below point to the 1.0.0 release, line numbers might have changed in the current main.

1. It grabs a device (e.g. /dev/input/event3), so that the key events won't
   reach X11/Wayland anymore
   [source](https://github.com/sezanzeb/input-remapper/blob/1.0.0/inputremapper/injection/injector.py#L197)
2. Reads the events from it (`evtest` can do it, you can also do
   `cat /dev/input/event3` which yields binary stuff)
   [source](https://github.com/sezanzeb/input-remapper/blob/1.0.0/inputremapper/injection/injector.py#L443)
3. Looks up the mapping if that event maps to anything
   [source](https://github.com/sezanzeb/input-remapper/blob/1.0.0/inputremapper/injection/keycode_mapper.py#L434)
4. Injects the output event in a new device that input-remapper created (another
   new path in /dev/input, device name is suffixed by "mapped")
   [source](https://github.com/sezanzeb/input-remapper/blob/1.0.0/inputremapper/injection/keycode_mapper.py#L242),
   [new device](https://github.com/sezanzeb/input-remapper/blob/1.0.0/inputremapper/injection/injector.py#L356)
5. Forwards any events that should not be mapped to anything in another new
   device (device name is suffixed by "forwarded")
   [source](https://github.com/sezanzeb/input-remapper/blob/1.0.0/inputremapper/injection/keycode_mapper.py#L247),
   [new device](https://github.com/sezanzeb/input-remapper/blob/1.0.0/inputremapper/injection/injector.py#L367)

This stuff is going on as a daemon in the background

## How combinations are injected

Here is an example how combinations are injected:

```
a -> x
a + b -> y
```

1. the `a` button is pressed with your finger, `a 1` arrives via evdev in input-remapper
2. input-remapper maps it to `x 1` and injects it
3. `b` is pressed with your finger, `b 1` arrives via evdev in input-remapper
4. input-remapper sees a triggered combination and maps it to `y 1` and injects it
5. `b` is released, `b 0` arrives at input-remapper
6. input-remapper remembered that it was the trigger for a combination and maps that release to `y 0` and injects it
7. the `a` button is released, `a 0` arrives at input-remapper
8. input-remapper maps that release to `x 0` and injects it

## Multiple sources, single UInput

https://github.com/sezanzeb/input-remapper/blob/1.0.0/inputremapper/injection/injector.py

This "Injector" process is the only process that injects if input-remapper is used for a single device.

Inside `run` of that process there is an iteration of `for source in sources:`,
which runs an event loop for each possible source for events.
Each event loop has convenient access to the "context" to read some globals.

Consider this typical example of device capabilities:

- "BrandXY Mouse" -> EV_REL, BTN_LEFT, ...
- "BrandXY Mouse" -> KEY_1, KEY_2

There are two devices called "BrandXY Mouse", and they report different events.
Key-mapper creates a single uinput to inject all mapped events to. For example

- BTN_LEFT -> a
- KEY_2 -> b

so you end up with a new device with the following capabilities

"input-remapper BrandXY Mouse mapped" -> KEY_A, KEY_B

while input-remapper reads from multiple InputDevices it injects the mapped letters into a single UInput.

## Resources

- [Guidelines for device capabilities](https://www.kernel.org/doc/Documentation/input/event-codes.txt)
- [PyGObject API Reference](https://lazka.github.io/pgi-docs/)
- [python-evdev](https://python-evdev.readthedocs.io/en/stable/)
- [Python Unix Domain Sockets](https://pymotw.com/2/socket/uds.html)
- [GNOME HIG](https://developer.gnome.org/hig/stable/)
