#!/usr/bin/env bash
# Provides commands for installing and uninstalling input-remapper in the system.
# Supports using the system's `/usr/bin/python3` or the local `python3`.
# Provides commands for cleaning up everything.
# Supports installation of the modules in a virtual env.

python=/usr/bin/python3           # python executable used by this script
script="$(readlink -f "$0")"      # absolute path of this script
scripts="$(dirname $"$script")"   # dir of this script
source="$(dirname "$scripts")"    # input-remapper source dir
build="$source/build"             # build dir used during installation
bin="$source/bin"                 # source dir of the binaries
project="$(basename "$source")"   # name of the source dir (must be "input-remapper")

# sanity that check we are managing the right source code
if test "$project" = "input-remapper"
then echo "using input-remapper sources in '$source'"
else echo "could not find input-remapper at '$source'"; exit 1
fi

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
    sudo $python "$source/setup.py" install --record "$build/files.txt"
    sudo chown "$USER:$USER" build "$build/files.txt"
    echo "install: writing list of install dirs to 'build/dirs.txt'"
    grep -o '.*input[-_]*remapper.*/' "$build/files.txt" | sort -r -u > "$build/dirs.txt"
}

# use whatever python3 is currently used even in a virtual env
local_install() {
    if test -n "$VIRTUAL_ENV"; then
        echo "install: running in virtual env '$VIRTUAL_ENV'"
        site_packages="$(find "$VIRTUAL_ENV" -name site-packages)"
        echo "install: temporarily ingesting site-packages path '$site_packages' into binaries"
        inject_path inject "$site_packages"
    fi

    echo "install: using local python3"
    python=python3 system_install

    if test -n "$VIRTUAL_ENV"; then
        echo "install: removing temporary site-packages path from binaries"
        inject_path uninject
    fi
}

# determine which files were installed an then remove them together with any empty target dirs
uninstall() {
    echo "uninstall: removing previously recorded installation files"
    if test -e "$build/files.txt" -a -e "$build/dirs.txt"; then
        echo "uninstall: removing files from build/files.txt"
        sudo xargs -I "FILE" rm -v -f "FILE" <"$build/files.txt"
        echo "uninstall: removing empty dirs from build/dirs.txt"
        sudo xargs -I "FILE" rmdir --parents --ignore-fail-on-non-empty "FILE" <"$build/dirs.txt" 2> /dev/null
        return 0
    else
        echo "uninstall: build/files.txt or build/dirs.txt not found, please reinstall using '$0 install' first"
        return 1
    fi
}

# basic build file cleanup
remove_build_files() {
    echo "clean: removing build files"
    sudo rm -rf "$source/build"
    sudo rm -rf "$source/input_remapper.egg-info"
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
    files="$(
        find /usr         -name 'input*remapper*' 2> /dev/null
        find /etc         -name 'input*remapper*' 2> /dev/null
        find $HOME/.local -name 'input*remapper*' 2> /dev/null
    )"

    if test -n "$files"; then
        echo -e "system files installed:\n$files"
        return 1
    fi
}

inject_path() {
    case "$1" in
        inject)
            inject_path="${2:-"$source"}"
            echo "inject import path '$inject_path' in bin file sources"
            sed -i "s#^import sys\$#import sys; sys.path.append(\"$inject_path\")#" "$bin"/input-remapper*
        ;;
        uninject)
            echo "remove extra import path in bin file sources"
            sed -i "s#^import sys; sys\\.path\\.append.*#import sys#" "$bin"/input-remapper*
        ;;
        *) echo "usage: $0 inject|uninject [PATH]"; return 1;;
    esac

    echo "injection result:"
    grep --color -E 'import sys$|import sys;.*' "$bin"/*
    echo "injection finished"
}

usage() {
cat <<-EOF

usage: $script [COMMAND..]

commands:
    help             show this help
    install          install using '$python $source/setup.py' (system python)
    local-install    install using 'python3 $source/setup.py' (local python)
    uninstall        uninstall everything
    show             find and show all installed filles
    clean            clean up build files
    purge            find and remove everything that was installed
    inject [path]    inject a 'sys.path' into the files in '$bin'
    uninject         undo the path injection

EOF
}

while test $# -gt 0; do case "$1" in
    inst*)           stop_service; system_install && start_service || exit 1 ;;
    local-inst*)     stop_service; local_install  && start_service || exit 1 ;;
    uninst*)         stop_service; uninstall && check_system_files || exit 1 ;;
    show)            check_system_files ;;
    clean)           remove_build_files ;;
    inject)          if test -e "$2"                      # check if next arg is a 'path'
                     then inject_path inject "$2"; shift  # use it and remove it
                     else inject_path inject              # use the default path
                     fi ;;
    uninject)        inject_path uninject ;;
    purge)           uninstall; remove_system_files; remove_build_files; check_system_files || exit 1 ;;
    help|-h|--help)  usage; exit 0 ;;
    *)               usage; exit 1 ;;
esac; shift; done
