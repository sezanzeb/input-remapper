# Usage

To open the UI to modify the mappings, look into your applications menu
and search for 'Input Remapper'. You should be prompted for your sudo password
as special permissions are needed to read events from `/dev/input/` files.
You can also start it via `input-remapper-gtk`.

<p align="center">
  <img src="usage_1.png"/>
  <img src="usage_2.png"/>
</p>

First, select your device (like your keyboard) on the first page, then create a new
preset on the second page, and add a mapping. Then you can already edit your inputs,
as shown in the screenshots.

In the text input field, type the key to which you would like to map this key.
More information about the possible mappings can be found in [examples.md](./examples.md) and [below](#key-names).

Changes are saved automatically. 
Press the "Apply" button to activate (inject) the mapping you created.

If you later want to modify the Input of your mapping you need to use the 
"Stop" button, so that the application can read your original input. 
It would otherwise be invisible since the daemon maps it independently of the GUI.

## Troubleshooting

If stuff doesn't work, check the output of `input-remapper-gtk -d` and feel free
to [open up an issue here](https://github.com/sezanzeb/input-remapper/issues/new).
Make sure to not post any debug logs that were generated while you entered
private information with your device. Debug logs are quite verbose.

If input-remapper or your presets prevents your input device from working
at all due to autoload, please try to unplug and plug it in twice.
No injection should be running anymore.

## Combinations

You can use combinations of different inputs to trigger a mapping: While you recorde
the input (`Recorde Input` - Button) press multiple keys and/or move axis at once.
The mapping will be triggered as soon as all the recorded inputs are pressed.

If you use an axis an input you can modify the threshold at which the mapping is 
activated in the advanced input configuration, which can be opened by clicking on the
`Advanced` button.

A mapping with an input combination is only injected once all combination keys 
are pressed. This means all the input keys you press before the combination is complete 
will be injected unmodified. In some cases this can be desirable, in others not. 
In the advanced input configuration there is the `Release Input` toggle. 
This will release all inputs which are part of the combination before the mapping is 
injected. Consider a mapping `Shift+1 -> a` this will inject a lowercase `a` if the 
toggle is on and an uppercase `A` if it is off. The exact behaviour if the toggle is off 
is dependent on keys (are modifiers involved?), the order in which they are pressed and 
on your environment (X11/Wayland). By default the toggle is on.

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

Input-remapper only recognizes symbol names, but not the symbols themselves. So for
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

## Analog Axis

It is possible to map analog inputs to analog outputs. E.g. use a gamepad as a mouse.
For this you need to create a mapping and recorde the input axis. Then click on 
`Advanced` and select `Use as Analog`. Make sure to select a target 
which supports analog axis and switch to the `Analog Axis` tab. 
There you can select an output axis and use the different sliders to configure the 
sensitivity, non-linearity and other parameters as you like. 

It is also possible to use an analog output with an input combination. 
This will result in the analog axis to be only injected if the combination is pressed 

# External tools

Repositories listed here are made by input-remappers users. Feel free to extend. Beware,
that I can't review their code, so use them at your own risk (just like everything).

- input-remapper-xautopresets: https://github.com/DreadPirateLynx/input-remapper-xautopresets

# Advanced

## Configuration Files

If you don't have a graphical user interface, you'll need to edit the
configuration files. All configuration files need to be valid json files, otherwise the 
parser refuses to work.

Note for the Beta branch: All configuration files are copied to: 
`~/.config/input-remapper/beta_VERSION/`

The default configuration is stored at `~/.config/input-remapper/config.json`,
which doesn't include any mappings, but rather other parameters that
are interesting for injections. The current default configuration as of 1.6
looks like, with  an example autoload entry:

```json
{
  "autoload": {
      "Logitech USB Keyboard": "preset name"
    },
  "version": "1.6"
}
```

`preset name` refers to `~/.config/input-remapper/presets/device name/preset name.json`.
The device name can be found with `sudo input-remapper-control --list-devices`.

#### Preset

The preset files are a collection of mappings.
Here is an example configuration for preset "a" for the "gamepad" device:
`~/.config/input-remapper/presets/gamepad/a.json`

```json
{
    "1,307,1": {
        "target_uinput": "keyboard",
        "output_symbol": "k(2).k(3)",
        "macro_key_sleep_ms": 100
    },
    "1,315,1+1,16,1": {
        "target_uinput": "keyboard",
        "output_symbol": "1"
    },
    "3,1,0": {
        "target_uinput": "mouse",
        "output_type": 2,
        "output_code": 1,
        "gain": 0.5
    }
}
```
This preset consists of three mappings.

 * The first maps the key event with code 307 to a macro and sets the time between 
   injected events of macros to 100 ms. The macro injects its events to the virtual keyboard.
 * The second mapping is a key combination, chained using `+`.
 * The third maps the y-Axis to the y-Axis on the virtual mouse.

#### Mapping

As shown above, the mapping is part of the preset. It consists of the input-combination 
and the mapping parameters.

```
<input-combination>: {
    <parameter 1>: <value1>,
    <parameter 2>: <value2>
}
```
The input-combination is a string like `"EV_TYPE, EV_CODE, EV_VALUE + ..."`.
`EV_TYPE` and `EV_CODE` describe the input event. Use the program `evtest` to find 
Available types and codes. See also the [evdev documentation](https://www.kernel.org/doc/html/latest/input/event-codes.html#input-event-codes)

The `EV_VALUE` describes the intention of the input. 
A value of `0` means that the event will be mapped to an axis. A non-zero value means 
that the event will be treated as a key input. 

If the event type is `3 (EV_ABS)` (as in: map a joystick axis to a key or macro) the 
value can be between `-100 [%]` and `100 [%]`. The mapping will be triggered once the joystick 
reaches the position described by the value. 

If the event type is `2 (EV_REL)` (as in: map a relative axis (e.g. mouse wheel) to a key or macro)
the value can be anything. The mapping will be triggered once the speed and direction of 
the axis is higher than described by the value.

The following table contains all possible parameters and their default values:

| Parameter                   | Default | Type            | Description                                                                                                 |
|-----------------------------|---------|-----------------|-------------------------------------------------------------------------------------------------------------|
| target_uinput               |         | string          | The UInput to which the mapped event will be sent                                                           |
| output_symbol               |         | string          | The symbol or macro string if applicable                                                                    |
| output_type                 |         | int             | The event type of the mapped event                                                                          |
| output_code                 |         | int             | The event code of the mapped event                                                                          |
| release_combination_keys    | true    | bool            | If release events will be sent to the forwarded device as soon as a combination triggers see also #229      |
| **Macro settings**          |
| macro_key_sleep_ms          | 20      | positive int    |                                                                                                             |
| **Axis settings**           |                         
| deadzone                    | 0.1     | float ∈ (0, 1)  | The deadzone of the input axis                                                                              |
| gain                        | 1.0     | float           | Scale factor when mapping an axis to an axis                                                                |
| expo                        | 0       | float ∈ (-1, 1) | Non liniarity factor see also [GeoGebra](https://www.geogebra.org/calculator/mkdqueky)                      |
| **EV_REL output**           |            
| rel_xy_rate                 | 60      | positive int    | The frequency `[Hz]` at which `REL_X` amd `REL_Y` events get generated (also effects mouse macro)           |
| rel_wheel_rate              | 60      | positive int    | The frequency `[Hz]` at which `REL_WHEEL` and `REL_HWHEEL` events get generated (also effects wheel macro)  |
| rel_xy_speed                | 50      | positive int    | The base speed of the relative axis, compounds with the gain (also effects mouse and wheel macro)           |
| rel_wheel_speed             | 5       | positive int    | The base speed of the relative axis, compounds with the gain (also effects mouse and wheel macro)           |
| rel_hi_res_wheel_speed      | 5       | positive int    | The base speed of the relative axis, compounds with the gain (also effects mouse and wheel macro)           |
| **EV_REL as input**         |         
| rel_xy_max_input            | 90      | positive int    | The absolute value at which `REL_X` and `REL_Y` input (mouse cursor movement) is considered at its maximum  |
| rel_wheel_max_input         | 3       | positive int    | The absolute value at which a `REL_WHEEL` and `REL_HWHEEL` input is considered at its maximum               |
| rel_hi_res_wheel_max_input  | 360     | positive int    | The absolute value at which a `REL_WHEEL_HI_RES` and `REL_HWHEEL_HI_RES` input is considered at its maximum |
| release_timeout             | 0.05    | positive float  | The time `[s]` until a relative axis is considered stationary if no new events arrive                       |


## CLI

**input-remapper-control**

`--command` requires the service to be running. You can start it via
`systemctl start input-remapper` or `sudo input-remapper-service` if it isn't already
running (or without sudo if your user has the appropriate permissions).

Examples:

| Description                                                                                              | Command                                                                                    |
|----------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------|
| Load all configured presets for all devices                                                              | `input-remapper-control --command autoload`                                                |
| If you are running as root user, provide information about the whereabouts of the input-remapper config  | `input-remapper-control --command autoload --config-dir "~/.config/input-remapper/"`       |
| List available device names for the `--device` parameter                                                 | `sudo input-remapper-control --list-devices`                                               |
| Stop injecting                                                                                           | `input-remapper-control --command stop --device "Razer Razer Naga Trinity"`                |
| Load `~/.config/input-remapper/presets/Razer Razer Naga Trinity/a.json`                                  | `input-remapper-control --command start --device "Razer Razer Naga Trinity" --preset "a"`  |
| Loads the configured preset for whatever device is using this /dev path                                  | `/bin/input-remapper-control --command autoload --device /dev/input/event5`                |

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
