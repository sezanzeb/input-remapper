<p align="center"><img src="data/input-remapper.svg" width=100/></p>

<h1 align="center">Input Remapper</h1>

<p align="center">
  An easy to use tool for Linux to change the behaviour of your input devices.<br/>
  Supports X11, Wayland, combinations, programmable macros, joysticks, wheels,<br/>
  triggers, keys, mouse-movements and more. Maps any input to any other input.
</p>

<p align="center"><a href="readme/usage.md">Usage</a> - <a href="readme/macros.md">Macros</a> - <a href="#installation">Installation</a> - <a href="readme/development.md">Development</a> - <a href="readme/examples.md">Examples</a></p>

<p align="center"><img src="readme/pylint.svg"/> <img src="readme/coverage.svg"/></p>


<p align="center">
  <img src="readme/screenshot.png" width="48%"/>
  &#160;
  <img src="readme/screenshot_2.png" width="48%"/>
</p>

<br/>

## Installation

#### Ubuntu/Debian

Get a .deb file from the [release page](https://github.com/sezanzeb/input-remapper/releases) and install it with `sudo apt install -f ./input-remapper-2.0.1.deb`

Or install the latest changes via:

```bash
sudo apt install git python3-setuptools gettext
git clone https://github.com/sezanzeb/input-remapper.git
cd input-remapper && ./scripts/build.sh
sudo apt install -f ./dist/input-remapper-2.0.1.deb
```

input-remapper is also available in the Repositories of [Debian](https://tracker.debian.org/pkg/input-remapper)
and [Ubuntu](https://packages.ubuntu.com/jammy/input-remapper) via `sudo apt install input-remapper`.

input-remapper ≥ 2.0 requires at least Ubuntu 22.04.

<br/>

#### Fedora

```bash
sudo dnf install input-remapper
sudo systemctl enable --now input-remapper
```

<br/>

#### Manjaro/Arch

```bash
yay -S input-remapper-git
sudo systemctl restart input-remapper
sudo systemctl enable input-remapper
```

<br/>

#### Manual

Dependencies: `python3-evdev` ≥1.3.0, `gtksourceview4`, `python3-devel`, `python3-pydantic`, `python3-pydbus`,
`python3-psutil`

Python packages need to be installed globally for the service to be able to import them. Don't use `--user`

Conda can cause problems due to changed python paths and versions.

If it doesn't seem to install, you can also try `sudo python3 setup.py install`

```bash
sudo pip install evdev -U  # If newest version not in distros repo
sudo pip uninstall key-mapper  # In case the old package is still installed
sudo pip install --no-binary :all: git+https://github.com/sezanzeb/input-remapper.git
sudo systemctl enable input-remapper
sudo systemctl restart input-remapper
```
