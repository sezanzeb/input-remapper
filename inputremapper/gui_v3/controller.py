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


"""All the behaviour of the beta GUI, without any GTK.

The window only displays what is here and forwards user actions. That keeps every
action testable, and routes all edits through one place, so undo covers all of them.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Collection, Hashable, Iterable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from inputremapper.configs.paths import PathUtils
from inputremapper.gui_v3.document import Entry, InputRef, Profile, Workspace
from inputremapper.gui_v3.recorder import RecorderError
from inputremapper.gui_v3.render import (
    RENDERED_PREFIX,
    RenderError,
    import_preset_file,
    is_rendered_name,
    write_rendered,
)
from inputremapper.gui_v3.store import load_workspace, save_workspace
from inputremapper.gui_v3.tree import variables_used
from inputremapper.gui_v3.undo import History
from inputremapper.logging.logger import logger


class GroupLike(Protocol):
    key: str
    name: str


class GroupsLike(Protocol):
    def get_groups(self) -> Sequence[GroupLike]: ...


class RecorderLike(Protocol):
    @property
    def recording(self) -> bool: ...

    def start(
        self,
        group_key: str | None,
        on_update: Callable[[tuple[InputRef, ...], str], None],
        on_done: Callable[[], None],
    ) -> None: ...

    def stop(self) -> None: ...


class DaemonLike(Protocol):
    def start_injecting(self, group_key: str, preset: str) -> bool: ...

    def stop_all(self) -> None: ...

    def set_config_dir(self, config_dir: str) -> None: ...

    def get_state(self, group_key: str) -> str: ...

    def get_running_preset(self, group_key: str) -> str: ...


@dataclass(frozen=True)
class V1Preset:
    group_key: str
    group_name: str
    name: str
    path: Path


def unique_name(base: str, taken: Collection[str]) -> str:
    """`base`, or "base 2", "base 3", ... if that is taken."""
    if base not in taken:
        return base
    number = 2
    while f"{base} {number}" in taken:
        number += 1
    return f"{base} {number}"


VARIABLE_NAME = re.compile(r"^[A-Za-z_]\w*$")
RECORD_BLOCKED_MESSAGE = "Stop the running profile to record input"


class Controller:
    def __init__(
        self,
        daemon: DaemonLike | None,
        groups: GroupsLike,
        profiles_dir: Path,
        presets_dir: str | os.PathLike[str] | None = None,
        workspace: Workspace | None = None,
        recorder: RecorderLike | None = None,
    ) -> None:
        self.recorder = recorder
        self.daemon = daemon
        self.groups = groups
        self.profiles_dir = profiles_dir
        self.presets_dir = presets_dir

        loaded = workspace if workspace is not None else load_workspace(profiles_dir)
        self._history = History(loaded)
        self._saved = loaded

        # Selection and the running profile are not undoable.
        self.selected_profile: str | None = (
            loaded.profiles[0].name if loaded.profiles else None
        )
        self.selected_entry: str | None = None
        self.active_profile: str | None = None
        # Something the service runs that isn't one of our profiles, for example an
        # autoloaded v1 preset.
        self.other_running = False
        self.message: str = ""
        # A problem the user must acknowledge, shown as a dialog by the window.
        self.error: str | None = None

        self._listeners: list[Callable[[], None]] = []

    # State ---------------------------------------------------------------------

    @property
    def workspace(self) -> Workspace:
        return self._history.current

    @property
    def profile(self) -> Profile | None:
        if self.selected_profile is None:
            return None
        return self.workspace.get(self.selected_profile)

    @property
    def entry(self) -> Entry | None:
        profile = self.profile
        if profile is None or self.selected_entry is None:
            return None
        return profile.get_entry(self.selected_entry)

    @property
    def can_undo(self) -> bool:
        return self._history.can_undo

    @property
    def can_redo(self) -> bool:
        return self._history.can_redo

    def subscribe(self, listener: Callable[[], None]) -> None:
        self._listeners.append(listener)

    @property
    def recording(self) -> bool:
        return self.recorder is not None and self.recorder.recording

    @property
    def running(self) -> bool:
        """Whether the service runs anything at all, ours or not."""
        return self.active_profile is not None or self.other_running

    @property
    def can_record(self) -> bool:
        """A running profile grabs its devices, so nothing can be read from them."""
        return not self.running

    def sync_running(self) -> None:
        """Ask the service what runs, because it may have been started elsewhere:
        autoload, the old GUI, or an earlier session of this one."""
        if self.daemon is None:
            return
        # {group key: preset name, or "" if the service can't say which}
        running: dict[str, str] = {}
        try:
            for group in self.groups.get_groups():
                name = self._running_preset(group.key)
                if name is not None:
                    running[group.key] = name
        except Exception:  # a dbus hiccup shouldn't lose what we already know
            return

        active = self._active_profile_for(running)
        other = bool(running) and active is None
        if (active, other) != (self.active_profile, self.other_running):
            logger.info(
                "Running presets %s: v3 profile %s%s",
                running or "none",
                active or "none",
                ", plus others" if other else "",
            )
            self.active_profile, self.other_running = active, other
            self._changed()

    def _running_preset(self, group_key: str) -> str | None:
        """The preset running on that group ("" if unknown), or None if none."""
        assert self.daemon is not None
        try:
            name = self.daemon.get_running_preset(group_key)
        except Exception:  # older services don't have this method
            name = ""
        if name:
            return name
        state = str(self.daemon.get_state(group_key))
        return "" if state in ("RUNNING", "STARTING") else None

    def _active_profile_for(self, running: dict[str, str]) -> str | None:
        """Which of our profiles is what's running, if any."""
        if not running:
            return None
        named = {n[len(RENDERED_PREFIX) :] for n in running.values() if n}
        if all(running.values()):
            # The service told us every name; they must all be one of ours.
            if len(named) == 1 and all(is_rendered_name(n) for n in running.values()):
                (only,) = named
                return only if self.workspace.get(only) is not None else None
            return None
        # Names unknown: the profile that covers exactly these devices.
        matches = [
            p.name
            for p in self.workspace.profiles
            if self._devices_of(p) == set(running)
        ]
        if self.selected_profile in matches:
            return self.selected_profile
        return matches[0] if len(matches) == 1 else None

    def _devices_of(self, profile: Profile) -> set[str]:
        """The connected devices the profile has mappings for. Doesn't render, so a
        profile with a half-finished mapping still matches."""
        return {
            e.trigger.device
            for e in profile.entries
            if e.trigger.device and self._group_name_of(e.trigger.device) is not None
        }

    def _changed(self) -> None:
        # Selections may point at things that undo or delete removed.
        if self.profile is None:
            names = [p.name for p in self.workspace.profiles]
            self.selected_profile = names[0] if names else None
        if self.entry is None:
            self.selected_entry = None
        if self.active_profile and self.workspace.get(self.active_profile) is None:
            self.active_profile = None
        for listener in list(self._listeners):
            listener()

    # Editing -------------------------------------------------------------------

    def edit(
        self,
        change: Callable[[Workspace], Workspace],
        merge_key: Hashable | None = None,
    ) -> None:
        """Apply an edit to the workspace. One call is one undo step."""
        try:
            new = change(self.workspace)
        except (ValueError, KeyError) as error:
            self.message = str(error)
            self._changed()
            return
        self.message = ""
        if self._history.commit(new, merge_key):
            self._save()
        self._changed()

    def edit_profile(
        self,
        change: Callable[[Profile], Profile],
        merge_key: Hashable | None = None,
    ) -> None:
        name = self.selected_profile
        if name is None:
            return

        def apply(workspace: Workspace) -> Workspace:
            profile = workspace.get(name)
            if profile is None:
                raise KeyError(name)
            return workspace.with_profile(change(profile))

        self.edit(apply, merge_key)

    def edit_entry(
        self,
        change: Callable[[Entry], Entry],
        merge_key: Hashable | None = None,
    ) -> None:
        entry_id = self.selected_entry
        if entry_id is None:
            return

        def apply(profile: Profile) -> Profile:
            entry = profile.get_entry(entry_id)
            if entry is None:
                raise KeyError(entry_id)
            return profile.with_entry(change(entry))

        self.edit_profile(
            apply, merge_key=("entry", entry_id, merge_key) if merge_key else None
        )

    def undo(self) -> None:
        self.stop_recording()
        if self._history.undo():
            self._save()
        self._changed()

    def redo(self) -> None:
        self.stop_recording()
        if self._history.redo():
            self._save()
        self._changed()

    def _save(self) -> None:
        save_workspace(self.workspace, self.profiles_dir, previous=self._saved)
        self._saved = self.workspace

    # Profiles ------------------------------------------------------------------

    def _taken_names(self) -> list[str]:
        return [p.name for p in self.workspace.profiles]

    def new_profile(self) -> None:
        name = unique_name("New profile", self._taken_names())
        self.selected_profile = name
        self.edit(lambda w: w.with_profile(Profile(name=name)))
        self.selected_profile = name
        self._changed()

    def copy_profile(self) -> None:
        source = self.selected_profile
        if source is None:
            return
        name = unique_name(f"{source} copy", self._taken_names())
        self.edit(lambda w: w.copied_profile(source, name))
        self.selected_profile = name
        self._changed()

    def delete_profile(self) -> None:
        name = self.selected_profile
        if name is None:
            return
        if name == self.active_profile:
            self.stop()
        self.edit(lambda w: w.without_profile(name))

    def rename_profile(self, new_name: str) -> None:
        old = self.selected_profile
        new_name = new_name.strip()
        if old is None or not new_name or new_name == old:
            return
        was_active = self.active_profile == old
        self.edit(lambda w: w.renamed_profile(old, new_name))
        if self.workspace.get(old) is None:
            self.selected_profile = new_name
            if was_active:
                self.active_profile = new_name
        self._changed()

    def select_profile(self, name: str | None) -> None:
        self.stop_recording()
        self.selected_profile = name
        self.selected_entry = None
        self._changed()

    def set_variables(self, names: Iterable[str]) -> None:
        cleaned: list[str] = []
        for name in names:
            name = name.strip()
            if name and name not in cleaned:
                cleaned.append(name)
        self.edit_profile(lambda p: replace(p, variables=tuple(cleaned)))

    def add_variable(self, name: str) -> None:
        """Declare a variable (a leading `$` is fine) unless it already is."""
        name = name.strip().lstrip("$")
        profile = self.profile
        if profile is None or not VARIABLE_NAME.match(name):
            return
        if name not in profile.variables:
            self.set_variables([*profile.variables, name])

    # Entries -------------------------------------------------------------------

    def select_entry(self, entry_id: str | None) -> None:
        if entry_id != self.selected_entry:
            self.stop_recording()
        self.selected_entry = entry_id
        self._changed()

    def new_entry(self) -> None:
        entry = Entry()
        self.edit_profile(lambda p: p.with_entry(entry))
        self.selected_entry = entry.id
        self._changed()

    def delete_entry(self, entry_id: str) -> None:
        self.edit_profile(lambda p: p.without_entry(entry_id))

    # Recording -----------------------------------------------------------------

    def start_recording(self) -> None:
        """Record the trigger keys of the selected entry.

        Always listens to every device, whatever the entry's device is now, and sets
        the entry's device to the one the keys were pressed on.
        """
        entry = self.entry
        if entry is None:
            return
        self.sync_running()
        if not self.can_record:
            self.message = RECORD_BLOCKED_MESSAGE
        elif self.recorder is None:
            self.message = "Recording is not available"
        else:
            self.message = "Press the keys now, release them all to finish"
            try:
                self.recorder.start(None, self._recorded, self._recording_done)
            except RecorderError as error:
                self.message = str(error)
        self._changed()

    def stop_recording(self) -> None:
        if self.recorder is not None and self.recorder.recording:
            self.recorder.stop()
            self.message = ""
            self._changed()

    def toggle_recording(self) -> None:
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def _recorded(self, inputs: tuple[InputRef, ...], group_key: str) -> None:
        # Each key added to the combination coalesces into one undo step.
        self.edit_entry(
            lambda e: replace(
                e,
                trigger=replace(e.trigger, inputs=inputs, device=group_key),
            ),
            merge_key="record",
        )

    def _recording_done(self) -> None:
        self.message = ""
        self._changed()

    # Import --------------------------------------------------------------------

    def list_v1_presets(self) -> list[V1Preset]:
        """Presets of the old UI, for the import menu. Generated ones are left out."""
        base = Path(self.presets_dir or PathUtils.get_preset_path())
        found: list[V1Preset] = []
        for group in self.groups.get_groups():
            directory = base / PathUtils.sanitize_path_component(group.name)
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.json")):
                if is_rendered_name(path.stem):
                    continue
                found.append(V1Preset(group.key, group.name, path.stem, path))
        return found

    def import_v1(self, preset: V1Preset) -> None:
        try:
            entries = import_preset_file(preset.path, preset.group_key)
        except (OSError, ValueError) as error:
            self.message = f'Could not import "{preset.name}": {error}'
            self._changed()
            return

        def add_entries(profile: Profile) -> Profile:
            # Variables the imported macros use are declared for the profile.
            variables = list(profile.variables)
            for entry in entries:
                for name in variables_used(entry.then):
                    if name not in variables:
                        variables.append(name)
            return replace(
                profile,
                entries=profile.entries + tuple(entries),
                variables=tuple(variables),
            )

        self.edit_profile(add_entries)
        if entries:
            self.selected_entry = entries[0].id
            self._changed()

    # Running -------------------------------------------------------------------

    def _group_name_of(self, group_key: str) -> str | None:
        for group in self.groups.get_groups():
            if group.key == group_key:
                return group.name
        return None

    def apply(self) -> None:
        """Start the selected profile, stopping whichever one ran before."""
        profile = self.profile
        if profile is None:
            return
        if self.daemon is None:
            self.message = "The input-remapper service is not running"
            self._changed()
            return
        try:
            started = write_rendered(profile, self._group_name_of, self.presets_dir)
        except RenderError as error:
            if error.entry_id is not None:
                # Show the offending mapping, and say what is wrong with it.
                self.selected_entry = error.entry_id
                self.error = f"In this mapping, {error}."
                self.message = ""
            else:
                self.message = str(error)
            self._changed()
            return

        # The service forgets which user it works for when it restarts, and then
        # refuses to start anything. Telling it again is cheap.
        base = Path(self.presets_dir or PathUtils.get_preset_path())
        self.daemon.set_config_dir(str(base.parent))

        # stop_all, not set_suspended: suspended injections would queue up.
        self.daemon.stop_all()
        failed = [
            key
            for key, preset in started.items()
            if not self.daemon.start_injecting(key, preset)
        ]
        if failed:
            self.error = (
                "Could not start for: "
                + ", ".join(failed)
                + ". The input-remapper service refused; see its log "
                "(journalctl -u input-remapper) for why."
            )
            self.message = ""
        elif not started:
            self.message = "None of this profile's devices are connected"
        else:
            self.message = ""
        self.active_profile = profile.name if started else None
        self._changed()

    def dismiss_error(self) -> None:
        self.error = None

    def stop(self) -> None:
        if self.daemon is not None:
            self.daemon.stop_all()
        self.active_profile = None
        self.other_running = False
        self.message = ""
        self._changed()

    def toggle_apply(self) -> None:
        if self.running:
            self.stop()
        else:
            self.apply()
