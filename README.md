<p align="center"><img src="data/input-remapper.svg" width=100/></p>

<h1 align="center">Input Remapper</h1>

<p align="center"><b>Formerly Key Mapper</b></p>

<p align="center">
  An easy to use tool to change the mapping of your input device buttons.<br/>
  Supports mice, keyboards, gamepads, X11, Wayland, combined buttons and programmable macros.<br/>
  Allows mapping non-keyboard events (click, joystick, wheel) to keys of keyboard devices.
</p>

<p align="center"><a href="readme/usage.md">Usage</a> - <a href="readme/macros.md">Macros</a> - <a href="#installation">Installation</a> - <a href="readme/development.md">Development</a> - <a href="#screenshots">Screenshots</a> - <a href="readme/examples.md">Examples</a></p>

<p align="center"><img src="readme/pylint.svg"/> <img src="readme/coverage.svg"/></p>

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
sudo apt install ./dist/input-remapper-1.2.2.deb
```

input-remapper is now part of [Debian Unstable](https://packages.debian.org/sid/input-remapper)

##### pip

```bash
sudo pip install --no-binary :all: git+https://github.com/sezanzeb/input-remapper.git
sudo systemctl enable input-remapper
sudo systemctl restart input-remapper
```

If it doesn't seem to install, you can also try `sudo python3 setup.py install`

## Screenshots

<p align="center">
  <img src="readme/screenshot.png"/>
</p>

<p align="center">
  <img src="readme/screenshot_2.png"/>
</p>
