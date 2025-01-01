# Macros

input-remapper comes with an optional custom macro language with support for cross-device
variables, conditions and named parameters.

Syntax errors are shown in the UI on save. Each `key` function adds a short delay of 10ms
between key-down, key-up and at the end. See [usage.md](usage.md#configuration-files)
for more info.

Macros are written into the same text field, that would usually contain the output symbol.

Bear in mind that anti-cheat software might detect macros in games.

### key

> Acts like a pressed key. All names that are available in regular mappings can be used
> here.
>
> You don't have to use quotes around the symbol constants.
>
> ```ts
> key(symbol: str)
> ```
>
> Examples:
>
> ```ts
> key(symbol=KEY_A)
> key(b).key(space)
> ```

### key_down and key_up

> Inject the press/down/1 and release/up/0 events individually with those macros.
>
> ```ts
> key_down(symbol: str)
> key_up(symbol: str)
> ```
>
> Examples:
>
> ```ts
> key_down(KEY_A)
> key_up(KEY_B)
> ```

### wait

> Waits in milliseconds before continuing the macro. If the max_time argument is
> provided, it will randomize the time between time and max_time.
> 
> ```ts
> wait(time: int, max_time: int | None)
> ```
>
> Examples:
>
> ```ts
> wait(time=100)
> wait(500)
> wait(10, 1000)
> ```

### repeat

> Repeats the execution of the second parameter a few times
>
> ```ts
> repeat(repeats: int, macro: Macro)
> ```
>
> Examples:
>
> ```ts
> repeat(1, key(KEY_A))
> repeat(repeats=2, key(space))
> ```

### modify

> Holds a modifier while executing the second parameter
>
> ```ts
> modify(modifier: str, macro: Macro)
> ```
>
> Examples:
>
> ```ts
> modify(Control_L, key(a).key(x))
> ```

### mod_tap

> If an input is held down long enough, then it turns into a modifier for all keys
> that came and come afterwards.
> 
> You can use this to create home row mods for example.
> 
> Behaves similar to the Mod-Tap feature of QMK.
>
> ```ts
> mod_tap(default: str, modifier: str, tapping_term: int)
> ```
>
> Examples:
>
> ```ts
> mod_tap(a, Shift_L)
> mod_tap(s, Control_L, 300)
> ```

### hold_keys

> Holds down all the provided symbols like a combination, and releases them when the
> actual key on your keyboard is released.
>
> An arbitrary number of symbols can be provided.
> 
> When provided with a single key, it will behave just like a regular keyboard key.
>
> ```ts
> hold_keys(*symbols: str)
> ```
>
> Examples:
>
> ```ts
> hold_keys(KEY_B)
> hold_keys(KEY_LEFTCTRL, KEY_A)
> hold_keys(Control_L, Alt_L, Delete)
> set(foo, KEY_A).hold_keys($foo)
> ```

### hold

> Executes the child macro repeatedly as long as the key is pressed down.
>
> ```ts
> hold(macro: Macro)
> ```
>
> Examples:
>
> ```ts
> hold(key(space))
> ```

### mouse

> Moves the mouse cursor
> 
> If `acceleration` is provided then the cursor will accelerate from zero to a maximum
> speed of `speed`.
>
> ```ts
> mouse(direction: str, speed: int, acceleration: float | None)
> ```
>
> Examples:
>
> ```ts
> mouse(up, 1)
> mouse(left, 2)
> mouse(down, 10, 0.3)
> ```

### mouse_xy

> Moves the mouse cursor in both x and y direction.
> 
> If `acceleration` is provided then the cursor will accelerate from zero to the
> maximum specified x and y speeds.
>
> ```ts
> mouse(x: int | float, y: int | float, acceleration: float | None)
> ```
>
> Examples:
>
> ```ts
> mouse_xy(x=10, y=20)
> mouse_xy(-5, -1, 0.01)
> ```

### wheel

> Injects scroll wheel events
>
> ```ts
> wheel(direction: str, speed: int)
> ```
>
> Examples:
>
> ```ts
> mouse(up, 10)
> mouse(left, 20)
> ```

### event

> Writes an event. Examples for `type`, `code` and `value` can be found via the
> `sudo evtest` command. Also check out [input-event-codes.h](https://github.com/torvalds/linux/blob/master/include/uapi/linux/input-event-codes.h).
> `EV_KEY` for keys, `EV_REL` for mouse movements, `EV_ABS` for gamepad events among
> others.
>
> ```ts
> event(type: str | int, code: str | int, value: int)
> ```
>
> Examples:
>
> ```ts
> event(EV_KEY, KEY_A, 1)
> event(EV_REL, REL_X, -10)
> event(2, 8, 1)
> ```

### set

> Set a variable to a value. This variable and its value is available in all injection
> processes.
>
> Variables can be used in function arguments by adding a `$` in front of their name:
> `repeat($foo, key(KEY_A))`
>
> Their values are available for other injections/devices as well, so you can make them
> interact with each other. In other words, using `set` on a keyboard and `if_eq` with
> the previously used variable name on a mouse will work.
>
> ```ts
> set(variable: str, value: str | int)
> ```
>
> Examples:
>
> ```ts
> set(foo, 1)
> set(foo, "qux")
> ```

### add

> Adds a number fo a variable.
>
> ```ts
> add(variable: str, value: int)
> ```
>
> Examples:
>
> ```ts
> set(a, 1).add(a, 2).if_eq($a, 3, key(x), key(y))
> ```

### if_eq

> Compare two values and run different macros depending on the outcome.
>
> ```ts
> if_eq(value_1: str | int, value_2: str | int, then: Macro | None, else: Macro | None)
> ```
>
> Examples:
>
> ```ts
> set(a, 1).if_eq($a, 1, key(KEY_A), key(KEY_B))
> set(a, 1).set(b, 1).if_eq($a, $b, else=key(KEY_B).key(KEY_C))
> set(a, "foo").if_eq("foo", $a, key(KEY_A))
> set(a, 1).if_eq($a, 1, None, key(KEY_B))
> ```

### if_capslock

> Run the first macro if your capslock is on, otherwise the second.
>
> ```ts
> if_capslock(then: Macro | None, else: Macro | None)
> ```
>
> Examples:
>
> ```ts
> if_capslock(
>     then=hold_keys(KEY_3),
>     else=hold_keys(KEY_4)
> )
> ```

### if_numlock

> Run the first macro if your numlock is on, otherwise the second.
>
> ```ts
> if_numlock(then: Macro | None, else: Macro | None)
> ```
>
> Examples:
>
> ```ts
> if_numlock(hold_keys(KEY_3), hold_keys(KEY_4))
> ```

### if_tap

> If the key is tapped quickly, run the `then` macro, otherwise the
> second. The third param is the optional time in milliseconds and defaults to
> 300ms
>
> ```ts
> if_tap(then: Macro | None, else: Macro | None, timeout: int)
> ```
>
> Examples:
>
> ```ts
> if_tap(key(KEY_A), key(KEY_B), timeout=500)
> if_tap(then=key(KEY_A), else=key(KEY_B))
> ```

### if_single

> If the key that is mapped to the macro is pressed and released, run the `then` macro.
>
> If another key is pressed while the triggering key is held down, run the `else` macro.
> 
> If a timeout number is provided, the macro will run `else` if no event arrives for
> more than the configured number in milliseconds.
>
> ```ts
> if_single(then: Macro | None, else: Macro | None, timeout: int | None)
> ```
>
> Examples:
>
> ```ts
> if_single(key(KEY_A), key(KEY_B))
> if_single(None, key(KEY_B))
> if_single(then=key(KEY_A), else=key(KEY_B))
> if_single(key(KEY_A), key(KEY_B), timeout=1000)
> ```

## Syntax

Multiple functions are chained using `.`.

Unlike other programming languages, `qux(bar())` would not run `bar` and then
`qux`. Instead, `cux` can decide to run `bar` during runtime depending on various
other factors. Like `repeat` is running its parameter multiple times.

Whitespaces, newlines and tabs don't have any meaning and are removed when the macro
gets compiled, unless you wrap your strings in "quotes".

Similar to python, arguments can be either positional or keyword arguments.
`key(symbol=KEY_A)` is the same as `key(KEY_A)`.

Using `$` resolves a variable during runtime. For example `set(a, $1)` and
`if_eq($a, 1, key(KEY_A), key(KEY_B))`.

Comments can be written with '#', like `key(KEY_A) # write an "a"`


