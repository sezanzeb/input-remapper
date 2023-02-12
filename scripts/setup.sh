#!/usr/bin/env bash
# Provides commands for installing and uninstalling input-remapper in the system.
# Supports using the system's `/usr/bin/python3` or the local `python3`.
# Provides commands for cleaning up everything.
# Supports installation of the modules in a virtual env.

here="$(dirname "$0")"
python=/usr/bin/python3

stop_service() {
    echo "disabling service"
    sudo systemctl stop    input-remapper.service 2> /dev/null
    sudo systemctl disable input-remapper.service 2> /dev/null
}

start_service() {
    echo "starting service"
    sudo systemctl enable  input-remapper.service
    sudo systemctl restart input-remapper.service
    input-remapper-control --command autoload
    sudo systemctl status input-remapper.service --no-pager -l
}

# install using the defined $python and record which file are installed
system_install() {
    echo "install: installing using '$python'"
    sudo $python setup.py install --record build/files.txt
    sudo chown "$USER:$USER" build build/files.txt
    echo "install: writing list of install dirs to 'build/dirs.txt'"
    grep -o '.*input[-_]*remapper.*/' build/files.txt | sort -r -u > build/dirs.txt
}

# use whatever python3 is currently used even in a virtual env
local_install() {
    if test -n "$VIRTUAL_ENV"; then
        echo "install: running in virtual env '$VIRTUAL_ENV'"
        site_packages="$(find "$VIRTUAL_ENV" -name site-packages)"
        echo "install: temporarily ingesting site-packages path '$site_packages' into binaries"
        "$here/inject-path.sh" inject "$site_packages"
    fi

    echo "install: using local python3"
    python=python3 system_install

    if test -n "$VIRTUAL_ENV"; then
        echo "install: removing temporary site-packages path from binaries"
        "$here/inject-path.sh" clean
    fi
}

# determine which files were installed an then remove them together with any empty target dirs
uninstall() {
    echo "uninstall: removing previously recorded installation files"
    if test -e build/files.txt -a -e build/dirs.txt; then
        echo "uninstall: removing files from build/files.txt"
        sudo xargs -I "FILE" rm -v -f "FILE" <build/files.txt
        echo "uninstall: removing empty dirs from build/dirs.txt"
        sudo xargs -I "FILE" rmdir --parents --ignore-fail-on-non-empty "FILE" <build/dirs.txt 2> /dev/null
        return 0
    else
        echo "uninstall: build/files.txt or build/dirs.txt not found, please reinstall using '$0 install' first"
        return 1
    fi
}

# basic build file cleanup
remove_build_files() {
    echo "clean: removing build files"
    sudo rm -rf build
    sudo rm -rf input_remapper.egg-info
}

# manual removal of the main system files
remove_system_files() {
    echo "manual removal: cleaning up /usr/bin binaries"
    sudo rm -f /usr/bin/input-remapper-gtk
    sudo rm -f /usr/bin/input-remapper-service
    sudo rm -f /usr/bin/input-remapper-reader-service
    sudo rm -f /usr/bin/input-remapper-control
    sudo rm -f /usr/bin/key-remapper-gtk
    sudo rm -f /usr/bin/key-remapper-service
    sudo rm -f /usr/bin/key-remapper-control

    echo "manual removal: cleaning up /usr/share and service files"
    sudo rm -rf /usr/share/input-remapper
    sudo rm -f /usr/share/applications/input-remapper-gtk.desktop
    sudo rm -f /usr/lib/systemd/system/input-remapper.service

    echo "manual removal: cleaning up /etc, config, and startup files"
    sudo rm -f /etc/dbus-1/system.d/inputremapper.Control.conf 
    sudo rm -f /etc/xdg/autostart/input-remapper-autoload.desktop 
    sudo rm -f /usr/lib/udev/rules.d/99-input-remapper.rules     
}

# find what is installed and print it (returns 1 if anything is found)
check_system_files() {
    echo "checking for installed system files"
    files="$((
        find /usr         -name 'input*remapper*'
        find /etc         -name 'input*remapper*'
        find $HOME/.local -name 'input*remapper*'
    ) 2> /dev/null)" 

    if test -n "$files"; then
        echo -e "system files installed:\n$files"
        return 1
    fi
}

for cmd in $*; do case "$cmd" in
    inst*)         stop_service; system_install && start_service || exit 1 ;;
    local-inst*)   stop_service; local_install  && start_service || exit 1 ;;
    uninst*)       stop_service; uninstall && check_system_files || exit 1 ;;
    show)          check_system_files ;;
    clean)         remove_build_files ;;
    purge)         uninstall; remove_system_files; remove_build_files; check_system_files || exit 1 ;;
    *)             echo "usage: $0 [local-]install|uninstall|show|clean|purge"; exit 1;;
esac; done
