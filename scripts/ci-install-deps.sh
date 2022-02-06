#!/usr/bin/env bash
# Called from multiple CI pipelines in .github/workflows
set -xeuo pipefail

# native deps
# FIXME: this is a lot and most aren't actually used in testing but tests will crash without due to GtkSource require
# this takes a while to run in CI
sudo apt-get install -y libgirepository1.0-dev gettext python3-gi gobject-introspection \
  gir1.2-gtk-3.0 gir1.2-gtksource-4 libgtksourceview-4-0 libgtksourceview-4-dev

# ensure pip and setuptools/wheel up to date so can install all pip modules
python -m pip install --upgrade pip
pip install wheel setuptools

# install input-remapper's deps from setup.py
python setup.py egg_info
pip install `grep -v '^\[' *.egg-info/requires.txt`

# install test deps which aren't in setup.py
pip install psutil
