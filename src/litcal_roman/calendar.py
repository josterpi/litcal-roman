"""
litcal_roman.calendar
~~~~~~~~~~~~~~~~~~~~~

Orchestrates the Roman Catholic liturgical calendar by merging the moveable
cycle (temporale) with fixed-date saints (sanctorale) and resolving precedence
according to GNLYC §§58–59.

Public API
----------
get_liturgical_day(d, config) -> LiturgicalDay
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
from typing import Optional

from .models import (
    CalendarConfig,
    Celebration,
    CelebrationKind,
    LiturgicalColor,
    LiturgicalDay,
    Rank,
    Season,
)
from .sanctorale import get_sanctorale_celebrations
from .temporale import compute_temporale, get_anchors


# ---------------------------------------------------------------------------
# Transfer helpers
# ---------------------------------------------------------------------------

def _annunciation_effective_date(year: int) -> date:
    """
    Annunciation (03-25) transfers to the Monday after the Easter Octave when
    it falls in Holy Week or the Easter Octave (GNLYC §60).
    """
    anchors = get_anchors(year)
    ann = date(year, 3, 25)
    # Holy Week (Palm Sunday = Easter-7) through 2nd Sunday of Easter (Easter+7)
    if anchors.easter - timedelta(days=7) <= ann <= anchors.easter + timedelta(days=7):
        return anchors.easter + timedelta(days=8)
    return ann


def _ic_effective_date(year: int) -> date:
    """
    Immaculate Conception (12-08) transfers to 12-09 when it falls on the
    2nd Sunday of Advent.
    """
    anchors = get_anchors(year)
    ic = date(year, 12, 8)
    advent_2 = anchors.advent_1 + timedelta(weeks=1)
    if ic == advent_2:
        return date(year, 12, 9)
    return ic


@lru_cache(maxsize=16)
def _build_transfer_map(year: int) -> dict[date, date]:
    """
    Return a {proper_date: effective_date} mapping for all celebrations that
    transfer in *year*. Only entries where effective ≠ proper are included.
    """
    transfers: dict[date, date] = {}

    ann_proper = date(year, 3, 25)
    ann_effective = _annunciation_effective_date(year)
    if ann_effective != ann_proper:
        transfers[ann_proper] = ann_effective

    ic_proper = date(year, 12, 8)
    ic_effective = _ic_effective_date(year)
    if ic_effective != ic_proper:
        transfers[ic_proper] = ic_effective

    as_proper = date(year, 11, 2)
    if as_proper.isoweekday() == 7:
        transfers[as_proper] = date(year, 11, 3)

    return transfers


def _get_effective_sanctorale(d: date, config: CalendarConfig) -> list[Celebration]:
    """
    Return sanctorale celebrations for *d* after applying transfer rules.

    Celebrations transferred away from *d* are excluded; celebrations
    transferred from other proper dates to *d* are included.
    """
    transfers = _build_transfer_map(d.year)
    result: list[Celebration] = []

    # Today's celebrations, unless today is a transfer-out date
    if d not in transfers:
        result.extend(get_sanctorale_celebrations(d, config))

    # Celebrations whose proper date is being redirected to today
    for proper_date, effective_date in transfers.items():
        if effective_date == d:
            result.extend(get_sanctorale_celebrations(proper_date, config))

    return result


# ---------------------------------------------------------------------------
# Feria color
# ---------------------------------------------------------------------------

def _feria_color(season: Season) -> LiturgicalColor:
    match season:
        case Season.ADVENT | Season.LENT:
            return LiturgicalColor.VIOLET
        case Season.EASTER | Season.CHRISTMAS:
            return LiturgicalColor.WHITE
        case _:
            return LiturgicalColor.GREEN


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_liturgical_day(d: date, config: CalendarConfig) -> LiturgicalDay:
    """
    Return the fully resolved LiturgicalDay for civil date *d* under *config*.

    Merges temporale and sanctorale, applies GNLYC transfer rules, and
    resolves precedence so the returned day has exactly one winning
    celebration and zero or more displaced ones.
    """
    t = compute_temporale(d, config)

    season: Season                   = t["season"]
    week: int                        = t["week"]
    weekday: int                     = t["weekday"]
    psalter_week: int                = t["psalter_week"]
    label: str                       = t["label"]
    temp_cel: Optional[Celebration]  = t["celebration"]

    # Easter Octave (season=Easter, week=1): sanctorale is entirely suppressed.
    # All eight days carry SOLEMNITY-rank-or-higher temporale celebrations and
    # the Octave is treated as a unified celebration (GNLYC §24).
    if season == Season.EASTER and week == 1:
        sanctorale: list[Celebration] = []
    else:
        sanctorale = _get_effective_sanctorale(d, config)

    # Build candidate list: temporale celebration (or feria baseline) + sanctorale
    if temp_cel is not None:
        candidates: list[Celebration] = [temp_cel, *sanctorale]
    else:
        feria = Celebration(
            name=label,
            rank=Rank.FERIA,
            kind=CelebrationKind.TEMPORALE,
            color=_feria_color(season),
        )
        candidates = [feria, *sanctorale]

    # Precedence: sort descending by rank; first entry wins (stable for ties)
    sorted_candidates = sorted(candidates, key=lambda c: c.rank, reverse=True)
    winner = sorted_candidates[0]
    displaced = tuple(sorted_candidates[1:])

    return LiturgicalDay(
        date=d,
        season=season,
        week=week,
        weekday=weekday,
        psalter_week=psalter_week,
        celebration=winner,
        displaced=displaced,
        scripture_cycle=t["scripture_cycle"],
        sunday_cycle=t["sunday_cycle"],
        region=config.region,
    )
