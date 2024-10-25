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
> ```c#
> key(symbol: str)
> ```
>
> Examples:
>
> ```c#
> key(symbol=KEY_A)
> key(b).key(space)
> ```

### key_down and key_up

> Inject the press/down/1 and release/up/0 events individually with those macros.
>
> ```c#
> key_down(symbol: str)
> key_up(symbol: str)
> ```
>
> Examples:
>
> ```c#
> key_down(KEY_A)
> key_up(KEY_B)
> ```

### wait

> Waits in milliseconds before continuing the macro. If the max_time argument is
> provided, it will randomize the time between time and max_time.
> 
> ```c#
> wait(time: int, max_time: int | None)
> ```
>
> Examples:
>
> ```c#
> wait(time=100)
> wait(500)
> wait(10, 1000)
> ```

### repeat

> Repeats the execution of the second parameter a few times
>
> ```c#
> repeat(repeats: int, macro: Macro)
> ```
>
> Examples:
>
> ```c#
> repeat(1, key(KEY_A))
> repeat(repeats=2, key(space))
> ```

### modify

> Holds a modifier while executing the second parameter
>
> ```c#
> modify(modifier: str, macro: Macro)
> ```
>
> Examples:
>
> ```c#
> modify(Control_L, k(a).k(x))
> ```

### hold

> Executes the child macro repeatedly as long as the key is pressed down.
>
> ```c#
> hold(macro: Macro)
> ```
>
> Examples:
>
> ```c#
> hold(key(space))
> ```

### hold_keys

> Holds down all the provided symbols like a combination.
>
> An arbitrary number of symbols can be provided.
>
> ```c#
> hold_keys(*symbols: str)
> ```
>
> Examples:
>
> ```c#
> hold_keys(KEY_LEFTCTRL, KEY_A)
> hold_keys(Control_L, Alt_L, Delete)
> set(foo, KEY_A).hold_keys($foo)
> ```

### mouse

> Moves the mouse cursor
> 
> If `acceleration` is provided then the cursor will accelerate from zero to a maximum speed of `speed`. 
>
> ```c#
> mouse(direction: str, speed: int, acceleration: float | None)
> ```
>
> Examples:
>
> ```c#
> mouse(up, 1)
> mouse(left, 2)
> mouse(down, 10, 0.3)
> ```

### wheel

> Injects scroll wheel events
>
> ```c#
> wheel(direction: str, speed: int)
> ```
>
> Examples:
>
> ```c#
> mouse(up, 10)
> mouse(left, 20)
> ```

### event

> Writes an event. Examples for `type`, `code` and `value` can be found via the
> `sudo evtest` command
>
> ```c#
> event(type: str | int, code: str | int, value: int)
> ```
>
> Examples:
>
> ```c#
> event(EV_KEY, KEY_A, 1)
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
> ```c#
> set(variable: str, value: str | int)
> ```
>
> Examples:
>
> ```c#
> set(foo, 1)
> set(foo, "qux")
> ```

### add

> Adds a number fo a variable.
>
> ```c#
> add(variable: str, value: int)
> ```
>
> Examples:
>
> ```c#
> set(a, 1).add(a, 2).if_eq($a, 3, key(x), key(y))
> ```

### if_eq

> Compare two values and run different macros depending on the outcome.
>
> ```c#
> if_eq(value_1: str | int, value_2: str | int, then: Macro | None, else: Macro | None)
> ```
>
> Examples:
>
> ```c#
> set(a, 1).if_eq($a, 1, key(KEY_A), key(KEY_B))
> set(a, 1).set(b, 1).if_eq($a, $b, else=key(KEY_B).key(KEY_C))
> set(a, "foo").if_eq("foo", $a, key(KEY_A))
> set(a, 1).if_eq($a, 1, None, key(KEY_B))
> ```

### if_tap

> If the key is tapped quickly, run the `then` macro, otherwise the
> second. The third param is the optional time in milliseconds and defaults to
> 300ms
>
> ```c#
> if_tap(then: Macro | None, else: Macro | None, timeout: int)
> ```
>
> Examples:
>
> ```c#
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
> ```c#
> if_single(then: Macro | None, else: Macro | None, timeout: int | None)
> ```
>
> Examples:
>
> ```c#
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


