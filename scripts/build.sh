#!/usr/bin/env bash

build_deb() {
  # https://github.com/phusion/debian-packaging-for-the-modern-developer/tree/master/tutorial-1
  # https://shallowsky.com/blog/programming/python-debian-packages-w-stdeb.html
  sudo apt install python3-stdeb fakeroot python3-all dh-python
  python3 setup.py --command-packages=stdeb.command bdist_deb
  echo "buid_deb done"
}

build_deb &
# add more build targets here

wait
