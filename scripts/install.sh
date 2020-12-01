#!/usr/bin/env bash

# in case setup.py does nothing instead of something.
# call via `./scripts/build.sh`

# try both ways of installation
sudo pip3 install .
sudo python3 setup.py install

# copy crucial files
sudo cp bin/* /usr/bin/ -r
sudo mkdir /usr/share/key-mapper
sudo cp data/* /usr/share/key-mapper -r
