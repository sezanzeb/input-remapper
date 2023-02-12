#!/usr/bin/env bash

echo "disabling service"
sudo systemctl stop    input-remapper.service 2> /dev/null
sudo systemctl disable input-remapper.service 2> /dev/null

echo "uninstalling package"
pip      uninstall -q -y input-remapper 2> /dev/null
sudo pip uninstall -q -y input-remapper 2> /dev/null

echo "cleaning up binaries"
sudo rm -rf /usr/bin/input-remapper-gtk
sudo rm -rf /usr/bin/input-remapper-service
sudo rm -rf /usr/bin/input-remapper-reader-service
sudo rm -rf /usr/bin/input-remapper-control

echo "cleaning up share"
sudo rm -rf /usr/share/input-remapper
sudo rm -rf /usr/share/applications/input-remapper-gtk.desktop
sudo rm -rf /usr/lib/systemd/system/input-remapper.service

echo "cleaning up config and startup files"
sudo rm -rf /etc/dbus-1/system.d/inputremapper.Control.conf 
sudo rm -rf /etc/xdg/autostart/input-remapper-autoload.desktop 
sudo rm -rf /usr/lib/udev/rules.d/99-input-remapper.rules     

echo "checking for remaining files"
files="$((
    find /usr         -name 'input*remapper'
    find /etc         -name 'input*remapper'
    find $HOME/.local -name 'input*remapper'
) 2> /dev/null)" 

if test -n "$files"; then
    echo -e "files remaining:\n$files"
    echo "uninstall incomplete"
    exit 1
fi

echo "uninstall finished"
