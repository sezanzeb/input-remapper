#!/usr/bin/env bash

build_deb() {
  # https://www.devdungeon.com/content/debian-package-tutorial-dpkgdeb
  # that was really easy actually
  rm build dist -r
  mkdir build/deb -p
  python3 setup.py install --root=build/deb
  cp ./DEBIAN build/deb/ -r
  mkdir dist -p
  dpkg -b build/deb dist/key-mapper-0.4.1.deb
}

build_deb &
# add more build targets here

wait
