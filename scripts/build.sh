#!/usr/bin/env bash

pack_deb() {
  # https://www.devdungeon.com/content/debian-package-tutorial-dpkgdeb
  # that was really easy actually
  mkdir build/deb -p
  python3 setup.py install --root=build/deb
  mv build/deb/usr/local/lib/python3.*/ build/deb/usr/lib/python3/
  cp ./DEBIAN build/deb/ -r

  if [[ -f build/dist/key-mapper-0.6.0.deb ]]; then
      rm build/dist/key-mapper-0.6.0.deb
  fi
  mkdir dist -p
  dpkg -b build/deb dist/key-mapper-0.6.0.deb
}

pack_flatpak() {
  python3 setup.py install --root=build/flatpak
  flatpak-builder build/flatpak_idk org.flatpak.Hello.yml
}

pack_deb &
# add more build targets here

wait

