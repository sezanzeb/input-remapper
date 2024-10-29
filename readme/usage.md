# Usage

Look into your applications menu and search for **Input Remapper** to open the UI. 
You should be prompted for your sudo password as special permissions are needed to read 
events from `/dev/input/` files. You can also start it via `input-remapper-gtk`.

First, select your device (like your keyboard) on the first page, then create a new
preset on the second page, and add a mapping. Then you can already edit your inputs,
as shown in the screenshots below.

<p align="center">
  <img src="usage_1.png"/>
  <img src="usage_2.png"/>
</p>

In the "Output" textbox on the right, type the key to which you would like to map this input.
More information about the possible mappings can be found in 
[examples.md](./examples.md) and [below](#key-names). You can also write your macro 
into the "Output" textbox. If you hit enter, it will switch to a multiline-editor with
line-numbers.

Changes are saved automatically. Press the "Apply" button to activate (inject) the 
mapping you created.

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

You can use combinations of different inputs to trigger a mapping: While you record
the input (`Record` - Button) press multiple keys and/or move axis at once.
The mapping will be triggered as soon as all the recorded inputs are pressed.

If you use an axis an input you can modify the threshold at which the mapping is 
activated in the advanced input configuration, which can be opened by clicking
on the `Advanced` button.

A mapping with an input combination is only injected once all combination keys 
are pressed. This means all the input keys you press before the combination is complete 
will be injected unmodified. In some cases this can be desirable, in others not.

*Option 1*: In the advanced input configuration there is the `Release Input` toggle. 
This will release all inputs which are part of the combination before the mapping is 
injected. Consider a mapping `Shift+1 -> a` this will inject a lowercase `a` if the 
toggle is on and an uppercase `A` if it is off. The exact behaviour if the toggle is off 
is dependent on keys (are modifiers involved?), the order in which they are pressed and 
on your environment (X11/Wayland). By default the toggle is on.

*Option 2*: Disable the keys that are part of the combination individually. So with
a mapping of `Super+1 -> a`, you could additionally map `Super` to `disable`. Now
`Super` won't do anything anymore, and therefore pressing the combination won't have
any side effects anymore.

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

It is also possible to map a key to `disable` to stop it from doing anything.

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
For this you need to create a mapping and record the input axis. Then click on 
`Advanced` and select `Use as Analog`. Make sure to select a target 
which supports analog axis and switch to the `Analog Axis` tab. 
There you can select an output axis and use the different sliders to configure the 
sensitivity, non-linearity and other parameters as you like. 

It is also possible to use an analog output with an input combination. 
This will result in the analog axis to be only injected if the combination is pressed 

## Wheels

When mapping wheels, you need to be aware that there are both `WHEEL` and `WHEEL_HI_RES`
events. This can cause your wheel to scroll, despite being mapped to something.
By fiddling around with the advanced settings when editing one of your inputs, you can
map the "Hi Res" inputs to `disable`.

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

### Preset

The preset files are a collection of mappings.
Here is an example configuration for preset "a" for the "gamepad" device:
`~/.config/input-remapper/presets/gamepad/a.json`

```json
[
    {
        "input_combination": [
            {"type": 1, "code": 307}
        ], 
        "target_uinput": "keyboard", 
        "output_symbol": "key(2).key(3)", 
        "macro_key_sleep_ms": 100
    }, 
    {
        "input_combination": [
            {"type": 1, "code": 315, "origin_hash": "07f543a6d19f00769e7300c2b1033b7a"}, 
            {"type": 3, "code": 1, "analog_threshold": 10}
        ], 
        "target_uinput": "keyboard", 
        "output_symbol": "1"
    }, 
    {
        "input_combination": [
            {"type": 3, "code": 1}
        ], 
        "target_uinput": "mouse", 
        "output_type": 2, 
        "output_code": 1, 
        "gain": 0.5
    }
]
```
This preset consists of three mappings.

 * The first maps the key event with code 307 to a macro and sets the time between 
   injected events of macros to 100 ms. The macro injects its events to the virtual keyboard.
 * The second mapping is a combination of a key event with the code 315 and a 
   analog input of the axis 1 (y-Axis).
 * The third maps the y-Axis of a joystick to the y-Axis on the virtual mouse.

### Mapping

As shown above, the mapping is part of the preset. It consists of the input-combination,
which is a list of input-configurations and the mapping parameters.

```
{
    "input_combination": [
	    <InputConfig 1>,
	    <InputConfig 2>
    ]
    <parameter 1>: <value1>,
    <parameter 2>: <value2>
}
```

#### Input Combination and Configuration
The input-combination is a list of one or more input configurations. To trigger a 
mapping, all input configurations must trigger.

A input configuration is a dictionary with some or all of the following parameters:

| Parameter        | Default | Type                   | Description                                                         |
|------------------|---------|------------------------|---------------------------------------------------------------------|
| type             | -       | int                    | Input Event Type                                                    |
| code             | -       | int                    | Input Evnet Code                                                    |
| origin_hash      | None    | hex (string formatted) | A unique identifier for the device which emits the described event. |
| analog_threshold | None    | int                    | The threshold above which a input axis triggers the mapping.        |

##### type, code
The `type` and `code` parameters are always needed. Use the program `evtest` to find 
Available types and codes. See also the [evdev documentation](https://www.kernel.org/doc/html/latest/input/event-codes.html#input-event-codes)
##### origin_hash
The origin_hash is an internally computed hash. It is used associate the input with a 
specific `/dev/input/eventXX` device. This is useful when a single pyhsical device 
creates multiple `/dev/input/eventXX` devices wihth similar capabilities.
See also: [Issue#435](https://github.com/sezanzeb/input-remapper/issues/435)

##### analog_threshold
Setting the `analog_threshold` to zero or omitting it means that the input will be 
mapped to an axis. There can only be one axis input with a threshold of 0 in a mapping. 
If the `type` is 1 (EV_KEY) the `analog_threshold` has no effect. 

The `analog_threshold` is needend when the input is a analog axis which should be 
treated as a key input. If the event type is `3 (EV_ABS)` (as in: map a joystick axis to
a key or macro) the threshold can be between `-100 [%]` and `100 [%]`. The mapping will 
be triggered once the joystick reaches the position described by the value. 

If the event type is `2 (EV_REL)` (as in: map a relative axis (e.g. mouse wheel) to a 
key or macro) the threshold can be anything. The mapping will be triggered once the 
speed and direction of the axis is higher than described by the threshold.

#### Mapping Parameters
The following table contains all possible parameters and their default values:

| Parameter                | Default | Type            | Description                                                                                                             |
|--------------------------|---------|-----------------|-------------------------------------------------------------------------------------------------------------------------|
| input_combination        |         | list            | see [above](#input-combination-and-configuration)                                                                       |
| target_uinput            |         | string          | The UInput to which the mapped event will be sent                                                                       |
| output_symbol            |         | string          | The symbol or macro string if applicable                                                                                |
| output_type              |         | int             | The event type of the mapped event                                                                                      |
| output_code              |         | int             | The event code of the mapped event                                                                                      |
| release_combination_keys | true    | bool            | If release events will be sent to the forwarded device as soon as a combination triggers see also #229                  |
| **Macro settings**       |         |                 |                                                                                                                         |
| macro_key_sleep_ms       | 0       | positive int    |                                                                                                                         |
| **Axis settings**        |         |                 |                                                                                                                         |
| deadzone                 | 0.1     | float ∈ (0, 1)  | The deadzone of the input axis                                                                                          |
| gain                     | 1.0     | float           | Scale factor when mapping an axis to an axis                                                                            |
| expo                     | 0       | float ∈ (-1, 1) | Non liniarity factor see also [GeoGebra](https://www.geogebra.org/calculator/mkdqueky)                                  |
| **EV_REL output**        |         |                 |                                                                                                                         |
| rel_rate                 | 60      | positive int    | The frequency `[Hz]` at which `EV_REL` events get generated (also effects mouse macro)                                  |
| **EV_REL as input**      |         |                 |                                                                                                                         |
| rel_to_abs_input_cutoff  | 2       | positive float  | The value relative to a predefined base-speed, at which `EV_REL` input (cursor and wheel) is considered at its maximum. |
| release_timeout          | 0.05    | positive float  | The time `[s]` until a relative axis is considered stationary if no new events arrive                                   |


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

## Migrating beta configs to version 2

By default, Input Remapper will not migrate configurations from the beta.
If you want to use those you will need to copy them manually.

```bash
rm ~/.config/input-remapper-2 -r
cp ~/.config/input-remapper/beta_1.6.0-beta ~/.config/input-remapper-2 -r
```

Then start input-remapper
