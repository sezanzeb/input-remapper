<p align="center"><img src="data/key-mapper.svg" width=100/></p>

<h1 align="center">Key Mapper</h1>

<p align="center">
  A tool to change the mapping of your input device buttons.<br/>
  Supports mice, keyboards, gamepads, X11, Wayland and programmable macros.
</p>

<p align="center"><a href="readme/usage.md">Usage</a> - <a href="#installation">Installation</a> - <a href="readme/development.md">Development</a> - <a href="#screenshots">Screenshots</a></p>

<p align="center"><img src="readme/pylint.svg"/> <img src="readme/coverage.svg"/></p>

## Installation

The tool shows and logs if there are issues, but usually, independent of the
method, you should add yourself to the `input` and `plugdev` groups so that
you can read information from your devices. You have to start the application
via sudo otherwise. You may also need to grant yourself write access to
`/dev/uinput` to be able to inject your programmed mapping.

There is a shortcut for configuring this stuff:

```bash
sudo key-mapper-service --setup-permissions
```

Now log out and back in (or restart in some cases).

##### Manjaro/Arch

```bash
pacaur -S key-mapper-git
```

##### Ubuntu/Debian

```bash
wget "https://github.com/sezanzeb/key-mapper/releases/"\
"download/0.3.1/python3-key-mapper_0.3.1-1_all.deb"
sudo dpkg -i python3-key-mapper_0.3.1-1_all.deb
```

##### Git/pip

Depending on your distro, maybe you need to use `--force` to get all your
files properly in place and overwrite a previous installation of key-mapper.

```bash
# method 1
sudo pip install git+https://github.com/sezanzeb/key-mapper.git
# method 2
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
