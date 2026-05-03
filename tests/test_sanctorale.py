"""
tests/test_sanctorale.py
~~~~~~~~~~~~~~~~~~~~~~~~

Tests for litcal_roman.sanctorale.

Strategy
--------
1. Spot-checks — key solemnities, feasts, and memorials on known dates.
2. Rank and color invariants — solemnities are white/red; martyrs are red;
   optional_memorial ↔ optional=True.
3. Multiple celebrations on one date — shared dates return multiple entries.
4. Empty dates — dates with no sanctorale entry return [].
5. Kind — all entries from the universal file are SANCTORALE_UNIVERSAL.
6. No temporale feasts — dates owned by temporale.py are absent.
7. Regional fallback — unknown region returns only universal entries.
"""

from datetime import date

import pytest

from litcal_roman.models import (
    CalendarConfig,
    CelebrationKind,
    LiturgicalColor,
    Rank,
)
from litcal_roman.sanctorale import get_sanctorale_celebrations


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def universal():
    return CalendarConfig.universal()

@pytest.fixture
def us():
    return CalendarConfig.us()


# ---------------------------------------------------------------------------
# 1. Spot-checks
# ---------------------------------------------------------------------------

class TestSpotChecks:

    def test_mary_mother_of_god(self, universal):
        entries = get_sanctorale_celebrations(date(2026, 1, 1), universal)
        assert len(entries) == 1
        c = entries[0]
        assert c.rank == Rank.SOLEMNITY
        assert c.color == LiturgicalColor.WHITE
        assert "Mother of God" in c.name

    def test_joseph_solemnity(self, universal):
        entries = get_sanctorale_celebrations(date(2026, 3, 19), universal)
        assert any(c.rank == Rank.SOLEMNITY and "Joseph" in c.name for c in entries)

    def test_annunciation_solemnity(self, universal):
        entries = get_sanctorale_celebrations(date(2026, 3, 25), universal)
        assert any(c.rank == Rank.SOLEMNITY and "Annunciation" in c.name for c in entries)

    def test_birth_of_john_the_baptist(self, universal):
        entries = get_sanctorale_celebrations(date(2026, 6, 24), universal)
        assert any(c.rank == Rank.SOLEMNITY and "John the Baptist" in c.name for c in entries)

    def test_peter_and_paul(self, universal):
        entries = get_sanctorale_celebrations(date(2026, 6, 29), universal)
        assert any(c.rank == Rank.SOLEMNITY and "Peter" in c.name for c in entries)

    def test_assumption(self, universal):
        entries = get_sanctorale_celebrations(date(2026, 8, 15), universal)
        assert any(c.rank == Rank.SOLEMNITY and "Assumption" in c.name for c in entries)

    def test_all_saints(self, universal):
        entries = get_sanctorale_celebrations(date(2026, 11, 1), universal)
        assert any(c.rank == Rank.SOLEMNITY and "Saints" in c.name for c in entries)

    def test_immaculate_conception(self, universal):
        entries = get_sanctorale_celebrations(date(2026, 12, 8), universal)
        assert any(c.rank == Rank.SOLEMNITY and "Immaculate Conception" in c.name for c in entries)

    def test_presentation_feast(self, universal):
        entries = get_sanctorale_celebrations(date(2026, 2, 2), universal)
        assert any(c.rank == Rank.LORD_FEAST and "Presentation" in c.name for c in entries)

    def test_transfiguration_feast(self, universal):
        entries = get_sanctorale_celebrations(date(2026, 8, 6), universal)
        assert any(c.rank == Rank.FEAST and "Transfiguration" in c.name for c in entries)

    def test_mark_feast(self, universal):
        entries = get_sanctorale_celebrations(date(2026, 4, 25), universal)
        assert any(c.rank == Rank.FEAST and "Mark" in c.name for c in entries)

    def test_peter_and_paul_solemnity_color_red(self, universal):
        entries = get_sanctorale_celebrations(date(2026, 6, 29), universal)
        c = next(e for e in entries if "Peter" in e.name)
        assert c.color == LiturgicalColor.RED

    def test_anthony_memorial(self, universal):
        entries = get_sanctorale_celebrations(date(2026, 1, 17), universal)
        assert any(c.rank == Rank.MEMORIAL and "Anthony" in c.name for c in entries)

    def test_thomas_aquinas_memorial(self, universal):
        entries = get_sanctorale_celebrations(date(2026, 1, 28), universal)
        assert any(c.rank == Rank.MEMORIAL for c in entries)

    def test_all_souls_memorial(self, universal):
        entries = get_sanctorale_celebrations(date(2026, 11, 2), universal)
        assert any("All" in c.name and "Departed" in c.name for c in entries)

    def test_christmas_octave_stephen_feast(self, universal):
        entries = get_sanctorale_celebrations(date(2026, 12, 26), universal)
        assert any(c.rank == Rank.FEAST and "Stephen" in c.name for c in entries)

    def test_holy_innocents_feast(self, universal):
        entries = get_sanctorale_celebrations(date(2026, 12, 28), universal)
        assert any(c.rank == Rank.FEAST and "Innocents" in c.name for c in entries)


# ---------------------------------------------------------------------------
# 2. Rank and color invariants
# ---------------------------------------------------------------------------

class TestInvariants:

    def _all_entries(self, config):
        """Yield every sanctorale entry across the full calendar year."""
        from datetime import timedelta
        d = date(2026, 1, 1)
        while d.year == 2026:
            yield from get_sanctorale_celebrations(d, config)
            d += timedelta(days=1)

    def test_optional_memorial_has_optional_true(self, universal):
        for c in self._all_entries(universal):
            if c.rank == Rank.OPTIONAL_MEMORIAL:
                assert c.optional is True, f"{c.name}: optional_memorial must have optional=True"

    def test_non_optional_memorial_has_optional_false(self, universal):
        for c in self._all_entries(universal):
            if c.rank != Rank.OPTIONAL_MEMORIAL:
                assert c.optional is False, f"{c.name}: only optional_memorial may have optional=True"

    def test_all_universal_entries_have_correct_kind(self, universal):
        for c in self._all_entries(universal):
            assert c.kind == CelebrationKind.SANCTORALE_UNIVERSAL, \
                f"{c.name}: expected SANCTORALE_UNIVERSAL, got {c.kind}"

    def test_martyrs_are_red_or_white(self, universal):
        """Martyrs should be red; non-martyrs white. Spot-check a few."""
        martyrs = {
            date(2026, 1, 21),   # Agnes
            date(2026, 2, 23),   # Polycarp
            date(2026, 6, 29),   # Peter and Paul
            date(2026, 8, 10),   # Lawrence
            date(2026, 12, 26),  # Stephen
        }
        for d in martyrs:
            entries = get_sanctorale_celebrations(d, universal)
            for c in entries:
                assert c.color == LiturgicalColor.RED, \
                    f"{d} {c.name}: martyr feast should be red"

    def test_bvm_feasts_are_white(self, universal):
        bvm_dates = [
            date(2026, 1, 1),   # Mary, Mother of God
            date(2026, 8, 15),  # Assumption
            date(2026, 8, 22),  # Queenship
            date(2026, 9, 8),   # Nativity of BVM
            date(2026, 9, 15),  # Our Lady of Sorrows
            date(2026, 12, 8),  # Immaculate Conception
        ]
        for d in bvm_dates:
            for c in get_sanctorale_celebrations(d, universal):
                assert c.color == LiturgicalColor.WHITE, \
                    f"{d} {c.name}: BVM feast should be white"

    def test_rank_values_are_valid(self, universal):
        valid_ranks = {Rank.SOLEMNITY, Rank.LORD_FEAST, Rank.FEAST, Rank.MEMORIAL, Rank.OPTIONAL_MEMORIAL}
        for c in self._all_entries(universal):
            assert c.rank in valid_ranks, f"{c.name}: unexpected rank {c.rank}"


# ---------------------------------------------------------------------------
# 3. Multiple celebrations on one date
# ---------------------------------------------------------------------------

class TestMultipleCelebrations:

    def test_jan_20_has_two_optional_memorials(self, universal):
        # Fabian AND Sebastian
        entries = get_sanctorale_celebrations(date(2026, 1, 20), universal)
        assert len(entries) == 2
        names = {c.name for c in entries}
        assert any("Fabian" in n for n in names)
        assert any("Sebastian" in n for n in names)

    def test_feb_3_has_two_optional_memorials(self, universal):
        # Blaise AND Ansgar
        entries = get_sanctorale_celebrations(date(2026, 2, 3), universal)
        assert len(entries) == 2

    def test_may_25_has_three_optional_memorials(self, universal):
        # Bede, Gregory VII, Mary Magdalene de' Pazzi
        entries = get_sanctorale_celebrations(date(2026, 5, 25), universal)
        assert len(entries) == 3

    def test_sep_17_has_two_optional_memorials(self, universal):
        # Bellarmine AND Hildegard
        entries = get_sanctorale_celebrations(date(2026, 9, 17), universal)
        assert len(entries) == 2


# ---------------------------------------------------------------------------
# 4. Empty dates
# ---------------------------------------------------------------------------

class TestEmptyDates:

    def test_feb_15_has_no_entry(self, universal):
        # No GRC entry on Feb 15
        assert get_sanctorale_celebrations(date(2026, 2, 15), universal) == []

    def test_jun_16_has_no_entry(self, universal):
        assert get_sanctorale_celebrations(date(2026, 6, 16), universal) == []

    def test_oct_31_has_no_entry(self, universal):
        assert get_sanctorale_celebrations(date(2026, 10, 31), universal) == []


# ---------------------------------------------------------------------------
# 5. No temporale feasts in sanctorale
# ---------------------------------------------------------------------------

class TestNoTemporaleDates:
    """
    Dates whose celebrations are entirely owned by temporale.py must not
    appear in the sanctorale data file.
    """

    def test_christmas_not_in_sanctorale(self, universal):
        # Dec 25 is handled by temporale.py
        entries = get_sanctorale_celebrations(date(2026, 12, 25), universal)
        assert not any("Christmas" in c.name or "Nativity" in c.name for c in entries), \
            "Christmas should not appear in sanctorale"


# ---------------------------------------------------------------------------
# 6. Regional fallback
# ---------------------------------------------------------------------------

class TestRegionalFallback:

    def test_unknown_region_returns_universal_only(self):
        config = CalendarConfig(region="zz", locale="en_US")
        entries = get_sanctorale_celebrations(date(2026, 1, 1), config)
        # Should still get universal Mary Mother of God
        assert any("Mother of God" in c.name for c in entries)
        # All returned entries are universal kind
        for c in entries:
            assert c.kind == CelebrationKind.SANCTORALE_UNIVERSAL

    def test_us_config_returns_at_least_universal_entries(self, us):
        entries = get_sanctorale_celebrations(date(2026, 11, 1), us)
        assert any(c.rank == Rank.SOLEMNITY and "Saints" in c.name for c in entries)
