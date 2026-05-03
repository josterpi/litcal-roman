"""
tests/test_calendar.py
~~~~~~~~~~~~~~~~~~~~~~

Tests for litcal_roman.calendar.get_liturgical_day.

Test strategy
-------------
- Known-date assertions verified against published liturgical calendars.
- Transfer tests use years where the transfer condition is known to fire.
- Precedence tests confirm winner/displaced ordering by rank.

Test years used:
    2026 — Easter April 5 (current year; standard case)
    2025 — Easter April 20 (All Souls Nov 2 falls on Sunday → transfers)
    2019 — Advent 1 Dec 1 (IC Dec 8 = 2nd Sunday of Advent → transfers)
    2018 — Easter April 1 (March 25 = Palm Sunday → Annunciation transfers)
"""

from datetime import date

import pytest

from litcal_roman.calendar import get_liturgical_day
from litcal_roman.models import (
    CalendarConfig,
    CelebrationKind,
    LiturgicalColor,
    Rank,
    Season,
)

_UNIVERSAL = CalendarConfig.universal()
_US = CalendarConfig.us()


# ---------------------------------------------------------------------------
# Ordinary feria
# ---------------------------------------------------------------------------

class TestOrdinaryFeria:
    def test_feria_rank(self):
        # 2026-01-14: OT week 1, Wednesday; no sanctorale entry
        ld = get_liturgical_day(date(2026, 1, 14), _US)
        assert ld.celebration.rank == Rank.FERIA

    def test_feria_kind(self):
        ld = get_liturgical_day(date(2026, 1, 14), _US)
        assert ld.celebration.kind == CelebrationKind.TEMPORALE

    def test_feria_label(self):
        ld = get_liturgical_day(date(2026, 1, 14), _US)
        assert ld.celebration.name == "Wednesday of the 1st Week in Ordinary Time"

    def test_feria_no_displaced(self):
        ld = get_liturgical_day(date(2026, 1, 14), _US)
        assert ld.displaced == ()

    def test_feria_season(self):
        ld = get_liturgical_day(date(2026, 1, 14), _US)
        assert ld.season == Season.ORDINARY


# ---------------------------------------------------------------------------
# Memorial on OT feria
# ---------------------------------------------------------------------------

class TestMemorialWins:
    # 2026-01-17: Saint Anthony, Abbot (Memorial); OT week 1, Saturday

    def test_memorial_wins(self):
        ld = get_liturgical_day(date(2026, 1, 17), _US)
        assert ld.celebration.rank == Rank.MEMORIAL
        assert ld.celebration.name == "Saint Anthony, Abbot"

    def test_feria_displaced(self):
        ld = get_liturgical_day(date(2026, 1, 17), _US)
        assert len(ld.displaced) == 1
        assert ld.displaced[0].rank == Rank.FERIA

    def test_displaced_sorted_descending(self):
        ld = get_liturgical_day(date(2026, 1, 17), _US)
        ranks = [c.rank for c in ld.displaced]
        assert ranks == sorted(ranks, reverse=True)


# ---------------------------------------------------------------------------
# Optional memorial on OT feria
# ---------------------------------------------------------------------------

class TestOptionalMemorialWins:
    # 2026-01-13: Saint Hilary (Optional Memorial); OT week 1, Tuesday

    def test_optional_memorial_wins(self):
        ld = get_liturgical_day(date(2026, 1, 13), _US)
        assert ld.celebration.rank == Rank.OPTIONAL_MEMORIAL
        assert "Hilary" in ld.celebration.name

    def test_feria_displaced(self):
        ld = get_liturgical_day(date(2026, 1, 13), _US)
        assert any(c.rank == Rank.FERIA for c in ld.displaced)


# ---------------------------------------------------------------------------
# Solemnity on OT Sunday
# ---------------------------------------------------------------------------

class TestSolemnityOnSunday:
    # 2026-11-01: All Saints (Solemnity) falls on 31st Sunday of OT
    # All Saints (50) > OT Sunday / FEAST (40)

    def test_solemnity_wins(self):
        ld = get_liturgical_day(date(2026, 11, 1), _US)
        assert ld.celebration.rank == Rank.SOLEMNITY
        assert ld.celebration.name == "All Saints"

    def test_sunday_displaced(self):
        ld = get_liturgical_day(date(2026, 11, 1), _US)
        assert any(c.rank == Rank.FEAST and c.kind == CelebrationKind.TEMPORALE
                   for c in ld.displaced)

    def test_displaced_is_sunday(self):
        ld = get_liturgical_day(date(2026, 11, 1), _US)
        ot_sunday = next(
            c for c in ld.displaced
            if c.kind == CelebrationKind.TEMPORALE
        )
        assert "Sunday" in ot_sunday.name


# ---------------------------------------------------------------------------
# Christ the King (OT week 34 Sunday) beats a concurrent memorial
# ---------------------------------------------------------------------------

class TestChristTheKing:
    # 2026-11-22: OT week 34, Sunday — Christ the King (Solemnity)
    # Saint Cecilia (Memorial) is also on 11-22 but is displaced

    def test_winner_is_christ_the_king(self):
        ld = get_liturgical_day(date(2026, 11, 22), _US)
        assert "King" in ld.celebration.name
        assert ld.celebration.rank == Rank.SOLEMNITY

    def test_cecilia_displaced(self):
        ld = get_liturgical_day(date(2026, 11, 22), _US)
        names = [c.name for c in ld.displaced]
        assert any("Cecilia" in n for n in names)


# ---------------------------------------------------------------------------
# Easter Octave: sanctorale suppressed
# ---------------------------------------------------------------------------

class TestEasterOctaveSuppression:
    # Easter 2026 = April 5.  April 7 has "Saint John Baptist de la Salle"
    # (Memorial) in the universal sanctorale, but it is suppressed.

    def test_octave_day_wins(self):
        ld = get_liturgical_day(date(2026, 4, 7), _US)
        assert ld.season == Season.EASTER
        assert ld.week == 1
        assert ld.celebration.rank == Rank.SOLEMNITY
        assert ld.celebration.kind == CelebrationKind.TEMPORALE

    def test_sanctorale_suppressed(self):
        ld = get_liturgical_day(date(2026, 4, 7), _US)
        # No sanctorale celebration should appear anywhere
        all_cel = ld.all_celebrations
        assert all(c.kind == CelebrationKind.TEMPORALE for c in all_cel)

    def test_octave_label(self):
        ld = get_liturgical_day(date(2026, 4, 7), _US)
        assert "Tuesday" in ld.celebration.name
        assert "Octave" in ld.celebration.name


# ---------------------------------------------------------------------------
# Annunciation transfer: 2018 (Easter = April 1, March 25 = Palm Sunday)
# ---------------------------------------------------------------------------

class TestAnnunciationTransfer:
    # March 25, 2018 is Palm Sunday → Annunciation transfers to April 9

    def test_annunciation_absent_on_proper_date(self):
        ld = get_liturgical_day(date(2018, 3, 25), _UNIVERSAL)
        names = [c.name for c in ld.all_celebrations]
        assert not any("Annunciation" in n for n in names)

    def test_palm_sunday_wins_on_proper_date(self):
        ld = get_liturgical_day(date(2018, 3, 25), _UNIVERSAL)
        assert ld.season == Season.LENT
        assert "Palm Sunday" in ld.celebration.name

    def test_annunciation_present_on_transfer_date(self):
        ld = get_liturgical_day(date(2018, 4, 9), _UNIVERSAL)
        names = [c.name for c in ld.all_celebrations]
        assert any("Annunciation" in n for n in names)

    def test_annunciation_wins_on_transfer_date(self):
        ld = get_liturgical_day(date(2018, 4, 9), _UNIVERSAL)
        assert ld.celebration.rank == Rank.SOLEMNITY
        assert "Annunciation" in ld.celebration.name


# ---------------------------------------------------------------------------
# Immaculate Conception transfer: 2019 (Dec 8 = 2nd Sunday of Advent)
# ---------------------------------------------------------------------------

class TestImmaculateConceptionTransfer:
    # Advent 1, 2019 = Dec 1 → Advent 2 Sunday = Dec 8 = IC → transfers to Dec 9

    def test_ic_absent_on_proper_date(self):
        ld = get_liturgical_day(date(2019, 12, 8), _UNIVERSAL)
        names = [c.name for c in ld.all_celebrations]
        assert not any("Immaculate" in n for n in names)

    def test_advent_sunday_wins_on_dec_8(self):
        ld = get_liturgical_day(date(2019, 12, 8), _UNIVERSAL)
        assert ld.season == Season.ADVENT
        assert ld.weekday == 7
        assert ld.week == 2

    def test_ic_present_on_transfer_date(self):
        ld = get_liturgical_day(date(2019, 12, 9), _UNIVERSAL)
        names = [c.name for c in ld.all_celebrations]
        assert any("Immaculate" in n for n in names)

    def test_ic_wins_on_transfer_date(self):
        ld = get_liturgical_day(date(2019, 12, 9), _UNIVERSAL)
        assert ld.celebration.rank == Rank.SOLEMNITY
        assert "Immaculate" in ld.celebration.name


# ---------------------------------------------------------------------------
# All Souls transfer: 2025 (Nov 2 = Sunday → transfers to Nov 3)
# ---------------------------------------------------------------------------

class TestAllSoulsTransfer:
    # All Souls is LORD_FEAST (GNLYC row 4) and displaces OT Sundays.
    # No transfer to Nov 3 is required; All Souls wins on Nov 2 itself.

    def test_all_souls_wins_on_nov_2_even_when_sunday(self):
        # 2025-11-02 is a Sunday; All Souls (LORD_FEAST) beats OT Sunday (FEAST)
        ld = get_liturgical_day(date(2025, 11, 2), _UNIVERSAL)
        assert "Faithful Departed" in ld.celebration.name

    def test_all_souls_rank(self):
        ld = get_liturgical_day(date(2025, 11, 2), _UNIVERSAL)
        assert ld.celebration.rank == Rank.LORD_FEAST

    def test_ot_sunday_displaced_on_nov_2(self):
        ld = get_liturgical_day(date(2025, 11, 2), _UNIVERSAL)
        assert ld.weekday == 7
        assert ld.season == Season.ORDINARY
        assert any("Sunday" in c.name for c in ld.displaced)

    def test_nov_3_is_normal_weekday(self):
        # Nov 3 is not a transfer target — Martin de Porres (Opt. Mem.) or feria
        ld = get_liturgical_day(date(2025, 11, 3), _UNIVERSAL)
        assert "Faithful Departed" not in ld.celebration.name


# ---------------------------------------------------------------------------
# LiturgicalDay field consistency
# ---------------------------------------------------------------------------

class TestLiturgicalDayFields:
    def test_date_field(self):
        d = date(2026, 4, 5)
        ld = get_liturgical_day(d, _US)
        assert ld.date == d

    def test_region_matches_config(self):
        ld = get_liturgical_day(date(2026, 6, 1), _US)
        assert ld.region == "us"
        ld2 = get_liturgical_day(date(2026, 6, 1), _UNIVERSAL)
        assert ld2.region == "universal"

    def test_easter_sunday_rank(self):
        ld = get_liturgical_day(date(2026, 4, 5), _US)
        assert ld.celebration.rank == Rank.EASTER_SUNDAY

    def test_psalter_week_in_range(self):
        for day_offset in range(50):
            d = date(2026, 1, 1) + __import__("datetime").timedelta(days=day_offset)
            ld = get_liturgical_day(d, _US)
            assert 1 <= ld.psalter_week <= 4
