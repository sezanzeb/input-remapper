#!/usr/bin/env bash

build_deb() {
  # https://www.devdungeon.com/content/debian-package-tutorial-dpkgdeb
  # that was really easy actually
  rm build -r
  python3 -m building
  cp ./DEBIAN build/ -r
  dpkg-deb -Z gzip -b build dist/input-remapper-2.2.0.deb
}

build_deb &
# add more build targets here

wait
