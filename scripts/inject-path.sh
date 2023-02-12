#!/usr/bin/env bash
# Modifies (or cleans) local bin/* files to point to the local development
# modules by injecting a corresponding `sys.path`.

case "$1" in
    inject)
        inject_path="${2:-$PWD}"
        echo "inject import path '$inject_path' in bin file sources"
        sed -i "s#^import sys\$#import sys; sys.path.append(\"$PWD\")#" bin/input-remapper*
    ;;
    clean)
        echo "remove extra import path in bin file sources"
        sed -i "s#^import sys; sys\\.path\\.append.*#import sys#" bin/input-remapper*
    ;;
    *) echo "usage inject|clean [PATH]"; exit 1;;
esac

echo "injection result:"
grep --color -E 'import sys$|import sys;.*' bin/*
echo "injection finished"
