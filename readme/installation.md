# Installation

Below are installation instructions for certain distributions.  If your
distribution is not included, use the <a
href="#manual-installation">Manual installation</a> instructions.

We welcome contributors to maintain missing distributions.

Please note that the distribution package may lag with the latest bug
fixes.  Use the <a href="#manual-installation">Manual installation</a>
method to get the latest bug fixes.

## Manjaro/Arch

```bash
yay -S input-remapper-git
sudo systemctl restart input-remapper
sudo systemctl enable input-remapper
```

## Ubuntu/Debian
Get the latest version:

```bash
sudo apt install git python3-setuptools gettext
git clone https://github.com/sezanzeb/input-remapper.git
cd input-remapper && ./scripts/build.sh
sudo apt install -f ./dist/input-remapper-2.0.0.deb
```

Or alternatively, use one of the following methods.

### Install using a .deb file

1. Download the `.deb` file from the
[release page](https://github.com/sezanzeb/input-remapper/releases)
2. and install it manually:
```bash
sudo apt install -f /path/to/input-remapper-2.0.0.deb
```

### Distribution repository

input-remapper is available on [Debian](https://tracker.debian.org/pkg/input-remapper)
and [Ubuntu](https://packages.ubuntu.com/jammy/input-remapper)
distributions.  Use your package manager to install the software:

```bash
sudo apt update && sudo apt install input-remapper
```

## Manual installation

Ensure that the following dependencies are met:

- `python3-evdev` ≥1.3.0
- `gtksourceview4`
- `python3-devel`
- `python3-pydantic`
- `python3-pydbus`

Python packages need to be installed globally for the service to be able
to import them.  Do not use `--user`.

There are known issues (see #523) with `Conda`.  If you encounter
`MonduleNotFoundError`, uninstall/disable `Conda`.

### Install method #1

```bash
sudo pip install evdev -U  # If newest version not in distros repo
sudo pip uninstall key-mapper  # In case the old package is still installed
sudo pip install --no-binary :all: git+https://github.com/sezanzeb/input-remapper.git
sudo systemctl enable input-remapper
sudo systemctl restart input-remapper
```

### Install method #2

Use this installation method if the above method is problematic:

```bash
git clone https://github.com/sezanzeb/input-remapper.git
cd input-remapper
./scripts/setup.sh install
```

# Migrating beta configs to version 2

<i><b>Warning:</b>  the following will remove any existing <b>new</b>
configurations.</i>

By default, input-remapper will not migrate configurations from the beta
release.

To manually migrate beta configurations, *before* creating any
configurations, perform the following:

```bash
# Ignore whether the subdirectory exists ...
rm -fr ~/.config/input-remapper-2
cp -r ~/.config/input-remapper/beta_1.6.0-beta ~/.config/input-remapper-2
```

Once completed, start input-remapper.
