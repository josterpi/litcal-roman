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

from dataclasses import replace
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
# Color helpers
# ---------------------------------------------------------------------------

def _feria_color(season: Season) -> LiturgicalColor:
    match season:
        case Season.ADVENT | Season.LENT:
            return LiturgicalColor.VIOLET
        case Season.EASTER | Season.CHRISTMAS:
            return LiturgicalColor.WHITE
        case _:
            return LiturgicalColor.GREEN


def _resolve_color(winner: Celebration, season: Season) -> LiturgicalColor:
    """
    Return the effective vestment colour for the winning celebration.

    Feasts and above always keep their proper colour.  For lower ranks,
    the season overrides the celebration's stored colour per GIRM §346:
    - Optional memorials take the season colour (the Mass follows the feria).
    - Obligatory memorials use Violet during Lent and Advent.
    """
    if winner.rank >= Rank.FEAST:
        return winner.color
    if winner.rank == Rank.OPTIONAL_MEMORIAL:
        return _feria_color(season)
    if winner.rank == Rank.MEMORIAL and season == Season.LENT:
        return LiturgicalColor.VIOLET
    return winner.color


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

    # Sanctorale is suppressed on Holy Week Mon–Wed and during the Easter Octave
    # (GNLYC §60c, §24).
    anchors = get_anchors(d.year)
    holy_week_start = anchors.palm_sunday + timedelta(days=1)
    holy_week_end   = anchors.holy_thursday - timedelta(days=1)
    in_suppressed = (
        (season == Season.EASTER and week == 1)
        or (holy_week_start <= d <= holy_week_end)
    )
    sanctorale: list[Celebration] = [] if in_suppressed else _get_effective_sanctorale(d, config)

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

    # Precedence: sort descending by rank.
    # Tiebreaker at MEMORIAL rank: fixed sanctorale memorials beat moveable
    # temporale ones (e.g. Irenaeus beats Immaculate Heart when they coincide).
    # At FEAST and above, the stable insertion order prevails (temporale first).
    def _rank_key(c: Celebration) -> tuple[int, int]:
        if c.rank == Rank.MEMORIAL:
            priority = 0 if c.kind == CelebrationKind.TEMPORALE else 1
        else:
            priority = 0
        return (c.rank, priority)

    sorted_candidates = sorted(candidates, key=_rank_key, reverse=True)
    winner = sorted_candidates[0]
    displaced = tuple(sorted_candidates[1:])

    # Apply season-based colour overrides (GIRM §346)
    effective_color = _resolve_color(winner, season)
    if effective_color != winner.color:
        winner = replace(winner, color=effective_color)

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
