# The problems with overwriting keys

If you had one keyboard layout for your mouse that writes SHIFT keys on
keycode 10, and one for your keyboard that is normal and writes 1/! on
keycode 10, then you would not be able to write ! by pressing that mouse
button and that keyboard button at the same time. Keycodes may not clash.

The first idea was to write special keycodes known only to key-mapper
(256 - 511) into an input device in /dev/input, and map those to SHIFT and
such, whenever a button is clicked. A mapping would have existed to prevent
the original keycode 10 from writing a 1. But X seems to ignore anything
greater than 255, or even crash in some cases, for regular keyboard events.
Mouse buttons can use those though, but they cannot be remapped, which I
guess is another indicator of that.

The second idea is to create a new input device that uses 8 - 255, just like
other layouts, and key-mapper always tries to use the same keycodes for
SHIFT as already used in the system default. The pipeline is like this:

1. A human thumb presses an extra-button of the device "mouse"
2. key-mapper uses evdev to get the event from "mouse", sees "ahh, it's a
   10, I know that one and will now write 50 into my own device". 50 is
   the keycode for SHIFT on my regular keyboard, so it won't clash anymore
   with alphanumeric keys and such.
3. X has key-mappers configs for the key-mapper device loaded and
   checks in it's keycodes config file "50, that would be <50>", then looks
   into it's symbols config "<50> is mapped to SHIFT", and then it actually
   presses the SHIFT down to modify all other future buttons.
4. X has another config for "mouse" loaded, which prevents any system default
   mapping to print the overwritten key "1" into the session.

# How I would have liked it to be

setxkbmap -layout ~/.config/key-mapper/mouse -device 13

config looks like:
```
10 = a, A
11 = Shift_L
```

done. Without crashing X. Without printing generic useless errors. If it was
that easy, an app to map keys would have already existed.

# Folder Structure of Key Mapper in /usr

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
