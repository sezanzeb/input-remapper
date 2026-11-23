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

"""Matching and ranking for the search popovers (blocks and keys). No GTK."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

# Where a name's words start: after an underscore, a space, a slash or a dash.
_WORD_BREAK = re.compile(r"[_ /\-]+")


@dataclass(frozen=True)
class Item:
    """One thing to find. `aliases` are other words that find it."""

    value: str
    label: str
    group: str
    aliases: str = ""


def search(items: Sequence[Item], query: str) -> list[tuple[str, list[Item]]]:
    """The matches by group, best first.

    Every word of the query has to match. A word matches the label best when the
    label starts with it, then when a word of the label does (the rest of the label
    from there on starts with it, so "left_sh" finds KEY_LEFT_SHIFT), then when a
    word of an alias does, then when the label contains it, and last when an alias
    does. Ties go to the earlier word, then the shorter label, then the label.

    A group is as good as its best match, and comes first for it; ties keep the
    order the groups were given in. Without a query everything is listed as given.
    """
    words = query.lower().split()
    groups: dict[str, list[tuple[tuple[int, int, int, str], Item]]] = {}
    for item in items:
        rank = _rank(item, words)
        if rank is not None:
            groups.setdefault(item.group, []).append((rank, item))

    if not words:
        return [(group, [i for _r, i in found]) for group, found in groups.items()]

    ordered = [
        (group, sorted(found, key=lambda f: f[0])) for group, found in groups.items()
    ]
    ordered.sort(key=lambda g: g[1][0][0][:3])  # stable: ties keep the group order
    return [(group, [i for _r, i in found]) for group, found in ordered]


def rank_labels(labels: Iterable[str], query: str) -> list[str]:
    """Just the labels that match, best first (see `search`)."""
    found = search([Item(label, label, "") for label in labels], query)
    return [item.label for _group, items in found for item in items]


def _rank(item: Item, words: list[str]) -> tuple[int, int, int, str] | None:
    if not words:
        return (0, 0, len(item.label), item.label)
    tiers: list[tuple[int, int]] = []
    for word in words:
        tier = _word_tier(item, word)
        if tier is None:
            return None
        tiers.append(tier)
    worst_tier = max(t for t, _ in tiers)
    worst_word = max(w for _, w in tiers)
    return (worst_tier, worst_word, len(item.label), item.label)


def _word_tier(item: Item, word: str) -> tuple[int, int] | None:
    label, aliases = item.label.lower(), item.aliases.lower()
    starts = _starts(label)
    for index, start in enumerate(starts):
        if label[start:].startswith(word):
            return (0, 0) if index == 0 else (1, index)
    for index, start in enumerate(_starts(aliases)):
        if aliases[start:].startswith(word):
            return (2, index)
    if word in label:
        return (3, label.index(word))
    if word in aliases:
        return (4, aliases.index(word))
    return None


def _starts(text: str) -> list[int]:
    """The positions where the words of a text start."""
    starts = [0] if text else []
    starts.extend(
        match.end() for match in _WORD_BREAK.finditer(text) if match.end() < len(text)
    )
    return starts
