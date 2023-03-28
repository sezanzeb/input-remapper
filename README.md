<p align="center"><img src="data/input-remapper.svg" width=100/></p>

<h1 align="center">Input Remapper</h1>

<p align="center">
  An easy to use tool to change the behaviour of your input devices.<br/>
  Supports X11, Wayland, key combinations, programmable macros, joysticks, wheels,<br/>
  triggers, keys, mouse-movements and much more. Maps any input to any other input.
</p>

<p align="center"><a href="readme/usage.md">Usage</a> - <a href="readme/macros.md">Macros</a> - <a href="#installation">Installation</a> - <a href="readme/development.md">Development</a> - <a href="readme/examples.md">Examples</a></p>

<p align="center"><img src="readme/pylint.svg"/> <img src="readme/coverage.svg"/></p>


<p align="center">
  <img src="readme/screenshot.png" width="48%"/>
  &#160;
  <img src="readme/screenshot_2.png" width="48%"/>
</p>

## Installation

Below are instructions for certain distributions.  Contributions are
welcomed for missing distributions.

Distributions may lag with the latest bug fixes.  For some users, it may
be desirable to install the latest version using the `Manual` method below.

##### Manjaro/Arch

```bash
yay -S input-remapper-git
sudo systemctl restart input-remapper
sudo systemctl enable input-remapper
```

Please note that the above version may lag from the latest version.  See
the `manual` method below to install the latest version.

##### Ubuntu/Debian

Get a `.deb` file from the [release
page](https://github.com/sezanzeb/input-remapper/releases) and manually
install it.

The above version may not have the latest bug fixes.  Use the following
method to get the latest version:

```bash
sudo apt install git python3-setuptools gettext
git clone https://github.com/sezanzeb/input-remapper.git
cd input-remapper && ./scripts/build.sh
sudo apt install -f ./dist/input-remapper-2.0.0.deb
```

input-remapper is also available on [Debian](https://tracker.debian.org/pkg/input-remapper)
and [Ubuntu](https://packages.ubuntu.com/jammy/input-remapper)
distributions.  Please note that these versions may lag from the latest
version.

##### Manual installation

The following dependencies are required:

- `python3-evdev` ≥1.3.0
- `gtksourceview4`
- `python3-devel`
- `python3-pydantic`
- `python3-pydbus`

> Python packages need to be installed globally for the service to be able
> to import them.  Don't use `--user`.

`Conda` can cause problems due to changed python paths and versions.

###### Install method #1

```bash
sudo pip install evdev -U  # If newest version not in distros repo
sudo pip uninstall key-mapper  # In case the old package is still installed
sudo pip install --no-binary :all: git+https://github.com/sezanzeb/input-remapper.git
sudo systemctl enable input-remapper
sudo systemctl restart input-remapper
```

###### Install method #2

Use this installation method if the above method is problematic:

```bash
# Obtain the software:
mkdir -p ~/src
cd ~/src
git clone https://github.com/sezanzeb/input-remapper.git

# Install
cd ~/src/input-remapper
sudo python3 setup.py install
```

## Migrating beta configs to version 2

By default, input-remapper will not migrate configurations from the beta
release.

To manually migrate beta configurations, *before* starting
input-remapper, perform the following:

```bash
# Ignore whether the subdirectory exists ...
rm -fr ~/.config/input-remapper-2
cp -r ~/.config/input-remapper/beta_1.6.0-beta ~/.config/input-remapper-2
```

Once done, start input-remapper.

> **Warning:**  the above will remove any existing **new** configurations.
