#!/usr/bin/env bash
# Called from multiple CI pipelines in .github/workflows
set -xeuo pipefail

# native deps
# gettext required to generate translations, others are python deps
sudo apt-get install -y gettext python3-evdev python3-pydbus python3-pydantic python3-gi gir1.2-gtk-3.0 gir1.2-gtksource-4

# ensure pip and setuptools/wheel up to date so can install all pip modules
python -m pip install --upgrade pip
python -m pip install --upgrade --force-reinstall wheel setuptools

# install test deps which aren't in setup.py
python -m pip install psutil pylint-pydantic dbus-next
