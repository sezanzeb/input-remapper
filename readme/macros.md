# Macros

This document contains examples for macros with explanations. You are very
welcome to contribute your examples as well if you have a special use-case
via a pull-request.

## The syntax

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
- variable names (used in `set`, `get` and `ifeq`)
- funcion names (like `r` or `mouse`)
- key names (like `a` or `BTN_LEFT`)

Depending on how names are used they have a different meaning. If you were
to use `set(BTN_LEFT, 1)`, `k(BTN_KEFT)` would still write a left mouse click,
but `get(BTN_LEFT, 2)` yields `1` now. `get(BTN_RIGHT, 2)` would yield 2.

Whitespaces, newlines and tabs don't have any meaning and are removed
when the macro gets compiled.

## Combinations spanning multiple devices

**Keyboard:**

`space` -> `set(foo, bar).m(space, h()).set(foo, 0)`
`space` -> `idk1(foo, bar, space, 0)`

**Mouse:**

`middle` -> `ifeq(foo, bar, m(a, h()), m(BTN_MIDDLE, h()))`
`middle` -> `idk2(foo, bar, a, BTN_MIDDLE)`

# TODO capabilities in this case?
`middle` -> `m(ifeq(foo, bar, a, BTN_MIDDLE), h())`

Apply both presets.

If you press space on your keyboard, it will write a space exactly like
it used to.

If you hold down space and press the middle button of your mouse, it will
write "a" instead.

If you just press the middle button of your mouse it behaves like a regular
middle mouse button.

**Explanation:**

`m(space, h())` makes your key work exactly like it was mapped to "space".
It will inject a key-down event if you press it, and a key-up event after
releasing. Because `m` waits for `h()` to finish, which will block as long
as your key is held down.

`set(foo, 1).h().set(foo, 0)` sets "foo" to 1, waits until your key is
released and then sets "foo" to 0. `set` and `ifeq` work on shared memory,
so all injections will see your variables.

Combine both to get a key that works like a normal key, but that also
works as a modifier for other keys of other devices

`ifeq(foo, 1, a, BTN_MIDDLE)` returns either "a" or "BTN_MIDDLE" depending
on the value of foo. # TODO
