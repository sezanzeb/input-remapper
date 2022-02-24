# Usage

To open the UI to modify the mappings, look into your applications menu
and search for 'Input Remapper'. You should be prompted for your sudo password
as special permissions are needed to read events from `/dev/input/` files.
You can also start it via `input-remapper-gtk`.

<p align="center">
  <img src="usage_1.png"/>
  <img src="usage_2.png"/>
</p>

First, select your device (like your keyboard) from the large dropdown on the top.
Then you can already edit your keys, as shown in the screenshots.

In the text input field, type the key to which you would like to map this key.
More information about the possible mappings can be found [below](#key-names-and-macros).

Changes are saved automatically. Afterwards press the "Apply" button.

To change the mapping, you need to use the "Stop Injection" button, so that
the application can read the original keycode. It would otherwise be
invisible since the daemon maps it independently of the GUI.

## Troubleshooting

If stuff doesn't work, check the output of `input-remapper-gtk -d` and feel free
to [open up an issue here](https://github.com/sezanzeb/input-remapper/issues/new).
Make sure to not post any debug logs that were generated while you entered
private information with your device. Debug logs are quite verbose.

If input-remapper or your presets prevents your input device from working
at all due to autoload, please try to unplug and plug it in twice.
No injection should be running anymore.

## Combinations

Change the key of your mapping (`Change Key` - Button) and hold a few of your
device keys down. Releasing them will make your text cursor jump into the
mapping column  to type in what you want to map it to.

Combinations involving Modifiers might not work. Configuring a combination
of two keys to output a single key will require you to push down the first
key, which of course ends up injecting that first key. Then the second key
will trigger the mapping, because the combination is complete. This is
not a bug. Otherwise every combination would have to automatically disable
all keys that are involved in it.

For example a combination of `LEFTSHIFT + a` for `b` would write "B" instead,
because shift will be activated before you hit the "a". Therefore the
environment will see shift and a "b", which will then be capitalized.

Consider using a different key for the combination than shift. You could use
`KP1 + a` and map `KP1` to `disable`.

The second option is to release the modifier in your combination by writing
the modifier one more time. This will write lowercase "b" characters. To make
this work shift has to be injected via key-mappers devices though, which just
means it has to be forwarded. So the complete mapping for this would look like:

- `Shift L + a` -> `key(Shift_L).hold(b)`
- `Shift L` -> `Shift_L`

## Writing Combinations

You can write `Control_L + a` as mapping, which will inject those two
keycodes into your system on a single key press. An arbitrary number of
names can be chained using ` + `.

<p align="center">
  <img src="plus.png"/>
</p>

## UI Shortcuts

- `ctrl` + `del` stops the injection (only works while the gui is in focus)
- `ctrl` + `q` closes the application
- `ctrl` + `r` refreshes the device list

## Key Names

Check the autocompletion of the GUI for possible values. You can also
obtain a complete list of possiblities using `input-remapper-control --symbol-names`.

Input-remapper only recognizes symbol names, but not the symbols themselfes. So for
example, input-remapper might (depending on the system layout) know what a `minus` is, but
it doesn't know `-`.

Key names that start with `KEY_` are keyboard layout independent constants that might
not result in the expected output. For example using `KEY_Y` would  result in "z"
if the layout of the environment is set to german. Using `y` on the other hand would
correctly result in "y" to be written.

## Limitations

**If your fingers can't type it on your keyboard, input-remapper can't inject it.**

The available symbols depend on the environments keyboard layout, and only those that
don't require a combination to be pressed can be used without workarounds (so most
special characters need some extra steps to use them). Furthermore, if your configured
keyboard layout doesn't support the special character at all (not even via a
combination), then it also won't be possible for input-remapper to map that character at
all.

For example, mapping a key to an exclamation mark is not possible if the keyboard
layout is set to german. However, it is possible to mimic the combination that would
be required to write it, by writing `Shift_L + 1` into the mapping.

This is because input-remapper creates a new virtual keyboard and injects numeric keycodes,
and it won't be able to inject anything a usb keyboard wouldn't been able to. This has
the benefit of being compatible to all display servers, but means the environment will
ultimately decide which character to write.

<br/>
<br/>
<br/>
<br/>
<br/>
<br/>

# Advanced

## Configuration Files

If you don't have a graphical user interface, you'll need to edit the
configuration files.

The default configuration is stored at `~/.config/input-remapper/config.json`,
which doesn't include any mappings, but rather other parameters that
are interesting for injections. The current default configuration as of 1.2.1
looks like, with  an example autoload entry:

```json
{
    "autoload": {
        "Logitech USB Keyboard": "preset name"
    },
    "macros": {
        "keystroke_sleep_ms": 10
    },
    "gamepad": {
        "joystick": {
            "non_linearity": 4,
            "pointer_speed": 80,
            "left_purpose": "none",
            "right_purpose": "none",
            "x_scroll_speed": 2,
            "y_scroll_speed": 0.5
        }
    }
}
```

`preset name` refers to `~/.config/input-remapper/presets/device name/preset name.json`.
The device name can be found with `sudo input-remapper-control --list-devices`.

Anything that is relevant to presets can be overwritten in them as well.
Here is an example configuration for preset "a" for the "gamepad" device:
`~/.config/input-remapper/presets/gamepad/a.json`

```json
{
    "macros": {
        "keystroke_sleep_ms": 100
    },
    "mapping": {
        "1,315,1+1,16,-1": "1",
        "1,307,1": "k(2).k(3)"
    }
}
```

Both need to be valid json files, otherwise the parser refuses to work. This
preset maps the EV_KEY down event with code 307 to a macro and sets the time
between injected events of macros to 100 ms. Note that a complete keystroke
consists of two events: down and up. The other mapping is a key combination,
chained using `+`.

Other than that, it inherits all configurations from
`~/.config/input-remapper/config.json`. If config.json is missing some stuff,
it will query the hardcoded default values.

The event codes can be read using `evtest`. Available names in the mapping
can be listed with `input-remapper-control --symbol-names`.

## CLI

**input-remapper-control**

`--command` requires the service to be running. You can start it via
`systemctl start input-remapper` or `sudo input-remapper-service` if it isn't already
running (or without sudo if your user has the appropriate permissions).

Examples:

| Description                                                                                         | Command                                                                               |
|-----------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------|
| Load all configured presets for all devices                                                         | `input-remapper-control --command autoload`                                               |
| If you are running as root user, provide information about the whereabouts of the input-remapper config | `input-remapper-control --command autoload --config-dir "~/.config/input-remapper/"`          |
| List available device names for the `--device` parameter                                            | `sudo input-remapper-control --list-devices`                                              |
| Stop injecting                                                                                      | `input-remapper-control --command stop --device "Razer Razer Naga Trinity"`               |
| Load `~/.config/input-remapper/presets/Razer Razer Naga Trinity/a.json`                                 | `input-remapper-control --command start --device "Razer Razer Naga Trinity" --preset "a"` |
| Loads the configured preset for whatever device is using this /dev path                             | `/bin/input-remapper-control --command autoload --device /dev/input/event5`               |

**systemctl**

Stopping the service will stop all ongoing injections

```bash
sudo systemctl stop input-remapper
sudo systemctl start input-remapper
systemctl status input-remapper
```

## Testing your Installation

The following commands can be used to make sure it works:

```bash
sudo input-remapper-service &
input-remapper-control --command hello
```

should print `Daemon answered with "hello"`. And

```bash
sudo input-remapper-control --list-devices
```

should print `Found "...", ...`. If anything looks wrong, feel free to [create
an issue](https://github.com/sezanzeb/input-remapper/issues/new).
