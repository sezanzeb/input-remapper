# Installation

Below are installation instructions for certain distributions as well as
<a href="#manual-installation">Manual installation</a> instructions.

We welcome contributors for missing distributions.

Please note that distributions may lag with the latest bug fixes.  For
some users, it may be desirable to install the latest version using the
<a href="#manual-installation">Manual installation</a> method.

## Manjaro/Arch

```bash
yay -S input-remapper-git
sudo systemctl restart input-remapper
sudo systemctl enable input-remapper
```

Please note that the above version may lag from the latest version.  See
the <a href="#manual-installation">Manual installation</a> method below to install the latest version.

## Ubuntu/Debian

To get the latest version, use the following method:

```bash
sudo apt install git python3-setuptools gettext
git clone https://github.com/sezanzeb/input-remapper.git
cd input-remapper && ./scripts/build.sh
sudo apt install -f ./dist/input-remapper-2.0.0.deb
```

If you prefer to use a `.deb` file instead, download it from the
[release page](https://github.com/sezanzeb/input-remapper/releases) and
manually install it.  Please be aware that this version may not have the
latest bug fixes.

Finally, input-remapper is also available on [Debian](https://tracker.debian.org/pkg/input-remapper)
and [Ubuntu](https://packages.ubuntu.com/jammy/input-remapper)
distributions.  As previously mentioned, these versions may lag from the
latest version.

## Manual installation

The following dependencies are required:

- `python3-evdev` ≥1.3.0
- `gtksourceview4`
- `python3-devel`
- `python3-pydantic`
- `python3-pydbus`

Python packages need to be installed globally for the service to be able
to import them.  Don't use `--user`.

`Conda` can cause problems due to changed python paths and versions.

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
# Obtain the software:
mkdir -p ~/src
cd ~/src
git clone https://github.com/sezanzeb/input-remapper.git

# Install
cd ~/src/input-remapper
sudo python3 setup.py install
```

# Migrating beta configs to version 2

**Warning:**  the following will remove any existing **new** configurations.

By default, input-remapper will not migrate configurations from the beta
release.

To manually migrate beta configurations, *before* creating any
configurations, perform the following:

```bash
# Ignore whether the subdirectory exists ...
rm -fr ~/.config/input-remapper-2
cp -r ~/.config/input-remapper/beta_1.6.0-beta ~/.config/input-remapper-2
```

Once done, start input-remapper.
