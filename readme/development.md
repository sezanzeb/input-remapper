# Development

Contributions are very welcome, I will gladly review and discuss any merge
requests. If you have questions about the code and architecture, feel free
to [open an issue](https://github.com/sezanzeb/input-remapper/issues). This
file should give an overview about some internals of input-remapper.

All pull requests will at some point require unittests (see below for more
info), the code coverage may only be improved, not decreased. It also has to
be mostly compliant with pylint.

## Tests

```bash
pip install coverage --user
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

There is also a run configuration for PyCharm called "All Tests" included.

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

This will generate `input-remapper/deb/input-remapper-1.5.0.deb`

## Badges

```bash
sudo pip install anybadge pylint
sudo pkill -f input-remapper
sudo pip install .
# the source path in .coveragerc might be incorrect for your system
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

## Resources

- [Guidelines for device capabilities](https://www.kernel.org/doc/Documentation/input/event-codes.txt)
- [PyGObject API Reference](https://lazka.github.io/pgi-docs/)
- [python-evdev](https://python-evdev.readthedocs.io/en/stable/)
- [Python Unix Domain Sockets](https://pymotw.com/2/socket/uds.html)
- [GNOME HIG](https://developer.gnome.org/hig/stable/)
- [GtkSource Example](https://github.com/wolfthefallen/py-GtkSourceCompletion-example)
