# setxkbmap-gtk

This in a very early stage. But due to having all my vacation distributed until the end of the year it will probably
be easily finished this year.

GUI tool to map input buttons to e.g. change the thumb keys of the razor naga mouse or any keyboard to something
different. It should not be device specific, any input device supported by Linux plug and play will likely
work.

# TODO

- show a dropdown to select an arbitrary device from
- show a list that can be extended with a `[+]` button, showing `[keycode, current key for that keycode -> target]`
- generate a xmodmap.*.whatever file out of that (like for example https://github.com/sezanzeb/colemakDE/blob/master/xmodmap.colemak.de)
- load that file. Does it need to be loaded on every startup or every time the device connects? If so, add udev rules
