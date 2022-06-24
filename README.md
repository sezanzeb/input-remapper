<p align="center"><img src="data/input-remapper.svg" width=100/></p>

<h1 align="center">Input Remapper (Beta)</h1>

<p align="center"><b>Formerly Key Mapper</b></p>

<p align="center">
  An easy to use tool to change the mapping of your input device buttons.<br/>
  Supports mice, keyboards, gamepads, X11, Wayland, combined buttons and programmable macros.<br/>
  Allows mapping non-keyboard events (click, joystick, wheel) to keys of keyboard devices.
</p>

<p align="center"><a href="readme/usage.md">Usage</a> - <a href="readme/macros.md">Macros</a> - <a href="#installation">Installation</a> - <a href="readme/development.md">Development</a> - <a href="#screenshots">Screenshots</a> - <a href="readme/examples.md">Examples</a></p>

<p align="center"><img src="readme/pylint.svg"/> <img src="readme/coverage.svg"/></p>

#### Known Issues (Beta Branch)

 * The GUI is currently is not adapted to reflect all new features and might behave strange.
   Mapping a gamepad to mouse is currently not possible in the GUI. 
   Also mapping joystick or mouse axis to buttons might not work.
   Those are only limitations of the GUI, when editing the preset manually all those features are still available.

## Installation

##### Manjaro/Arch

```bash
pacaur -S input-remapper-git
```

##### Ubuntu/Debian

Get a .deb file from the [release page](https://github.com/sezanzeb/input-remapper/releases)
or install the latest changes via:

```bash
sudo apt install git python3-setuptools gettext
git clone https://github.com/sezanzeb/input-remapper.git
cd input-remapper && ./scripts/build.sh
sudo apt install ./dist/input-remapper-1.6.0-beta.deb
```

input-remapper is now part of [Debian Unstable](https://packages.debian.org/sid/input-remapper)
and of [Ubuntu](https://packages.ubuntu.com/jammy/input-remapper)

##### Manual

Dependencies: `python3-evdev` ≥1.3.0, `gtksourceview4`, `python3-devel`, `python3-pydantic`, `python3-pydbus`

Python packages need to be installed globally for the service to be able to import them. Don't use `--user`

```bash
sudo pip install evdev -U  # If newest version not in distros repo
sudo pip uninstall key-mapper  # In case the old package is still installed
sudo pip install --no-binary :all: git+https://github.com/sezanzeb/input-remapper.git
sudo systemctl enable input-remapper
sudo systemctl restart input-remapper
```

If it doesn't seem to install, you can also try `sudo python3 setup.py install`

##### Beta

The `beta` branch contains features that still require work, but that are ready for testing. It uses a different
config path, so your presets won't break. `input-remapper-beta-git` can be installed from the AUR. If you are
facing problems, please open up an [issue](https://github.com/sezanzeb/input-remapper/issues).

## Screenshots

<p align="center">
  <img src="readme/screenshot.png"/>
</p>

<p align="center">
  <img src="readme/screenshot_2.png"/>
</p>
