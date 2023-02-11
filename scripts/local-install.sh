#!/usr/bin/env bash
# Allows to install the app and services so that they use the local development
# modules. Includes support for modules installed in the USER's virtual env.

if test -n "$VIRTUAL_ENV"; then
    echo "running in virtual env '$VIRTUAL_ENV'"
    site_packages="$(find "$VIRTUAL_ENV" -name site-packages)"
    echo "temporarily ingesting site-packages path '$site_packages' into binaries"
    scripts/inject-path.sh inject "$site_packages"
fi

echo "stopping service"
sudo systemctl stop    input-remapper.service
sudo systemctl disable input-remapper.service

echo "installing local package"
sudo pip install -q .

if test -n "$VIRTUAL_ENV"; then
    echo "removing temporary site-packages path from binaries"
    scripts/inject-path.sh clean
fi

echo "updating applications database"
sudo update-desktop-database /usr/share/applications

echo "starting service"
sudo systemctl enable input-remapper.service
sudo systemctl start  input-remapper.service
input-remapper-control --command autoload
sudo systemctl status input-remapper.service | cat
