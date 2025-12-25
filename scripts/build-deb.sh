#!/usr/bin/env bash

build_deb() {
  # https://www.devdungeon.com/content/debian-package-tutorial-dpkgdeb
  # that was really easy actually
  rm build -r
  mkdir dist | true
  python3 -m install --root build/deb
  cp ./DEBIAN build/deb -r
  dpkg-deb -Z gzip -b build/deb dist/input-remapper-2.2.0.deb
}

build_deb
