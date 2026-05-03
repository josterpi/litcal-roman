"""
litcal_roman.sanctorale
~~~~~~~~~~~~~~~~~~~~~~~

Loads and queries the fixed-date sanctorale (saints' calendar) for the
Roman Catholic liturgical calendar (Ordinary Form).

Each supported region is backed by a YAML data file in the ``data/``
directory alongside this module.  The universal General Roman Calendar
is ``data/universal.yaml``; regional files (e.g. ``data/us.yaml``) add
celebrations on top of the universal layer.

Data files list one entry per celebration.  Multiple entries with the
same date represent distinct (typically optional) memorials that share
that date.

Precedence resolution — deciding which celebration *wins* on a given
day — is the caller's responsibility (the future Calendar orchestrator).
This module only answers "what is scheduled for this date?".
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

from .models import (
    CalendarConfig,
    Celebration,
    CelebrationKind,
    LiturgicalColor,
    Rank,
)

_DATA_DIR = Path(__file__).parent / "data"

_RANK_MAP: dict[str, Rank] = {
    "solemnity":        Rank.SOLEMNITY,
    "lord_feast":       Rank.LORD_FEAST,
    "feast":            Rank.FEAST,
    "memorial":         Rank.MEMORIAL,
    "optional_memorial": Rank.OPTIONAL_MEMORIAL,
}

_COLOR_MAP: dict[str, LiturgicalColor] = {
    "white":  LiturgicalColor.WHITE,
    "red":    LiturgicalColor.RED,
    "green":  LiturgicalColor.GREEN,
    "violet": LiturgicalColor.VIOLET,
    "rose":   LiturgicalColor.ROSE,
    "black":  LiturgicalColor.BLACK,
}


@lru_cache(maxsize=8)
def _load(region: str) -> dict[tuple[int, int], list[Celebration]]:
    """
    Parse ``data/<region>.yaml`` into a (month, day) → [Celebration] map.
    Cached so each region file is read only once per process.
    """
    path = _DATA_DIR / f"{region}.yaml"
    with path.open(encoding="utf-8") as f:
        entries = yaml.safe_load(f) or []

    kind = (
        CelebrationKind.SANCTORALE_UNIVERSAL
        if region == "universal"
        else CelebrationKind.SANCTORALE_REGIONAL
    )

    result: dict[tuple[int, int], list[Celebration]] = {}
    for entry in entries:
        month, day = map(int, entry["date"].split("-"))
        rank  = _RANK_MAP[entry["rank"]]
        color = _COLOR_MAP[entry["color"]]
        celebration = Celebration(
            name     = entry["name"],
            rank     = rank,
            kind     = kind,
            color    = color,
            optional = (rank == Rank.OPTIONAL_MEMORIAL),
        )
        result.setdefault((month, day), []).append(celebration)

    return result


def get_sanctorale_celebrations(
    d: date,
    config: CalendarConfig,
) -> list[Celebration]:
    """
    Return every sanctorale celebration scheduled for *d* under *config*.

    Always includes universal GRC entries.  If ``config.region`` is not
    ``"universal"`` and a corresponding data file exists, regional
    celebrations are appended after the universal ones.

    Returns an empty list for dates with no sanctorale entry.
    """
    key = (d.month, d.day)
    celebrations: list[Celebration] = list(_load("universal").get(key, []))

    if config.region != "universal":
        try:
            celebrations.extend(_load(config.region).get(key, []))
        except FileNotFoundError:
            pass

    return celebrations
