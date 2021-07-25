# Macros

You are very welcome to contribute your examples as well if you have a 
pecial use-case via a pull-request.

## Overview

It is possible to write timed macros into the center column:
- `r` repeats the execution of the second parameter
- `w` waits in milliseconds
- `k` writes a single keystroke
- `e` writes an event
- `m` holds a modifier while executing the second parameter
- `h` executes the parameter as long as the key is pressed down
- `.` executes two actions behind each other
- `mouse` and `wheel` take a direction like "up" and speed as parameters
- `set` set a variable to a value, visible to all injection processes
- `ifeq` if that variable is a certain value do something

The names for the most common functions are kept short, to make it easy to
write them into the constrained space.

Examples:
- `k(BTN_LEFT)` a single mouse-click
- `k(1).k(2)` 1, 2
- `r(3, k(a).w(500))` a, a, a with 500ms pause
- `m(Control_L, k(a).k(x))` CTRL + a, CTRL + x
- `k(1).h(k(2)).k(3)` writes 1 2 2 ... 2 2 3 while the key is pressed
- `e(EV_REL, REL_X, 10)` moves the mouse cursor 10px to the right
- `mouse(right, 4)` which keeps moving the mouse while pressed.
  Made out of `h(e(...))` internally
- `wheel(down, 1)` keeps scrolling down while held
- `set(foo, 1)` set  "[foo](https://en.wikipedia.org/wiki/Foobar)" to 1
- `ifeq(foo, 1, k(x), k(y))` if "foo" is 1, write x, otherwise y
- `h()` does nothing as long as your key is held down
- `h(a)` holds down "a" as long as the key is pressed, just like a
  regular mapping

Syntax errors are shown in the UI on save. Each `k` function adds a short
delay of 10ms between key-down, key-up and at the end. See
[usage.md](usage.md#configuration-files) for more info.

Bear in mind that anti-cheat software might detect macros in games.

## Syntax

The system is very trivial and basic, lots of features known from other
scripting languages are missing.

Multiple functions are chained using `.`.

There are three datatypes for function parameters: Macro, string and number.
Unlike other programming languages, `qux(bar())` would not run `bar` and then
`qux`. Instead, `bar()` is an rvalue of type macro and only when `qux` is
called, the implementation of `qux` might decide to run `bar()`. That means
that reading a macro from left to right always yields the correct order of
operations. This is comparable to using lambda functions in python.

Strings don't need quotes. This makes macros look simpler, and I hope
this decision won't cause problems later when the macro system keeps advancing.

Keywords/names/strings available are either:
- variable names (used in `set` and `ifeq`)
- funcion names (like `r` or `mouse`)
- key names (like `a` or `BTN_LEFT`)

Whitespaces, newlines and tabs don't have any meaning and are removed
when the macro gets compiled.

## Combinations spanning multiple devices

For regular combinations on only single devices it is not required to
configure macros. See [readme/usage.md](usage.md).

**Keyboard** `space` `set(foo, bar).h(space).set(foo, 0)`

**Mouse** `middle` `ifeq(foo, bar, h(a), h(BTN_MIDDLE))`

Apply both presets. If you press space on your keyboard, it will write a
space exactly like it used to. If you hold down space and press the middle
button of your mouse, it will write "a" instead. If you just press the
middle button of your mouse it behaves like a regular middle mouse button.

**Explanation**

`h(space)` makes your key work exactly like if it was mapped to "space".
It will inject a key-down event if you press it, does nothing as long you
hold your key down, and injects a key-up event after releasing.
`set(foo, 1).set(foo, 0)` sets "foo" to 1 and then sets "foo" to 0.
`set` and `ifeq` work on shared memory, so all injections will see your
variables. Combine both to get a key that works like a normal key, but that also
works as a modifier for other keys of other devices. `ifeq(foo, bar, ..., ...)`
runs the first param if foo is "bar", or the second one if foo is not "bar".
