#!/usr/bin/python3
# -*- coding: utf-8 -*-
# input-remapper - GUI for device specific keyboard mappings
# Copyright (C) 2022 sezanzeb <proxima@sezanzeb.de>
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

"""Contains and manages mappings."""

from __future__ import annotations

import os
import json

from typing import (
    Tuple,
    Dict,
    List,
    Optional,
    Iterator,
    Type,
    TypeVar,
    Generic,
    overload,
)

from pydantic import ValidationError
from inputremapper.logger import logger
from inputremapper.configs.mapping import Mapping, UIMapping
from inputremapper.configs.paths import touch

from inputremapper.input_event import InputEvent
from inputremapper.event_combination import EventCombination


MappingModel = TypeVar("MappingModel", bound=UIMapping)


class Preset(Generic[MappingModel]):
    """Contains and manages mappings of a single preset."""

    # workaround for typing: https://github.com/python/mypy/issues/4236
    @overload
    def __init__(self: Preset[Mapping], path: Optional[os.PathLike] = None):
        ...

    @overload
    def __init__(
        self,
        path: Optional[os.PathLike] = None,
        mapping_factory: Type[MappingModel] = ...,
    ):
        ...

    def __init__(
        self,
        path: Optional[os.PathLike] = None,
        mapping_factory=Mapping,
    ) -> None:
        self._mappings: Dict[EventCombination, MappingModel] = {}
        # a copy of mappings for keeping track of changes
        self._saved_mappings: Dict[EventCombination, MappingModel] = {}
        self._path: Optional[os.PathLike] = path

        # the mapping class which is used by load()
        self._mapping_factory: Type[MappingModel] = mapping_factory

    def __iter__(self) -> Iterator[MappingModel]:
        """Iterate over Mapping objects."""
        return iter(self._mappings.values())

    def __len__(self) -> int:
        return len(self._mappings)

    def __bool__(self):
        # otherwise __len__ will be used which results in False for a preset
        # without mappings
        return True

    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changed."""
        return self._mappings != self._saved_mappings

    def remove(self, combination: EventCombination) -> None:
        """Remove a mapping from the preset by providing the EventCombination."""

        if not isinstance(combination, EventCombination):
            raise TypeError(
                f"combination must by of type EventCombination, got {type(combination)}"
            )

        for permutation in combination.get_permutations():
            if permutation in self._mappings.keys():
                combination = permutation
                break
        try:
            mapping = self._mappings.pop(combination)
            mapping.remove_combination_changed_callback()
        except KeyError:
            logger.debug(
                "unable to remove non-existing mapping with combination = %s",
                combination,
            )
            pass

    def add(self, mapping: MappingModel) -> None:
        """Add a mapping to the preset."""
        for permutation in mapping.event_combination.get_permutations():
            if permutation in self._mappings:
                raise KeyError(
                    "A mapping with this event_combination: "
                    f"{permutation} already exists",
                )

        mapping.set_combination_changed_callback(self._combination_changed_callback)
        self._mappings[mapping.event_combination] = mapping

    def empty(self) -> None:
        """Remove all mappings and custom configs without saving.
        note: self.has_unsaved_changes() will report True
        """
        for mapping in self._mappings.values():
            mapping.remove_combination_changed_callback()
        self._mappings = {}

    def clear(self) -> None:
        """Remove all mappings and also self.path."""
        self.empty()
        self._saved_mappings = {}
        self.path = None

    def load(self) -> None:
        """Load from the mapping from the disc, clears all existing mappings."""
        logger.info('Loading preset from "%s"', self.path)

        if not self.path or not os.path.exists(self.path):
            raise FileNotFoundError(f'Tried to load non-existing preset "{self.path}"')

        self._saved_mappings = self._get_mappings_from_disc()
        self.empty()
        for mapping in self._saved_mappings.values():
            # use the public add method to make sure
            # the _combination_changed_callback is attached
            self.add(mapping.copy())

    def _is_mapped_multiple_times(self, event_combination: EventCombination) -> bool:
        """Check if the event combination maps to multiple mappings."""
        all_input_combinations = {mapping.event_combination for mapping in self}
        permutations = set(event_combination.get_permutations())
        union = permutations & all_input_combinations
        # if there are more than one matches, then there is a duplicate
        return len(union) > 1

    def _has_valid_event_combination(self, mapping: UIMapping) -> bool:
        """Check if the mapping has a valid input event combination."""
        is_a_combination = isinstance(mapping.event_combination, EventCombination)
        is_empty = mapping.event_combination == EventCombination.empty_combination()
        return is_a_combination and not is_empty

    def save(self) -> None:
        """Dump as JSON to self.path."""

        if not self.path:
            logger.debug("unable to save preset without a path set Preset.path first")
            return

        touch(self.path)
        if not self.has_unsaved_changes():
            logger.debug("Not saving unchanged preset")
            return

        logger.info("Saving preset to %s", self.path)

        preset_dict = {}
        saved_mappings = {}
        for mapping in self:
            if not mapping.is_valid():
                if not self._has_valid_event_combination(mapping):
                    # we save invalid mappings except for those with an invalid
                    # event_combination
                    logger.debug("skipping invalid mapping %s", mapping)
                    continue

                if self._is_mapped_multiple_times(mapping.event_combination):
                    logger.debug(
                        "skipping mapping with duplicate event combination %s",
                        mapping,
                    )
                    continue

            mapping_dict = mapping.dict(exclude_defaults=True)
            combination = mapping.event_combination
            if "event_combination" in mapping_dict:
                # used as key, don't store it redundantly
                del mapping_dict["event_combination"]
            preset_dict[combination.json_key()] = mapping_dict

            saved_mappings[combination] = mapping.copy()
            saved_mappings[combination].remove_combination_changed_callback()

        with open(self.path, "w") as file:
            json.dump(preset_dict, file, indent=4)
            file.write("\n")

        self._saved_mappings = saved_mappings

    def is_valid(self) -> bool:
        return False not in [mapping.is_valid() for mapping in self]

    def get_mapping(
        self, combination: Optional[EventCombination]
    ) -> Optional[MappingModel]:
        """Return the Mapping that is mapped to this EventCombination."""
        if not combination:
            return None

        if not isinstance(combination, EventCombination):
            raise TypeError(
                f"combination must by of type EventCombination, got {type(combination)}"
            )

        for permutation in combination.get_permutations():
            existing = self._mappings.get(permutation)
            if existing is not None:
                return existing

        return None

    def dangerously_mapped_btn_left(self) -> bool:
        """Return True if this mapping disables BTN_Left."""
        if EventCombination(InputEvent.btn_left()) not in [
            m.event_combination for m in self
        ]:
            return False

        values: List[str | Tuple[int, int] | None] = []
        for mapping in self:
            if mapping.output_symbol is None:
                continue
            values.append(mapping.output_symbol.lower())
            values.append(mapping.get_output_type_code())

        return (
            "btn_left" not in values
            or InputEvent.btn_left().type_and_code not in values
        )

    def _combination_changed_callback(
        self, new: EventCombination, old: EventCombination
    ) -> None:
        for permutation in new.get_permutations():
            if permutation in self._mappings.keys() and permutation != old:
                raise KeyError("combination already exists in the preset")
        self._mappings[new] = self._mappings.pop(old)

    def _update_saved_mappings(self) -> None:
        if self.path is None:
            return

        if not os.path.exists(self.path):
            self._saved_mappings = {}
            return
        self._saved_mappings = self._get_mappings_from_disc()

    def _get_mappings_from_disc(self) -> Dict[EventCombination, MappingModel]:
        mappings: Dict[EventCombination, MappingModel] = {}
        if not self.path:
            logger.debug("unable to read preset without a path set Preset.path first")
            return mappings

        if os.stat(self.path).st_size == 0:
            logger.debug("got empty file")
            return mappings

        with open(self.path, "r") as file:
            try:
                preset_dict = json.load(file)
            except json.JSONDecodeError:
                logger.error("unable to decode json file: %s", self.path)
                return mappings

        for combination, mapping_dict in preset_dict.items():
            try:
                mapping = self._mapping_factory(
                    event_combination=combination, **mapping_dict
                )
            except ValidationError as error:
                logger.error(
                    "failed to Validate mapping for %s: %s",
                    combination,
                    error,
                )
                continue

            mappings[mapping.event_combination] = mapping
        return mappings

    @property
    def path(self) -> Optional[os.PathLike]:
        return self._path

    @path.setter
    def path(self, path: Optional[os.PathLike]):
        if path != self.path:
            self._path = path
            self._update_saved_mappings()

    @property
    def name(self) -> Optional[str]:
        """The name of the preset."""
        if self.path:
            return os.path.basename(self.path).split(".")[0]
        return None
