#!/usr/bin/env bash

# build the .deb and .appimage files
# https://ubuntuforums.org/showthread.php?t=1002909

python3 setup.py sdist --dist-dir deb
tar -C deb -xzf dist/key-mapper-0.1.0.tar.gz
cp deb/DEBIAN deb/key-mapper-0.1.0 -r
dpkg-deb -b deb/key-mapper-0.1.0/ key-mapper-0.1.0.deb
rm deb/key-mapper-0.1.0 -r

