#!/usr/bin/env bash

# build the .deb and .appimage files
# https://ubuntuforums.org/showthread.php?t=1002909
dist=deb
name=key-mapper-0.1.0

python3 setup.py sdist --dist-dir deb
tar -C deb -xzf $dist/$name.tar.gz
cp $dist/DEBIAN $dist/$name -r
dpkg-deb -b $dist/$name $name.deb
rm $dist/$name -r

