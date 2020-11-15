# Folder Structure of Key Mapper

Stuff has to be placed in `/usr/share/X11/xkb` to my knowledge.

Every user gets a path within that `/usr/...` directory which is very
unconventional, but it works. This way the presets of multiple users
don't clash.

**Presets**

- `/usr/share/X11/xkb/symbols/key-mapper/<user>/<device>/<preset>`

This is how a single preset is stored.

**Defaults**

- `/usr/share/X11/xkb/symbols/key-mapper/<user>/default`

This is where key-mapper stores the defaults. They are generated from the
parsed output of `xmodmap` and used to keep the unmapped keys at their system
defaults.

**Keycodes**

- `/usr/share/X11/xkb/keycodes/key-mapper`

Because the concept of "reasonable symbolic names" ([www.x.org](https://www.x.org/releases/X11R7.7/doc/xorg-docs/input/XKB-Enhancing.html))
doesn't apply when mouse buttons are all over the place, an identity mapping
to make generating "symbols" files easier/possible exists. A keycode of
10 will be known as "<10>" in symbols configs. This has the added benefit
that keycodes reported by xev can be identified in the symbols file.
