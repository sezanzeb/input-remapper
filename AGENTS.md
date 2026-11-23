# Notes for agents

See `readme/development.md` for the general contribution rules. This file covers what
is easy to get wrong when working in this repo.

## Running things

- Python needs `evdev`, `gi`, `pydantic` and friends from the system. A virtualenv or
  an asdf/pyenv shim usually lacks them; use `/usr/bin/python3` if imports fail.
- Run tests with unittest, not pytest:
  `python3 -m unittest discover -s tests/unit -t .`
  or a single file: `python3 -m unittest tests.unit.test_gui_v3.test_undo`
- Most tests use `@test_setup`, which aborts with "Expected the service not to be
  running already" if `input-remapper.service` is active on the machine. Stop the
  service before running them (`sudo systemctl stop input-remapper.service`), and
  tell the user, since it needs root and they may be using it.
- Tests without `@test_setup` must not touch the real config directory: pass explicit
  temp paths, never rely on `PathUtils` defaults.

## Style and checks

CI runs `black --check` and `ruff check`. Both must pass. Type hints are required.
Annotate empty containers (`items: list[Foo] = []`), and use `os.PathLike[str]`
rather than bare `os.PathLike`.

New files carry the GPL header used by the other files.

## The beta GUI

Work in `inputremapper/gui_v3` is covered by its own notes in
`inputremapper/gui_v3/AGENTS.md`. Read them first.
