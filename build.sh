#!/usr/bin/env bash

# build the .deb and .appimage files
# https://ubuntuforums.org/showthread.php?t=1002909

python3 setup.py sdist
cd dist
tar -xzf key-mapper-0.1.0.tar.gz
cd key-mapper-0.1.0
