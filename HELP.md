# The problems with overwriting keys

**Initial target** You write a symbols file based on your specified mapping,
and that's pretty much it. There were two mappings: The first one is in the
keycodes file and contains "<10> = 10", which is super redundant but needed
for xkb. The second one mapped "<10>" to characters, modifiers, etc. using
symbol files in xkb. However, if you had one keyboard layout for your mouse
that writes SHIFT keys on keycode 10, and one for your keyboard that is normal
and writes 1/! on keycode 10, then you would not be able to write ! by
pressing that mouse button and that keyboard button at the same time.
Keycodes may not clash.

**The second idea** was to write special keycodes known only to key-mapper
(256 - 511) into the input device of your mouse in /dev/input, and map
those to SHIFT and such, whenever a button is clicked. A mapping would have
existed to prevent the original keycode 10 from writing a 1. But X/Linux seem
to ignore anything greater than 255 for regular keyboard events, or even
crash in some cases. Mouse click buttons can use those high keycodes though,
but they cannot be remapped, which I guess is another indicator of that.

**The third idea** is to create a new input device that uses 8 - 255, just
like other layouts, and key-mapper always tries to use the same keycodes for
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
   
But this is a rather complicated approach. The mapping of 10 -> 50 would
have to be stored somewhere as well. It would make the mess of configuration
files already needed for xkb even worse.

**Fourth idea**: Based on the first idea, instead of using keycodes greater
than 255, use unused keycodes starting from 255, going down. Issues existed
when two buttons with the same keycode are pressed at the same time,
so the goal is to avoid such overlaps. For example, if keycode 10 should be
mapped to Shift_L. It is impossible to write "!" using this mapped button
and a second keyboard, except if pressing key 10 triggers key-mapper to write
key 253 into the /dev device, while mapping key 10 to nothing. Unfortunately
linux just completely ignores some keycodes. 140 works, 145 won't, 150 works.

**Fifth idea**: Instead of writing xkb symbol files, just disable all
mouse buttons with a single symbol file. Key-mapper listens for key events
in /dev and then writes the mapped keycode into /dev. For example, if 10
should be mapped to Shift_L, xkb configs would disable key 10 and key-mapper
would write 50 into /dev, which is Shift_L in xmodmaps output. This sounds
incredibly simple and makes me throw away tons of code. Branches for all that
stuff exist to archive it instead of loosing it forever.


# The various mappings

There were two mappings: The first one is in the keycodes file and contains
"<10> = 10", which is super redundant but needed for xkb. The second one
mapped "<10>" to characters, modifiers, etc. using symbol files in xkb.


The third mapping reads the input keycodes from your mouse (also known as
system_keycode here) and writes a different one into /dev (also known as
target_keycode here). It is explained above why.

# How I would have liked it to be

setxkbmap -layout ~/.config/key-mapper/mouse -device 13

config looks like:
```
10 = a, A
11 = Shift_L
```

done. Without crashing X. Without printing generic useless errors. Without
colliding with other devices using the same keycodes. If it was that easy,
an app to map keys would have already existed.

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
