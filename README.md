<p align="center"><img src="data/key-mapper.svg" width=100/></p>

<h1 align="center">Key Mapper</h1>

<p align="center">
  A tool to change the mapping of your input device buttons.<br/>
  Supports mice, keyboards, gamepads, X11, Wayland and programmable macros.
</p>

<p align="center"><a href="readme/usage.md">Usage</a> - <a href="#installation">Installation</a> - <a href="readme/development.md">Development</a> - <a href="#screenshots">Screenshots</a></p>

<p align="center"><img src="readme/pylint.svg"/> <img src="readme/coverage.svg"/></p>

## Installation

##### Manjaro/Arch

```bash
pacaur -S key-mapper-git
```

##### Ubuntu/Debian

```bash
sudo apt install git python3-setuptools
git clone https://github.com/sezanzeb/key-mapper.git
cd key-mapper && ./scripts/build.sh
sudo dpkg -i ./dist/key-mapper-0.4.0.deb
sudo apt -f install
```

##### pip

Depending on your distro, maybe you need to use `--force` to get all your
files properly in place and overwrite a previous installation of key-mapper.
There are two options available to install using setuptools/pip:

```bash
sudo pip install git+https://github.com/sezanzeb/key-mapper.git
```

```bash
git clone https://github.com/sezanzeb/key-mapper.git
cd key-mapper && sudo python3 setup.py install
```

## Screenshots

<p align="center">
  <img src="readme/screenshot.png"/>
</p>

<p align="center">
  <img src="readme/screenshot_2.png"/>
</p>
