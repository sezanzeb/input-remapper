# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2026 sezanzeb <4t1pzast9@mozmail.com>
#
# This file is part of input-remapper.
#
# input-remapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# input-remapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with input-remapper.  If not, see <https://www.gnu.org/licenses/>.


"""Convert between v3 profiles and v1 preset files.

Rendering produces ordinary v1 presets, named so the old UI shows they are
generated. They are overwritten on every Apply and never read back.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from evdev.ecodes import EV_ABS, EV_KEY, EV_REL

from inputremapper.configs.mapping import Mapping
from inputremapper.configs.paths import PathUtils
from inputremapper.gui_v3.block_ops import first_gap
from inputremapper.gui_v3.document import Entry, InputRef, Profile, Trigger
from inputremapper.gui_v3.macro_text import (
    MacroTextError,
    parse_text,
    print_chain,
)
from inputremapper.gui_v3.tree import Call
from inputremapper.injection.global_uinputs import AUTO_UINPUT, GlobalUInputs

RENDERED_PREFIX = "[v3 read-only] "

# Mapping fields that v3 models itself, everything else is carried in v1_extra.
_HANDLED_FIELDS = {"input_combination", "name", "output_symbol", "target_uinput"}


class RenderError(ValueError):
    """Rendering failed. With an `entry_id`, the problem is in that entry, and the
    message is written to follow "In this mapping, "."""

    def __init__(self, message: str, entry_id: str | None = None) -> None:
        super().__init__(message)
        self.entry_id = entry_id


def rendered_name(profile_name: str) -> str:
    return f"{RENDERED_PREFIX}{profile_name}"


def is_rendered_name(preset_name: str) -> bool:
    return preset_name.startswith(RENDERED_PREFIX)


def entry_to_mapping(entry: Entry) -> dict[str, Any]:
    """The v1 mapping dict for an entry, as it is stored in a preset file."""
    if not entry.trigger.inputs:
        raise RenderError("no keys are set to trigger it", entry.id)

    gap = first_gap(entry.then)
    if gap is not None:
        raise RenderError(gap, entry.id)

    mapping: dict[str, Any] = {
        "input_combination": [i.to_json() for i in entry.trigger.inputs],
        "target_uinput": AUTO_UINPUT,
    }
    if entry.name:
        mapping["name"] = entry.name
    if entry.then:
        mapping["output_symbol"] = print_chain(entry.then)
    mapping.update(entry.v1_extra)
    if not entry.then:
        mapping["target_uinput"] = _device_for_output(mapping)
    _check_with_fitting_target(mapping, entry.id)
    return mapping


# v3 has no output device setting. Key and macro outputs use "auto": the engine sends
# each key to the keyboard and each mouse button to the mouse. Other outputs (analog
# ones, imported from v1) use the first of these that can produce them.
_OUTPUT_DEVICES = ("keyboard", "mouse", "gamepad")


def _device_for_output(mapping: dict[str, Any]) -> str:
    """The device for an output that isn't a macro, like an analog axis."""
    type_: int | None = mapping.get("output_type")
    code: int | None = mapping.get("output_code")
    if type_ == EV_ABS:
        return "gamepad"
    if type_ == EV_REL:
        return "mouse"
    if type_ is not None and code is not None and type_ == EV_KEY:
        for device in GlobalUInputs.find_fitting_default_uinputs(type_, code):
            if device in _OUTPUT_DEVICES:
                return device
    return _OUTPUT_DEVICES[0]


def _check_with_fitting_target(mapping: dict[str, Any], entry_id: str) -> None:
    """Validate the mapping, switching the target device to one that can produce
    all of its keys (keys and mouse buttons together need "keyboard + mouse")."""
    try:
        _check_mapping(mapping, entry_id)
        return
    except RenderError:
        for target in _OUTPUT_DEVICES:
            if target == mapping["target_uinput"]:
                continue
            try:
                _check_mapping({**mapping, "target_uinput": target}, entry_id)
            except RenderError:
                continue
            mapping["target_uinput"] = target
            return
        raise


def _check_mapping(mapping: dict[str, Any], entry_id: str) -> None:
    """Run the mapping through the same validation the service applies, so that
    problems are shown on Apply and not only in the service's log."""
    try:
        Mapping(**mapping).assert_strict()
    except Exception as error:
        errors = getattr(error, "errors", None)
        if callable(errors):
            found = cast(Callable[[], list[dict[str, Any]]], errors)()
            reasons = [str(e.get("msg", "")) for e in found]
        else:
            reasons = [str(error)]
        reason = "; ".join(r.strip() for r in reasons if r.strip())
        raise RenderError(reason or "it is not valid", entry_id) from error


def render_profile(profile: Profile) -> dict[str, list[dict[str, Any]]]:
    """Group the profile's mappings by device. Keys are device group keys."""
    by_device: dict[str, list[dict[str, Any]]] = {}
    for entry in profile.entries:
        if entry.trigger.device is None:
            raise RenderError("no device is chosen", entry.id)
        by_device.setdefault(entry.trigger.device, []).append(entry_to_mapping(entry))
    return by_device


def write_rendered(
    profile: Profile,
    group_name_of: Callable[[str], str | None],
    presets_dir: str | os.PathLike[str] | None = None,
) -> dict[str, str]:
    """Write v1 presets for the profile. Returns {device group key: preset name}.

    `group_name_of` maps a group key to the directory name the daemon looks in,
    or None for devices that are not connected. Those are skipped.
    Rendering is checked completely before anything is written.
    """
    rendered = render_profile(profile)
    base = presets_dir if presets_dir is not None else PathUtils.get_preset_path()
    preset_name = rendered_name(profile.name)

    targets: dict[str, tuple[Path, list[dict[str, Any]]]] = {}
    for group_key, mappings in rendered.items():
        group_name = group_name_of(group_key)
        if group_name is None:
            continue
        path = (
            Path(base)
            / PathUtils.sanitize_path_component(group_name)
            / f"{preset_name}.json"
        )
        targets[group_key] = (path, mappings)

    for path, mappings in targets.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(mappings, indent=4) + "\n")
        os.replace(temporary, path)

    return {key: preset_name for key in targets}


# Import ---------------------------------------------------------------------------


def entry_from_mapping(mapping: dict[str, Any], device: str | None) -> Entry:
    inputs = tuple(InputRef.from_json(i) for i in mapping.get("input_combination", []))

    then: tuple[Call, ...] = ()
    output = mapping.get("output_symbol")
    if output:
        try:
            then = parse_text(output)
            if len(then) == 1 and then[0].op == "symbol":
                # v1's plain "type this key" output holds the key while the trigger
                # is held; `hold_keys` is that, as a block that combines with others.
                then = (Call("hold_keys", (str(then[0].args[0]),)),)
        except MacroTextError:
            # Keep the original text; the block editor shows it as a grey block.
            then = (Call("raw", (output,)),)

    return Entry(
        name=mapping.get("name"),
        trigger=Trigger(inputs=inputs, device=device),
        then=then,
        v1_extra={k: v for k, v in mapping.items() if k not in _HANDLED_FIELDS},
    )


def import_preset_file(path: str | os.PathLike[str], device: str | None) -> list[Entry]:
    """Read a v1 preset file and convert each mapping to an entry."""
    data: Any = json.loads(Path(path).read_text() or "[]")
    if not isinstance(data, list):
        raise RenderError(f'"{path}" is not a preset file')
    items = cast("list[Any]", data)
    return [
        entry_from_mapping(cast("dict[str, Any]", m), device)
        for m in items
        if isinstance(m, dict)
    ]
