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


"""The editable document: profiles, entries and variables.

Everything is immutable. An edit creates a new `Workspace`, which is what the undo
history stores. Sharing unchanged parts between snapshots keeps them cheap.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from typing import Any

from inputremapper.gui_v3.tree import Chain, chain_from_json, chain_to_json

FORMAT_VERSION = 1


@dataclass(frozen=True)
class InputRef:
    """One key or button of a trigger, same fields as a v1 input_combination."""

    type: int
    code: int
    origin_hash: str | None = None
    analog_threshold: int | None = None

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"type": self.type, "code": self.code}
        if self.origin_hash is not None:
            out["origin_hash"] = self.origin_hash
        if self.analog_threshold is not None:
            out["analog_threshold"] = self.analog_threshold
        return out

    @staticmethod
    def from_json(data: dict[str, Any]) -> InputRef:
        return InputRef(
            type=data["type"],
            code=data["code"],
            origin_hash=data.get("origin_hash"),
            analog_threshold=data.get("analog_threshold"),
        )


@dataclass(frozen=True)
class Trigger:
    inputs: tuple[InputRef, ...] = ()
    # Only "pressed" exists in the engine for now.
    on: str = "pressed"
    # The device group key, like "Logitech MX Keys". None until the user picks one.
    device: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "inputs": [i.to_json() for i in self.inputs],
            "on": self.on,
            "device": self.device,
        }

    @staticmethod
    def from_json(data: dict[str, Any]) -> Trigger:
        return Trigger(
            inputs=tuple(InputRef.from_json(i) for i in data.get("inputs", [])),
            on=data.get("on", "pressed"),
            device=data.get("device"),
        )


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass(frozen=True)
class Entry:
    """One "When ... Then ..." rule. Becomes one v1 mapping."""

    id: str = field(default_factory=_new_id)
    # None means "show a name inferred from the trigger".
    name: str | None = None
    trigger: Trigger = Trigger()
    then: Chain = ()
    # v1 mapping fields the editor doesn't expose (deadzone, release_timeout, ...).
    # Carried through unchanged. Treat as read-only; copy before modifying.
    v1_extra: dict[str, Any] = field(default_factory=dict[str, Any])

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "when": self.trigger.to_json(),
            "then": chain_to_json(self.then),
        }
        if self.v1_extra:
            out["v1_extra"] = self.v1_extra
        return out

    @staticmethod
    def from_json(data: dict[str, Any]) -> Entry:
        return Entry(
            id=data.get("id") or _new_id(),
            name=data.get("name"),
            trigger=Trigger.from_json(data.get("when", {})),
            then=chain_from_json(data.get("then", [])),
            v1_extra=dict(data.get("v1_extra", {})),
        )


@dataclass(frozen=True)
class Profile:
    name: str
    entries: tuple[Entry, ...] = ()
    # Names of the variables macros of this profile may use.
    variables: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "version": FORMAT_VERSION,
            "variables": list(self.variables),
            "entries": [e.to_json() for e in self.entries],
        }

    @staticmethod
    def from_json(name: str, data: dict[str, Any]) -> Profile:
        if data.get("version", 1) > FORMAT_VERSION:
            raise ValueError(f'Profile "{name}" was saved by a newer version')
        return Profile(
            name=name,
            entries=tuple(Entry.from_json(e) for e in data.get("entries", [])),
            variables=tuple(data.get("variables", [])),
        )

    # Edits. Each returns a new Profile.

    def with_entry(self, entry: Entry) -> Profile:
        """Replace the entry with the same id, or append if it is new."""
        for index, existing in enumerate(self.entries):
            if existing.id == entry.id:
                entries = self.entries[:index] + (entry,) + self.entries[index + 1 :]
                return replace(self, entries=entries)
        return replace(self, entries=self.entries + (entry,))

    def without_entry(self, entry_id: str) -> Profile:
        return replace(self, entries=tuple(e for e in self.entries if e.id != entry_id))

    def moved_entry(self, entry_id: str, new_index: int) -> Profile:
        entries = list(self.entries)
        index = next(i for i, e in enumerate(entries) if e.id == entry_id)
        entries.insert(new_index, entries.pop(index))
        return replace(self, entries=tuple(entries))

    def get_entry(self, entry_id: str) -> Entry | None:
        return next((e for e in self.entries if e.id == entry_id), None)


@dataclass(frozen=True)
class Workspace:
    """All profiles. This is the unit that undo and redo snapshot."""

    profiles: tuple[Profile, ...] = ()

    def get(self, name: str) -> Profile | None:
        return next((p for p in self.profiles if p.name == name), None)

    def with_profile(self, profile: Profile) -> Workspace:
        for index, existing in enumerate(self.profiles):
            if existing.name == profile.name:
                profiles = (
                    self.profiles[:index] + (profile,) + self.profiles[index + 1 :]
                )
                return replace(self, profiles=profiles)
        return replace(self, profiles=self.profiles + (profile,))

    def without_profile(self, name: str) -> Workspace:
        return replace(self, profiles=tuple(p for p in self.profiles if p.name != name))

    def renamed_profile(self, old: str, new: str) -> Workspace:
        if self.get(new) is not None:
            raise ValueError(f'A profile named "{new}" already exists')
        profiles = tuple(
            replace(p, name=new) if p.name == old else p for p in self.profiles
        )
        return replace(self, profiles=profiles)

    def copied_profile(self, name: str, new_name: str) -> Workspace:
        """Duplicate a profile. Entries get fresh ids."""
        source = self.get(name)
        if source is None:
            raise KeyError(name)
        if self.get(new_name) is not None:
            raise ValueError(f'A profile named "{new_name}" already exists')
        entries = tuple(replace(e, id=_new_id()) for e in source.entries)
        return self.with_profile(replace(source, name=new_name, entries=entries))
