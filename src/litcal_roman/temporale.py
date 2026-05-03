"""
litcal_roman.temporale
~~~~~~~~~~~~~~~~~~~~~

Computes the moveable cycle of the Roman Catholic liturgical calendar
(Ordinary Form) for any given date.

The temporale is the portion of the calendar anchored to Easter Sunday,
whose date moves each year. All seasons, week numbers, and ferial
designations derive from two anchors:

    1. Easter Sunday          (computed via the Gregorian algorithm)
    2. First Sunday of Advent (computed from Christmas)

References
----------
- General Norms for the Liturgical Year and the Calendar (GNLYC), 1969
  appended to the Roman Missal, §§1–59
- General Instruction of the Liturgy of the Hours (GILH), 1971, §§125–135
  (Psalter week assignment)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from typing import Optional

from dateutil.easter import easter as _dateutil_easter

from .models import (
    CalendarConfig,
    Celebration,
    CelebrationKind,
    LiturgicalColor,
    Rank,
    ScriptureCycle,
    Season,
    SundayCycle,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_WEEKDAY_NAMES = {
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
    7: "Sunday",
}

_ORDINALS = {
    1: "1st", 2: "2nd", 3: "3rd", 4: "4th",
    5: "5th", 6: "6th", 7: "7th", 8: "8th",
    9: "9th", 10: "10th", 11: "11th", 12: "12th",
    13: "13th", 14: "14th", 15: "15th", 16: "16th",
    17: "17th", 18: "18th", 19: "19th", 20: "20th",
    21: "21st", 22: "22nd", 23: "23rd", 24: "24th",
    25: "25th", 26: "26th", 27: "27th", 28: "28th",
    29: "29th", 30: "30th", 31: "31st", 32: "32nd",
    33: "33rd", 34: "34th",
}

# Triduum day labels — these are proper names, not computed
_TRIDUUM_LABELS = {
    0: "Thursday of the Lord's Supper (Holy Thursday)",
    1: "Friday of the Passion of the Lord (Good Friday)",
    2: "Holy Saturday",
}

# Christmas season day labels for the days between Christmas and Epiphany
# that fall before January 1 or after (the "Christmas weekdays")
_OCTAVE_CHRISTMAS_LABELS = {
    1: "Christmas Day",
    2: "26 December",   # varies by region; in US: Saint Stephen
    3: "27 December",
    4: "28 December",
    5: "29 December",
    6: "30 December",
    7: "31 December",
}


# ---------------------------------------------------------------------------
# Anchor computation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class YearAnchors:
    """
    All moveable liturgical anchors for a given civil year.

    Most dates here are Easter-relative. The Advent anchor is
    Christmas-relative and belongs to the *next* liturgical year.

    Note: transfer booleans are NOT applied here — anchors always reflect
    the proper (un-transferred) dates. Transfers are handled in Temporale
    so the distinction between proper and transferred date is preserved.
    """
    year:               int
    easter:             date
    ash_wednesday:      date
    palm_sunday:        date
    holy_thursday:      date
    good_friday:        date
    holy_saturday:      date
    pentecost:          date
    trinity_sunday:     date
    # Proper (un-transferred) dates:
    ascension_proper:   date   # 39 days after Easter (Thursday)
    corpus_christi_proper: date  # 60 days after Easter (Thursday)
    epiphany_proper:    date   # January 6
    baptism_proper:     date   # Sunday after Epiphany (or Jan 13 if Ep on Sun)
    # First Sunday of Advent (opens the *next* liturgical year)
    advent_1:           date


@lru_cache(maxsize=10)
def get_anchors(year: int) -> YearAnchors:
    """
    Compute and cache all moveable anchors for a civil year.

    Cached because temporale lookups for a given year will call this
    repeatedly (once per date queried in that year).
    """
    easter = _dateutil_easter(year)

    epiphany = date(year, 1, 6)
    baptism  = _baptism_of_the_lord(epiphany)

    return YearAnchors(
        year               = year,
        easter             = easter,
        ash_wednesday      = easter - timedelta(days=46),
        palm_sunday        = easter - timedelta(days=7),
        holy_thursday      = easter - timedelta(days=3),
        good_friday        = easter - timedelta(days=2),
        holy_saturday      = easter - timedelta(days=1),
        pentecost          = easter + timedelta(days=49),
        trinity_sunday     = easter + timedelta(days=56),
        ascension_proper   = easter + timedelta(days=39),
        corpus_christi_proper = easter + timedelta(days=60),
        epiphany_proper    = epiphany,
        baptism_proper     = baptism,
        advent_1           = _first_sunday_of_advent(year),
    )


def _first_sunday_of_advent(year: int) -> date:
    """
    The First Sunday of Advent is the Sunday closest to November 30
    (the feast of Saint Andrew), which works out to the Sunday falling
    on or between November 27 and December 3.

    Equivalently: find the Sunday on or before December 25, then
    subtract three weeks to get four Sundays before Christmas.

    GNLYC §39: "Advent begins with First Vespers (Evening Prayer I) of
    the Sunday that falls on or closest to November 30."
    """
    christmas = date(year, 12, 25)
    # isoweekday(): Mon=1 … Sun=7
    # When Christmas is Sunday, % 7 gives 0 — we need 7 to step back a full week.
    days_to_prev_sunday = christmas.isoweekday() % 7 or 7
    sunday_before_christmas = christmas - timedelta(days=days_to_prev_sunday)
    return sunday_before_christmas - timedelta(weeks=3)


def _baptism_of_the_lord(epiphany: date) -> date:
    """
    The Baptism of the Lord is celebrated on the Sunday after Epiphany.

    Special rule (GNLYC §38): when Epiphany falls on January 7 or 8
    (which happens when it is transferred to Sunday in some regions),
    the Baptism of the Lord is observed on the following Monday because
    there is no remaining Sunday between it and the start of OT.

    For all other cases (proper Jan 6, or transferred Jan 2–6), Baptism
    is the Sunday after Epiphany, i.e. between January 7–13.
    """
    if epiphany.day in (7, 8):
        # No Sunday left in Christmas season — move Baptism to Monday
        return epiphany + timedelta(days=1)
    days_until_sunday = (7 - epiphany.isoweekday()) % 7 or 7
    return epiphany + timedelta(days=days_until_sunday)


# ---------------------------------------------------------------------------
# Transferred dates (region-aware)
# ---------------------------------------------------------------------------

def get_epiphany(year: int, config: CalendarConfig) -> date:
    """
    Epiphany: January 6 (proper) or transferred to Sunday Jan 2–8 (US).
    GNLYC §7.
    """
    if not config.transfer_epiphany:
        return date(year, 1, 6)
    # Find the Sunday between January 2 and January 8
    for day_offset in range(7):
        candidate = date(year, 1, 2) + timedelta(days=day_offset)
        if candidate.isoweekday() == 7:
            return candidate
    raise RuntimeError("No Sunday found between Jan 2–8")  # cannot happen


def get_baptism(year: int, config: CalendarConfig) -> date:
    """
    Baptism of the Lord: Sunday after (transferred or proper) Epiphany.
    """
    epiphany = get_epiphany(year, config)
    return _baptism_of_the_lord(epiphany)


def get_ascension(year: int, config: CalendarConfig) -> date:
    """
    Ascension: 39 days after Easter (Thursday) or 7th Sunday of Easter (US).
    GNLYC §7.
    """
    anchors = get_anchors(year)
    if not config.transfer_ascension:
        return anchors.ascension_proper
    # 7th Sunday of Easter = 42 days after Easter
    return anchors.easter + timedelta(days=42)


def get_corpus_christi(year: int, config: CalendarConfig) -> date:
    """
    Corpus Christi: 60 days after Easter (Thursday) or Sunday after Trinity (US).
    GNLYC §7.
    """
    anchors = get_anchors(year)
    if not config.transfer_corpus_christi:
        return anchors.corpus_christi_proper
    # Sunday after Trinity Sunday = 63 days after Easter
    return anchors.easter + timedelta(days=63)


# ---------------------------------------------------------------------------
# Season resolution
# ---------------------------------------------------------------------------

def get_season(d: date, config: CalendarConfig) -> tuple[Season, int]:
    """
    Return (season, week_number) for date *d*.

    Week numbers are 1-indexed within the season. For Ordinary Time the
    week number is the continuous count (1–34) spanning both segments,
    per GNLYC §44. The gap left by Lent and Easter is absorbed silently —
    OT week numbers simply skip from wherever segment 1 ends to wherever
    segment 2 begins when counted back from Advent.

    The Triduum returns week=0 (it has no week in the seasonal sense).
    """
    # We may need anchors for both this year and last year, since a
    # January date might still be in the previous year's Advent or Christmas.
    anchors      = get_anchors(d.year)
    prev_anchors = get_anchors(d.year - 1)

    baptism  = get_baptism(d.year, config)
    epiphany = get_epiphany(d.year, config)

    # --- Triduum ---
    # Holy Thursday evening through Holy Saturday.
    # Check before Easter (Easter Sunday is Season.EASTER week 1).
    if anchors.holy_thursday <= d <= anchors.holy_saturday:
        return Season.TRIDUUM, 0

    # --- Easter Season ---
    # Easter Sunday through Pentecost Sunday (inclusive).
    ascension = get_ascension(d.year, config)  # noqa: F841 — used implicitly via anchors
    if anchors.easter <= d <= anchors.pentecost:
        week = min((d - anchors.easter).days // 7 + 1, 7)
        return Season.EASTER, week

    # --- Lent ---
    # Ash Wednesday through Holy Wednesday (day before Holy Thursday).
    if anchors.ash_wednesday <= d < anchors.holy_thursday:
        # Ash Wednesday begins Lent; it falls mid-week.
        # Week 1 of Lent begins on Ash Wednesday regardless of weekday.
        # The Sunday before Ash Wednesday is the last Sunday of OT.
        # Palm Sunday begins week 6; Holy Week Mon–Wed are still week 6.
        week = min((d - anchors.ash_wednesday).days // 7 + 1, 6)
        return Season.LENT, week

    # --- Advent ---
    # First Sunday of Advent through Christmas Eve.
    # The current year's Advent opens the *next* liturgical year, so
    # dates in Dec after Advent 1 are in the current year's Advent.
    if anchors.advent_1 <= d < date(d.year, 12, 25):
        week = (d - anchors.advent_1).days // 7 + 1
        return Season.ADVENT, week

    # Dates in January before Baptism of the Lord may still be in
    # the previous year's Advent (i.e. late Dec before Christmas).
    # Actually: dates before Christmas are in Advent; dates from
    # Christmas Eve onwards are Christmas. Let's handle Christmas next.

    # --- Christmas ---
    # December 25 through the Baptism of the Lord.
    christmas_this_year = date(d.year, 12, 25)
    christmas_prev_year = date(d.year - 1, 12, 25)
    baptism_this_year   = baptism
    baptism_prev_year   = get_baptism(d.year - 1, config)

    if d >= christmas_this_year:
        # Dec 25 onward (already ruled out Advent above)
        week = (d - christmas_this_year).days // 7 + 1
        return Season.CHRISTMAS, week

    if d <= baptism_this_year:
        # January 1 – Baptism of the Lord: still Christmas season
        # from the previous December 25.
        week = (d - christmas_prev_year).days // 7 + 1
        return Season.CHRISTMAS, week

    # --- Ordinary Time ---
    return Season.ORDINARY, _ordinary_time_week(d, anchors, config)


def _ordinary_time_week(d: date, anchors: YearAnchors, config: CalendarConfig) -> int:
    """
    Compute the continuous Ordinary Time week number for *d*.

    GNLYC §44: OT begins the day after Baptism of the Lord and runs
    until Ash Wednesday; it resumes the day after Pentecost and runs
    until (but not including) the First Sunday of Advent.

    The week numbers across both segments are continuous, with the
    numbering of the second segment determined by counting *backwards*
    from Advent: the week immediately before Advent 1 is always week 34
    (Christ the King Sunday). This means the "missing" weeks swallowed
    by Lent/Easter simply don't appear — there is no week 7 of OT if
    Lent begins before it.
    """
    baptism = get_baptism(anchors.year, config)

    # First segment: Monday after Baptism of the Lord → Tuesday before Ash Wednesday
    ot_start = baptism + timedelta(days=1)
    if ot_start <= d < anchors.ash_wednesday:
        return (d - ot_start).days // 7 + 1

    # Second segment: day after Pentecost → Saturday before Advent 1
    # Week 34 is anchored on Christ the King Sunday (Advent 1 minus 1 week).
    # Count back from that Sunday using d's liturgical week-start Sunday.
    christ_the_king = anchors.advent_1 - timedelta(weeks=1)
    days_since_sunday = d.isoweekday() % 7   # Sun=0, Mon=1, …, Sat=6
    week_start_sunday = d - timedelta(days=days_since_sunday)
    weeks_before_ctk  = (christ_the_king - week_start_sunday).days // 7
    return 34 - weeks_before_ctk


# ---------------------------------------------------------------------------
# Psalter week
# ---------------------------------------------------------------------------

def get_psalter_week(season: Season, week: int) -> int:
    """
    Return the Psalter week (1–4) for a given season and week number.

    The four-week Psalter cycles continuously but resets at the opening
    of each major season. Reset points per GILH §§125–135:

        Advent week 1     → Psalter week 1
        Christmas         → Psalter week 3
        Lent week 1       → Psalter week 4  (note: NOT week 1)
        Easter week 1     → Psalter week 1  (but week 1 = octave, special)
        Ordinary Time     → continuous from week 1, cycling mod 4

    The Triduum uses the Psalter of Holy Week (treated as Psalter week 2,
    the continuation of Palm Sunday's week).
    """
    match season:
        case Season.ADVENT:
            return ((week - 1) % 4) + 1
        case Season.CHRISTMAS:
            # Starts at Psalter week 3
            return ((week + 1) % 4) + 1
        case Season.LENT:
            # Starts at Psalter week 4
            return ((week + 2) % 4) + 1
        case Season.TRIDUUM:
            return 2
        case Season.EASTER:
            # Week 1 (Octave) uses its own proper Psalter;
            # week 2 onward resumes at Psalter week 1 equivalent.
            # Conventionally modelled as: week 1 → Psalter 2, week 2 → 1, etc.
            if week == 1:
                return 2
            return ((week - 2) % 4) + 1
        case Season.ORDINARY:
            return ((week - 1) % 4) + 1
        case _:
            raise ValueError(f"Unknown season: {season}")


# ---------------------------------------------------------------------------
# Lectionary cycles
# ---------------------------------------------------------------------------

def get_scripture_cycle(d: date) -> ScriptureCycle:
    """
    Year I (odd liturgical years) or Year II (even liturgical years).

    The liturgical year begins on the First Sunday of Advent. Dates in
    Advent and December therefore belong to the *next* calendar year's
    liturgical year for cycle purposes.

    e.g. Advent 2025 (beginning late November 2025) opens liturgical
    year 2026, which is even → Year II.
    """
    liturgical_year = _liturgical_year(d)
    return ScriptureCycle.YEAR_I if liturgical_year % 2 != 0 else ScriptureCycle.YEAR_II


def get_sunday_cycle(d: date) -> SundayCycle:
    """
    Lectionary cycle A, B, or C for Sunday Mass.

    Cycle A begins in Advent of years divisible by 3 (i.e. the liturgical
    year number mod 3 == 0 → Cycle A).

    Liturgical year 2026 → 2026 % 3 == 1 → Cycle B (2025–2026).
    Liturgical year 2025 → 2025 % 3 == 0 → Cycle A (2024–2025).
    """
    liturgical_year = _liturgical_year(d)
    remainder = liturgical_year % 3
    match remainder:
        case 0:
            return SundayCycle.A
        case 1:
            return SundayCycle.B
        case 2:
            return SundayCycle.C
        case _:
            raise RuntimeError("Unreachable")


def _liturgical_year(d: date) -> int:
    """
    The liturgical year number that *d* belongs to.

    Dates from the First Sunday of Advent through December 31 belong to
    the liturgical year of the *following* calendar year.
    Dates from January 1 through the Saturday before Advent belong to
    the liturgical year of the *current* calendar year.
    """
    advent_1 = get_anchors(d.year).advent_1
    if d >= advent_1:
        return d.year + 1
    return d.year


# ---------------------------------------------------------------------------
# Label generation
# ---------------------------------------------------------------------------

def make_temporale_label(season: Season, week: int, weekday: int) -> str:
    """
    Generate the standard English liturgical label for a temporale day.

    Examples
    --------
    >>> make_temporale_label(Season.EASTER, 4, 3)
    'Wednesday of the 4th Week of Easter'
    >>> make_temporale_label(Season.ORDINARY, 12, 7)
    '12th Sunday in Ordinary Time'
    >>> make_temporale_label(Season.ADVENT, 3, 7)
    '3rd Sunday of Advent'
    """
    day_name = _WEEKDAY_NAMES[weekday]
    ordinal  = _ORDINALS[week]

    # Sundays have their own form
    if weekday == 7:
        match season:
            case Season.ADVENT:
                return f"{ordinal} Sunday of Advent"
            case Season.CHRISTMAS:
                return f"{ordinal} Sunday of Christmas"
            case Season.LENT:
                if week == 6:
                    return "Palm Sunday of the Passion of the Lord"
                return f"{ordinal} Sunday of Lent"
            case Season.EASTER:
                if week == 1:
                    return "Easter Sunday of the Resurrection of the Lord"
                return f"{ordinal} Sunday of Easter"
            case Season.ORDINARY:
                return f"{ordinal} Sunday in Ordinary Time"
            case Season.TRIDUUM:
                # No Sunday in the Triduum proper
                raise ValueError("Triduum has no Sunday designation")

    # Weekdays
    match season:
        case Season.ADVENT:
            # From Dec 17 onward, Advent days have proper names in the
            # sanctorale (O Antiphon days). The temporale label is still
            # used as fallback.
            return f"{day_name} of the {ordinal} Week of Advent"

        case Season.CHRISTMAS:
            return f"{day_name} of the {ordinal} Week of Christmas"

        case Season.LENT:
            if week == 1 and weekday in (4, 5, 6):
                # Ash Wednesday week: special labels (Ash Wed itself = ISO 3, handled separately)
                match weekday:
                    case 4:
                        return "Thursday after Ash Wednesday"
                    case 5:
                        return "Friday after Ash Wednesday"
                    case 6:
                        return "Saturday after Ash Wednesday"
            return f"{day_name} of the {ordinal} Week of Lent"

        case Season.TRIDUUM:
            return _TRIDUUM_LABELS.get(week, f"Day {week} of the Triduum")

        case Season.EASTER:
            if week == 1:
                # Easter Octave: each day has a proper name
                match weekday:
                    case 1: return "Monday within the Octave of Easter"
                    case 2: return "Tuesday within the Octave of Easter"
                    case 3: return "Wednesday within the Octave of Easter"
                    case 4: return "Thursday within the Octave of Easter"
                    case 5: return "Friday within the Octave of Easter"
                    case 6: return "Saturday within the Octave of Easter"
            return f"{day_name} of the {ordinal} Week of Easter"

        case Season.ORDINARY:
            return f"{day_name} of the {ordinal} Week in Ordinary Time"

        case _:
            raise ValueError(f"Unknown season: {season}")


# ---------------------------------------------------------------------------
# Special temporale celebrations (solemnities / feasts of the Lord)
# ---------------------------------------------------------------------------

# These are temporale days that are celebrations in their own right
# (not merely ferial days), keyed by their offset from Easter or by
# fixed logic. The sanctorale handles fixed-date solemnities; this
# handles moveable ones.

def get_temporale_celebration(
    d: date,
    season: Season,
    week: int,
    weekday: int,
    config: CalendarConfig,
) -> Optional[Celebration]:
    """
    Return a proper Celebration for special temporale days, or None
    if the day is an ordinary feria (to be filled by sanctorale or
    left as feria by the precedence resolver).

    Covers: Easter Sunday, Sundays, Octave days, Ascension, Pentecost,
    Trinity Sunday, Corpus Christi, Christ the King, Ash Wednesday,
    Palm Sunday, Triduum days, Christmas, Epiphany, Baptism of the Lord.

    The returned Celebration has kind=TEMPORALE. The orchestrating
    Calendar class merges this with sanctorale results and resolves
    precedence.
    """
    anchors  = get_anchors(d.year)
    epiphany = get_epiphany(d.year, config)
    baptism  = get_baptism(d.year, config)
    ascension = get_ascension(d.year, config)
    corpus   = get_corpus_christi(d.year, config)

    # --- Triduum ---
    if season == Season.TRIDUUM:
        triduum_offset = (d - anchors.holy_thursday).days
        label = _TRIDUUM_LABELS[triduum_offset]
        color = LiturgicalColor.WHITE if triduum_offset == 0 else LiturgicalColor.RED
        rank  = Rank.TRIDUUM
        return Celebration(name=label, rank=rank, kind=CelebrationKind.TEMPORALE, color=color)

    # --- Easter Sunday ---
    if d == anchors.easter:
        return Celebration(
            name  = "Easter Sunday of the Resurrection of the Lord",
            rank  = Rank.EASTER_SUNDAY,
            kind  = CelebrationKind.TEMPORALE,
            color = LiturgicalColor.WHITE,
        )

    # --- Easter Octave (Mon–Sat of week 1) ---
    if season == Season.EASTER and week == 1 and weekday != 7:
        label = make_temporale_label(Season.EASTER, 1, weekday)
        return Celebration(
            name  = label,
            rank  = Rank.SOLEMNITY,  # octave days rank as solemnities
            kind  = CelebrationKind.TEMPORALE,
            color = LiturgicalColor.WHITE,
        )

    # --- Ascension ---
    if d == ascension:
        return Celebration(
            name  = "The Ascension of the Lord",
            rank  = Rank.SOLEMNITY,
            kind  = CelebrationKind.TEMPORALE,
            color = LiturgicalColor.WHITE,
        )

    # --- Pentecost Sunday ---
    if d == anchors.pentecost:
        return Celebration(
            name  = "Pentecost Sunday",
            rank  = Rank.SOLEMNITY,
            kind  = CelebrationKind.TEMPORALE,
            color = LiturgicalColor.RED,
        )

    # --- Trinity Sunday ---
    if d == anchors.trinity_sunday:
        return Celebration(
            name  = "The Most Holy Trinity",
            rank  = Rank.SOLEMNITY,
            kind  = CelebrationKind.TEMPORALE,
            color = LiturgicalColor.WHITE,
        )

    # --- Corpus Christi ---
    if d == corpus:
        return Celebration(
            name  = "The Most Holy Body and Blood of Christ (Corpus Christi)",
            rank  = Rank.SOLEMNITY,
            kind  = CelebrationKind.TEMPORALE,
            color = LiturgicalColor.WHITE,
        )

    # --- Christ the King (always last Sunday of OT = Sunday before Advent) ---
    if season == Season.ORDINARY and week == 34 and weekday == 7:
        return Celebration(
            name  = "Our Lord Jesus Christ, King of the Universe",
            rank  = Rank.SOLEMNITY,
            kind  = CelebrationKind.TEMPORALE,
            color = LiturgicalColor.WHITE,
        )

    # --- Ash Wednesday ---
    if d == anchors.ash_wednesday:
        return Celebration(
            name  = "Ash Wednesday",
            rank  = Rank.SOLEMNITY,  # outranks feasts; GNLYC §16
            kind  = CelebrationKind.TEMPORALE,
            color = LiturgicalColor.VIOLET,
        )

    # --- Palm Sunday ---
    if d == anchors.palm_sunday:
        return Celebration(
            name  = "Palm Sunday of the Passion of the Lord",
            rank  = Rank.SOLEMNITY,
            kind  = CelebrationKind.TEMPORALE,
            color = LiturgicalColor.RED,
        )

    # --- Christmas ---
    if d == date(d.year, 12, 25):
        return Celebration(
            name  = "The Nativity of the Lord (Christmas)",
            rank  = Rank.SOLEMNITY,
            kind  = CelebrationKind.TEMPORALE,
            color = LiturgicalColor.WHITE,
        )

    # --- Epiphany ---
    if d == epiphany:
        return Celebration(
            name  = "The Epiphany of the Lord",
            rank  = Rank.SOLEMNITY,
            kind  = CelebrationKind.TEMPORALE,
            color = LiturgicalColor.WHITE,
        )

    # --- Baptism of the Lord ---
    if d == baptism:
        return Celebration(
            name  = "The Baptism of the Lord",
            rank  = Rank.FEAST,
            kind  = CelebrationKind.TEMPORALE,
            color = LiturgicalColor.WHITE,
        )

    # --- Generic Sundays ---
    if weekday == 7:
        label = make_temporale_label(season, week, weekday)
        # Sundays in OT/Lent/Advent/Christmas rank as solemnities
        # for the purposes of displacing sanctorale feasts (GNLYC §5).
        rank = Rank.SOLEMNITY if season != Season.ORDINARY else Rank.FEAST
        color = _sunday_color(season)
        return Celebration(
            name  = label,
            rank  = rank,
            kind  = CelebrationKind.TEMPORALE,
            color = color,
        )

    # Ordinary feria — caller fills this with sanctorale or leaves as feria
    return None


def _sunday_color(season: Season) -> LiturgicalColor:
    match season:
        case Season.ADVENT | Season.LENT:
            return LiturgicalColor.VIOLET
        case Season.EASTER | Season.CHRISTMAS:
            return LiturgicalColor.WHITE
        case Season.ORDINARY:
            return LiturgicalColor.GREEN
        case _:
            return LiturgicalColor.WHITE


# ---------------------------------------------------------------------------
# Primary public interface
# ---------------------------------------------------------------------------

def compute_temporale(d: date, config: CalendarConfig) -> dict:
    """
    Compute the raw temporale data for *d* under *config*.

    Returns a dict suitable for passing to the Calendar orchestrator,
    which will merge it with sanctorale data and produce a LiturgicalDay.

    Keys
    ----
    season          : Season
    week            : int
    weekday         : int (ISO 1–7)
    psalter_week    : int (1–4)
    label           : str  (ferial label, may be overridden by celebration name)
    celebration     : Optional[Celebration]  (None for ordinary ferias)
    scripture_cycle : ScriptureCycle
    sunday_cycle    : SundayCycle
    """
    season, week  = get_season(d, config)
    weekday       = d.isoweekday()
    psalter_week  = get_psalter_week(season, week)
    if season == Season.TRIDUUM:
        label = _TRIDUUM_LABELS.get((d - get_anchors(d.year).holy_thursday).days, "")
    else:
        label = make_temporale_label(season, week, weekday)
    celebration   = get_temporale_celebration(d, season, week, weekday, config)
    scripture     = get_scripture_cycle(d)
    sunday_cycle  = get_sunday_cycle(d)

    return {
        "season":          season,
        "week":            week,
        "weekday":         weekday,
        "psalter_week":    psalter_week,
        "label":           label,
        "celebration":     celebration,
        "scripture_cycle": scripture,
        "sunday_cycle":    sunday_cycle,
    }
