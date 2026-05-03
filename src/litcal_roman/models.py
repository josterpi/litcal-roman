"""
litcal_roman.models
~~~~~~~~~~~~~~~~~~

Core data model for the Roman Catholic liturgical calendar.

All types here are pure values — frozen dataclasses and enums. No I/O,
no computation beyond what's intrinsic to the types. Everything else in
the library imports from here; this module imports nothing internal.

Rank values follow GNLYC paragraph 59 (table of liturgical days in order
of precedence). Higher integer = higher rank. This makes precedence
resolution expressible as max(celebrations, key=lambda c: c.rank).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum, IntEnum
from typing import Optional


# ---------------------------------------------------------------------------
# Season
# ---------------------------------------------------------------------------

class Season(Enum):
    """
    The six liturgical seasons of the Roman Rite.

    Note that ORDINARY_TIME appears in two non-contiguous segments of the
    civil year (post-Epiphany and post-Pentecost) but is a single season
    with continuous week numbering across both segments.
    """
    ADVENT       = "advent"
    CHRISTMAS    = "christmas"
    ORDINARY     = "ordinary_time"
    LENT         = "lent"
    TRIDUUM      = "triduum"
    EASTER       = "easter"

    def __str__(self) -> str:
        return self.value.replace("_", " ").title()


# ---------------------------------------------------------------------------
# Rank
# ---------------------------------------------------------------------------

class Rank(IntEnum):
    """
    Liturgical rank of a celebration, in ascending order of precedence.

    Values are spaced to allow future insertion of intermediate ranks
    without renumbering. The ordering follows GNLYC paragraph 59.

    FERIA is the baseline — a day with no proper celebration of its own.
    The Triduum ranks above all else; within solemnities, further ordering
    is handled by the precedence resolver using the GNLYC table directly.
    """
    FERIA                = 10   # ferial weekday
    OPTIONAL_MEMORIAL    = 20   # memoria ad libitum
    MEMORIAL             = 30   # memoria obligatoria
    FEAST                = 40   # festum (saints' feasts, OT Sundays, Christmas Sundays)
    LORD_FEAST           = 45   # feasts of the Lord in the sanctorale (GNLYC §59 row 4)
    SOLEMNITY            = 50   # sollemnitas
    # The Triduum days are technically solemnities but outrank everything
    TRIDUUM              = 60
    # Easter Sunday outranks other Triduum days
    EASTER_SUNDAY        = 70

    def __str__(self) -> str:
        return self.name.replace("_", " ").title()


# ---------------------------------------------------------------------------
# CelebrationKind
# ---------------------------------------------------------------------------

class CelebrationKind(Enum):
    """
    Whether a celebration originates in the temporale or sanctorale,
    and whether it is proper to a region or universal.

    This is metadata for consumers and for the precedence resolver — it
    does not affect rank directly, but the resolver needs it to apply
    GNLYC collision rules correctly (e.g. a proper feast of a church
    outranks a universal optional memorial on the same day).
    """
    TEMPORALE           = "temporale"       # season / week day (feria, Sunday, etc.)
    SANCTORALE_UNIVERSAL = "sanctorale_universal"
    SANCTORALE_REGIONAL  = "sanctorale_regional"  # national or diocesan proper


# ---------------------------------------------------------------------------
# LiturgicalColor
# ---------------------------------------------------------------------------

class LiturgicalColor(Enum):
    """
    Vestment colour for the celebration.
    Rose (gaudete / laetare) and black (Masses for the dead) included
    for completeness; they are uncommon but part of the General Roman Calendar.
    """
    WHITE  = "white"
    RED    = "red"
    GREEN  = "green"
    VIOLET = "violet"
    ROSE   = "rose"
    BLACK  = "black"

    def __str__(self) -> str:
        return self.value.title()


# ---------------------------------------------------------------------------
# ScriptureCycle
# ---------------------------------------------------------------------------

class ScriptureCycle(Enum):
    """
    The two-year Office of Readings / weekday Mass cycle.

    Year I = odd liturgical years, Year II = even liturgical years.
    The liturgical year begins on the First Sunday of Advent, so the
    cycle flips in late November / early December, not on January 1.
    """
    YEAR_I  = 1
    YEAR_II = 2

    def __str__(self) -> str:
        return f"Year {'I' if self == self.YEAR_I else 'II'}"


# ---------------------------------------------------------------------------
# SundayCycle
# ---------------------------------------------------------------------------

class SundayCycle(Enum):
    """
    The three-year Sunday Mass Lectionary cycle (A, B, C).
    Cycle A begins in Advent of years divisible by 3.
    """
    A = "A"
    B = "B"
    C = "C"

    def __str__(self) -> str:
        return f"Cycle {self.value}"


# ---------------------------------------------------------------------------
# Celebration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Celebration:
    """
    A single liturgical celebration — a feria, memorial, feast, or solemnity.

    A given calendar day resolves to exactly one *winning* Celebration plus
    zero or more *displaced* ones (see LiturgicalDay). This type represents
    any of those.

    Attributes
    ----------
    name:
        Liturgical name in the locale of the calendar instance.
        e.g. "Wednesday of the 4th Week of Easter", "Saint Cecilia, Virgin and Martyr"
    rank:
        Liturgical rank; determines precedence when celebrations collide.
    kind:
        Temporale or sanctorale; universal or regional.
    color:
        Vestment colour for this celebration.
    feast_date:
        The proper (fixed) date of a sanctorale celebration, or None for
        temporale days. Useful for distinguishing "transferred" feasts.
    optional:
        True for optional memorials (Rank.OPTIONAL_MEMORIAL); False otherwise.
        Redundant with rank but convenient for callers.
    """
    name:       str
    rank:       Rank
    kind:       CelebrationKind
    color:      LiturgicalColor
    feast_date: Optional[date]  = field(default=None)
    optional:   bool            = field(default=False)

    def __post_init__(self) -> None:
        # Invariant: optional flag must agree with rank
        if self.optional and self.rank != Rank.OPTIONAL_MEMORIAL:
            raise ValueError(
                f"optional=True requires Rank.OPTIONAL_MEMORIAL, got {self.rank}"
            )
        if not self.optional and self.rank == Rank.OPTIONAL_MEMORIAL:
            raise ValueError(
                "Rank.OPTIONAL_MEMORIAL requires optional=True"
            )

    def __str__(self) -> str:
        return f"{self.name} ({self.rank})"


# ---------------------------------------------------------------------------
# LiturgicalDay
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LiturgicalDay:
    """
    The full liturgical context for a single civil calendar date.

    This is the primary return type of LiturgicalCalendar.get(date).

    Attributes
    ----------
    date:
        The civil calendar date.
    season:
        Liturgical season.
    week:
        Week number within the season (1-indexed).
        For Ordinary Time, this is the continuous week number (1–34)
        per GNLYC §44, spanning both pre-Lent and post-Pentecost segments.
    weekday:
        ISO weekday: 1=Monday … 7=Sunday.
    psalter_week:
        Which week of the four-week Psalter (1–4).
    celebration:
        The winning celebration for this day after precedence resolution.
    displaced:
        Celebrations that lost to the winner in precedence resolution.
        Ordered by descending rank. May be empty.
    scripture_cycle:
        Year I or Year II for the Office of Readings / weekday lectionary.
    sunday_cycle:
        Lectionary cycle A, B, or C (relevant on Sundays and solemnities).
    region:
        Region key used to produce this day (e.g. "universal", "us").
    """
    date:            date
    season:          Season
    week:            int
    weekday:         int          # ISO: 1=Mon, 7=Sun
    psalter_week:    int          # 1–4
    celebration:     Celebration
    displaced:       tuple[Celebration, ...]  = field(default_factory=tuple)
    scripture_cycle: Optional[ScriptureCycle] = field(default=None)
    sunday_cycle:    Optional[SundayCycle]    = field(default=None)
    region:          str                      = field(default="universal")

    def __post_init__(self) -> None:
        if not 1 <= self.week <= 34 and self.season == Season.ORDINARY:
            raise ValueError(
                f"Ordinary Time week must be 1–34, got {self.week}"
            )
        if not 1 <= self.psalter_week <= 4:
            raise ValueError(
                f"Psalter week must be 1–4, got {self.psalter_week}"
            )
        if not 1 <= self.weekday <= 7:
            raise ValueError(
                f"ISO weekday must be 1–7, got {self.weekday}"
            )
        # displaced must be sorted descending by rank
        if len(self.displaced) > 1:
            ranks = [c.rank for c in self.displaced]
            if ranks != sorted(ranks, reverse=True):
                raise ValueError("displaced celebrations must be ordered by descending rank")

    @property
    def is_sunday(self) -> bool:
        return self.weekday == 7

    @property
    def is_feria(self) -> bool:
        return self.celebration.rank == Rank.FERIA

    @property
    def is_solemnity(self) -> bool:
        return self.celebration.rank >= Rank.SOLEMNITY

    @property
    def has_displaced(self) -> bool:
        return len(self.displaced) > 0

    @property
    def all_celebrations(self) -> tuple[Celebration, ...]:
        """Winner first, then displaced in descending rank order."""
        return (self.celebration,) + self.displaced

    def __str__(self) -> str:
        base = f"{self.date.isoformat()} | {self.celebration.name}"
        if self.displaced:
            displaced_names = ", ".join(c.name for c in self.displaced)
            base += f" (displaces: {displaced_names})"
        return base


# ---------------------------------------------------------------------------
# CalendarConfig
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CalendarConfig:
    """
    Configuration for a LiturgicalCalendar instance.

    Attributes
    ----------
    region:
        Region key determining which sanctorale data and transfer rules
        to apply. "universal" applies no transfers and no national propers.
        "us" applies USCCB propers and US transfer rules (Ascension to Sunday).
    locale:
        BCP 47 locale tag for label generation. Currently "en_US" and "la"
        (Latin) are bundled. Additional locales can be registered.
    transfer_ascension:
        If True, Ascension is observed on the 7th Sunday of Easter rather
        than Thursday of the 6th week. Defaults to True for "us", False
        for "universal". Can be overridden explicitly.
    transfer_epiphany:
        If True, Epiphany is transferred to the Sunday between Jan 2–8.
        Defaults to True for "us".
    transfer_corpus_christi:
        If True, Corpus Christi is transferred to the Sunday after Trinity.
        Defaults to True for "us".
    """
    region:                  str  = "us"
    locale:                  str  = "en_US"
    transfer_ascension:      bool = True
    transfer_epiphany:       bool = True
    transfer_corpus_christi: bool = True

    @classmethod
    def universal(cls) -> "CalendarConfig":
        """No transfers, no national propers."""
        return cls(
            region="universal",
            locale="en_US",
            transfer_ascension=False,
            transfer_epiphany=False,
            transfer_corpus_christi=False,
        )

    @classmethod
    def us(cls) -> "CalendarConfig":
        """USCCB calendar with standard US transfers."""
        return cls(
            region="us",
            locale="en_US",
            transfer_ascension=True,
            transfer_epiphany=True,
            transfer_corpus_christi=True,
        )
