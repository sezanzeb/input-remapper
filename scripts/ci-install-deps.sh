#!/usr/bin/env bash
# Called from multiple CI pipelines in .github/workflows
set -xeuo pipefail

# native deps
# gettext required to generate translations
sudo apt-get install -y gettext

# ensure pip and setuptools/wheel up to date so can install all pip modules
python -m pip install --upgrade pip
pip install wheel setuptools

# install input-remapper's deps from setup.py
python setup.py egg_info
pip install `grep -v '^\[' *.egg-info/requires.txt`

# install test deps which aren't in setup.py
pip install psutil
