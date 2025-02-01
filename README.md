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

### Ubuntu/Debian

Either download an installable .deb file from the [latest release](https://github.com/sezanzeb/input-remapper/releases):

```bash
wget https://github.com/sezanzeb/input-remapper/releases/download/2.1.0/input-remapper-2.1.0.deb
sudo apt install -f ./input-remapper-2.1.0.deb
```

Or install the very latest changes via:

```bash
sudo apt install git python3-setuptools gettext
git clone https://github.com/sezanzeb/input-remapper.git
cd input-remapper
./scripts/build.sh
sudo apt remove input-remapper input-remapper-daemon input-remapper-gtk python3-inputremapper --purge
sudo apt install -f ./dist/input-remapper-2.1.0.deb
```

Input Remapper is also available in the repositories of [Debian](https://tracker.debian.org/pkg/input-remapper)
and [Ubuntu](https://packages.ubuntu.com/oracular/input-remapper) via

```bash
sudo apt install input-remapper
```

Input Remapper ≥ 2.0 requires at least Ubuntu 22.04.

<br/>

### Fedora

```bash
sudo dnf install input-remapper
sudo systemctl enable --now input-remapper
```

<br/>

### Manjaro/Arch

```bash
yay -S input-remapper-git
sudo systemctl enable --now input-remapper
```

<br/>

### Other Distros

Figure out the packages providing those dependencies in your distro, and install them:
`python3-evdev` ≥1.3.0, `gtksourceview4`, `python3-devel`, `python3-pydantic`,
`python3-pydbus`, `python3-psutil`

You can also use pip to install some of them. Python packages need to be installed
globally for the service to be able to import them. Don't use `--user`. Conda and such
may also cause problems due to changed python paths and versions.

```bash
sudo pip install evdev pydantic pydbus PyGObject setuptools
```

```bash
git clone https://github.com/sezanzeb/input-remapper.git
cd input-remapper
sudo python3 setup.py install
sudo systemctl enable --now input-remapper
```
