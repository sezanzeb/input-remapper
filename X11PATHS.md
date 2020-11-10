# Folder Structure of Key Mapper

Stuff has to be placed in /usr/share/X11/xkb to my knowledge. In order to
be able to make backups of the configs, which would be expected in the
users home directory, this is symlinked to home.

Every user gets a path within that /usr directory which is very
unconventional, but it works. This way the presets of multiple users
don't clash.

This is how a single preset is stored. The path in /usr is a symlink, the
files are actually in home.
- /usr/share/X11/xkb/symbols/key-mapper/<user>/<device>/<preset>
- /home/<user>/.config/key-mapper/<device>/<preset>

This is where key-mapper stores the defaults. They are generated from the
parsed output of `xmodmap` and used to keep the unmapped keys at their system
defaults.
- /usr/share/X11/xkb/symbols/key-mapper/<user>/default
- /home/<user>/.config/key-mapper/default

Because the concept of "reasonable symbolic names" [3] doesn't apply
when mouse buttons are all over the place, an identity mapping
to make generating "symbols" files easier/possible exists.
Keycode 10 -> "<10>". This has the added benefit that keycodes reported
by xev can be identified in the symbols file.
- /usr/share/X11/xkb/keycodes/key-mapper

[3] https://www.x.org/releases/X11R7.7/doc/xorg-docs/input/XKB-Enhancing.html
