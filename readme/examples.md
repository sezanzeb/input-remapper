# Examples

Examples for particular devices and/or use cases:

## Event Names

- Alphanumeric `a` to `z` and `0` to `9`
- Modifiers `Alt_L` `Control_L` `Control_R` `Shift_L` `Shift_R`
- Mouse buttons `BTN_LEFT` `BTN_RIGHT` `BTN_MIDDLE` `BTN_SIDE` ...
- Multimedia keys `KEY_NEXTSONG` `KEY_PLAYPAUSE` `XF86AudioMicMute` ...

Mouse movements have to be performed by macros. See below.

## Short Macro Examples

- `key(BTN_LEFT)` a single mouse-click
- `key(1).key(2)` 1, 2
- `wheel(down, 10)` `wheel(up, 10)` Scroll while the input is pressed.
- `mouse(left, 5)` `mouse(right, 2)` `mouse(up, 1)` `mouse(down, 3)` Move the cursor while the input is pressed.
- `repeat(3, key(a).w(500))` a, a, a with 500ms pause
- `modify(Control_L, key(a).key(x))` CTRL + a, CTRL + x
- `key(1).hold(key(2)).key(3)` writes 1 2 2 ... 2 2 3 while the key is pressed
- `event(EV_REL, REL_X, 10)` moves the mouse cursor 10px to the right
- `mouse(right, 4)` which keeps moving the mouse while pressed
- `wheel(down, 1)` keeps scrolling down while held
- `set(foo, 1)` set ["foo"](https://en.wikipedia.org/wiki/Metasyntactic_variable) to 1
- `if_eq($foo, 1, key(x), key(y))` if "foo" is 1, write x, otherwise y
- `hold()` does nothing as long as your key is held down
- `hold_keys(a)` holds down "a" as long as the key is pressed, just like a regular non-macro mapping
- `if_tap(key(a), key(b))` writes a if the key is tapped, otherwise b
- `if_tap(key(a), key(b), 1000)` writes a if the key is released within a second, otherwise b
- `if_single(key(a), key(b))` writes b if another key is pressed, or a if the key is released
  and no other key was pressed in the meantime.
- `if_tap(if_tap(key(a), key(b)), key(c))` "a" if tapped twice, "b" if tapped once and "c" if
  held down long enough
- `key_up(a).wait(1000).key_down(a)` keeps a pressed for one second
- `hold_keys(Control_L, a)` holds down those two keys
- `key(BTN_LEFT).wait(100).key(BTN_LEFT)` a double-click

## Double Tap

```
if_tap(
  if_tap(
    key(a),
    key(c)
  ),
  key(b)
)
```

- press twice: a
- press and hold: b
- press and release: c

## Combinations Spanning Multiple Devices

For regular combinations on only single devices it is not required to
configure macros. See [readme/usage.md](usage.md#combinations).

**Keyboard** `space` `set(foo, 1).hold_keys(space).set(foo, 0)`

**Mouse** `middle` `if_eq($foo, 1, hold_keys(a), hold_keys(BTN_MIDDLE))`

Apply both presets. If you press space on your keyboard, it will write a
space exactly like it used to. If you hold down space and press the middle
button of your mouse, it will write "a" instead. If you just press the
middle button of your mouse it behaves like a regular middle mouse button.

**Explanation**

`hold_keys(space)` makes your key work exactly like if it was mapped to "space".
It will inject a key-down event if you press it, does nothing as long you
hold your key down, and injects a key-up event after releasing.
`set(foo, 1).set(foo, 0)` sets "foo" to 1 and then sets "foo" to 0.
`set` and `if_eq` work on shared memory, so all injections will see your
variables. Combine both to get a key that works like a normal key, but that also
works as a modifier for other keys of other devices. `if_eq($foo, 1, ..., ...)`
runs the first param if foo is 1, or the second one if foo is not 1.


## Scroll and Click on a Keyboard

Seldom used PrintScreen, ScrollLock and Pause keys on keyboards with TKL (ten key
less) layout are easily accessible by the right hand thanks to the missing
numeric block, so they can be mapped to mouse scroll and click events:

- Print: `wheel(up, 1)`
- Pause: `wheel(down, 1)`
- Scroll Lock: `BTN_LEFT`
- Menu: `BTN_RIGHT`
- F12: `KEY_LEFTCTRL + w`

In contrast to libinput's `ScrollMethod` `button` which requires the scroll
button to belong to the same (mouse) device, clicking and scrolling events mapped
to a keyboard key can fully cooperate with events from a real mouse, e.g.
drag'n'drop by holding a (mapped) keyboard key and moving the cursor by mouse.

Mapping the scrolling to a keyboard key is also useful for trackballs without
a scroll ring.

In contrast to a real scroll wheel, holding a key which has mouse wheel event
mapped produces linear auto-repeat, without any acceleration. Using a PageDown
key for fast scrolling requires only a small adjustment of the right hand
position.

## Scroll on a 3-Button Mouse

Cheap 3-button mouse without a scroll wheel can scroll using the middle button:

- Button MIDDLE: `wheel(down, 1)`

## Click on Lower Buttons of Trackball

Trackball with 4 buttons (e.g. Kensington Wireless Expert Mouse) with lower 2
buttons by default assigned to middle and side button can be remapped to provide
left and right click on both the upper and lower pairs of buttons to avoid
readjusting a hand after moving the cursor down:

- Button MIDDLE: BTN_LEFT
- Button SIDE: BTN_RIGHT

## Scroll on Foot Pedals

While Kinesis Savant Elite 2 foot pedals can be programmed to emit key press or
mouse click events, they cannot emit scroll events themselves. Using the pedals
for scrolling while standing at a standing desk is possible thanks to remapping:

- Button LEFT: `wheel(up, 1)`
- Button RIGHT: `wheel(down, 1)`

## Gamepads

Joystick movements will be translated to mouse movements, while the second
joystick acts as a mouse wheel. You can swap this in the user interface.
All buttons, triggers and D-Pads can be mapped to keycodes and macros.

The D-Pad can be mapped to W, A, S, D for example, to run around in games,
while the joystick turns the view (depending on the game).

Tested with the XBOX 360 Gamepad. On Ubuntu, gamepads worked better in
Wayland than with X11.

## Sequence of Keys with Modifiers

Alt+TAB, Enter, Alt+TAB:

```
modify(Alt_L, key(tab)).wait(250).
key(KP_Enter).key(key_UP).wait(150).
modify(Alt_L, key(tab))
```

## Home Row Mods

See https://precondition.github.io/home-row-mods#home-row-mods-order

- a: `mod_tap(a, Super_L)`
- s: `mod_tap(s, Alt_L)`
- d: `mod_tap(d, Shift_L)`
- f: `mod_tap(f, Control_L)`

## Emitting Unavailable Symbols

For example Japanese letters without overwriting any existing key
of your system-layout. Only works in X11.

```
xmodmap -pke > keyboard_layout
mousepad keyboard_layout &
```

Find a code that is not mapped to anything, for example `keycode  93 = `,
and map it like `keycode  93 = kana_YA`. See [this gist](https://gist.github.com/sezanzeb/e29bae637b8a799ccf2490b8537487df)
for available symbols.

```
xmodmap keyboard_layout
input-remapper-gtk
```

"kana_YA" should be in the dropdown of available symbols now. Map it
to a key and press apply. Now run

```
xmodmap keyboard_layout
```

again for the injection to use that xmodmap as well. It should be possible
to write "ヤ" now when pressing the key.

## Implementing Layers

We can implement layer functionality (similar to QMK) using the `set` and `if_eq` macros.

- `A`: `set(foo, 0)`
- `B`: `set(foo, 1)`
- `X`: `if_eq(foo, 1, hold_keys(Y), hold_keys(X))`

Pressing `A` sets `$foo=0`, pressing `B` sets `$foo=1`. `X` is `Y` if `$foo=1`, otherwise `X` is `X`. Pressing `A` > `X` > `B` > `X` will output `XY`.



We can implement a single macro to toggle back and forth betwixt layers.

- `A`:`if_eq(foo, 1, set(foo, 0), set(foo, 1))`
- `X`:`if_eq(foo, 1, hold_keys(Y), hold_keys(X))`

Pressing `A` toggles between `$foo=0` and `$foo=1`. So pressing `X` > `A` > `X` will output `XY` (or `YX` if you start from `$foo=1`).


We can create layer-shift macros that will enable the layer only while being held.

- `A`:`set(foo, 1).hold().set(foo, 0)`
- `X`:`if_eq(foo, 1, hold_keys(Y), hold_keys(X))`

This will set `$foo=1` only while `A` is held down. Pressing `X` will output `X` but holding `A` while pressing `X` will output `Y`. 

We can extend this further to create second (and third, fourth, etc...) layer macros for the entire keyboard.

For example creating a Vim HJKL movement layer when `left Alt` is held down.

- `Alt_L`:`set(layer, 1).hold().set(layer, 0)`
- `H`:`ifeq(layer, 1, hold_keys(Left), hold_keys(H))`
- `J`:`ifeq(layer, 1, hold_keys(Down), hold_keys(J))`
- `K`:`ifeq(layer, 1, hold_keys(Up), hold_keys(K))`
- `L`:`ifeq(layer, 1, hold_keys(Right), hold_keys(L))`

