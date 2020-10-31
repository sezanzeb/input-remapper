# Key Mapper

GUI tool to map input buttons to e.g. change the thumb keys of the razor naga mouse or any keyboard to something
different. It should not be device specific, any input device supported by Linux plug and play will likely
work.

<p align="center">
    <img src="data/screenshot.png"/>
</p>

# Roadmap

- [x] show a dropdown to select an arbitrary device from `xinput list`
- [x] creating plugins per device
- [ ] renaming plugins
- [ ] load xmodmap files from the config path
- [x] show a list that can be extended with a `[+]` button
- [ ] The list shows `[keycode, current key for that keycode -> target]`
- [ ] generate a xmodmap.*.whatever file out of that (like for example https://github.com/sezanzeb/colemakDE/blob/master/xmodmap.colemak.de)
- [ ] load that file (`setxkbmap funnystuff; xmodmap xmodmap.asdf.whatever`, `setxkbmap funnystuff -device <id>`).
- [ ] Does it need to be loaded on every startup or every time the device connects? If so, add udev rules
