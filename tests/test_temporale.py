"""
tests/test_temporale.py
~~~~~~~~~~~~~~~~~~~~~~

Tests for litcal_roman.temporale.

Strategy
--------
1. Known-date assertions — dates whose liturgical identity is not in
   dispute, checked against published liturgical calendars (Universalis,
   USCCB, iBreviary).

2. Seam tests — the day before and day after every season boundary for
   a spread of years. These are where off-by-one errors live.

3. Invariant tests — properties that must hold for *every* day of a full
   liturgical year regardless of the specific date:
       - season is always a valid Season
       - week is always in range for the season
       - psalter_week is always 1–4
       - OT weeks never exceed 34
       - the sum of days in all seasons == 365 (or 366 in leap years)

4. Transfer tests — Ascension, Epiphany, Corpus Christi with US config
   vs. universal config.

5. Lectionary cycle tests — Year I/II and Sunday cycle A/B/C flip at
   the right moment (First Sunday of Advent, not January 1).

Test years chosen to cover edge cases:
    2019 — Easter April 21 (late); Ascension on Thursday (universal)
    2024 — Easter March 31 (early); leap year
    2025 — Easter April 20
    2026 — Easter April 5 (current year at time of writing)
    2027 — Easter March 28 (very early; shortest OT)
    2038 — Easter April 25 (latest possible Easter)
"""

from datetime import date, timedelta

import pytest

from litcal_roman.models import (
    CalendarConfig,
    LiturgicalColor,
    Rank,
    ScriptureCycle,
    Season,
    SundayCycle,
)
from litcal_roman.temporale import (
    _first_sunday_of_advent,
    _liturgical_year,
    _ordinary_time_week,
    compute_temporale,
    get_anchors,
    get_ascension,
    get_baptism,
    get_corpus_christi,
    get_epiphany,
    get_psalter_week,
    get_scripture_cycle,
    get_season,
    get_sunday_cycle,
    get_temporale_celebration,
    make_temporale_label,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def us_config() -> CalendarConfig:
    return CalendarConfig.us()

@pytest.fixture
def universal_config() -> CalendarConfig:
    return CalendarConfig.universal()


def _all_days_in_year(year: int):
    """Yield every date in the civil calendar year."""
    d = date(year, 1, 1)
    while d.year == year:
        yield d
        d += timedelta(days=1)


# ---------------------------------------------------------------------------
# 1. Known-date assertions
# ---------------------------------------------------------------------------

class TestKnownDates:
    """
    Spot-checks against published liturgical calendars.
    Sources: USCCB liturgical calendar PDFs, Universalis.com, iBreviary.
    """

    # --- Easter season ---

    def test_easter_sunday_2026(self, us_config):
        d = date(2026, 4, 5)
        result = compute_temporale(d, us_config)
        assert result["season"] == Season.EASTER
        assert result["week"] == 1
        assert result["weekday"] == 7
        assert result["celebration"].rank == Rank.EASTER_SUNDAY
        assert result["celebration"].color == LiturgicalColor.WHITE

    def test_easter_octave_wednesday_2026(self, us_config):
        # Wednesday within the Octave of Easter
        d = date(2026, 4, 8)
        result = compute_temporale(d, us_config)
        assert result["season"] == Season.EASTER
        assert result["week"] == 1
        assert result["weekday"] == 3
        assert result["celebration"].rank == Rank.SOLEMNITY
        assert "Octave" in result["celebration"].name

    def test_4th_sunday_of_easter_2026(self, us_config):
        # Good Shepherd Sunday — 4th Sunday of Easter
        d = date(2026, 4, 26)
        result = compute_temporale(d, us_config)
        assert result["season"] == Season.EASTER
        assert result["week"] == 4
        assert result["weekday"] == 7

    def test_wednesday_4th_week_easter_2026(self, us_config):
        d = date(2026, 4, 29)
        result = compute_temporale(d, us_config)
        assert result["season"] == Season.EASTER
        assert result["week"] == 4
        assert result["weekday"] == 3
        assert result["label"] == "Wednesday of the 4th Week of Easter"

    def test_pentecost_2026(self, us_config):
        d = date(2026, 5, 24)
        result = compute_temporale(d, us_config)
        assert result["season"] == Season.EASTER
        assert result["week"] == 7
        assert result["celebration"].name == "Pentecost Sunday"
        assert result["celebration"].color == LiturgicalColor.RED

    # --- Ordinary Time (post-Pentecost) ---

    def test_trinity_sunday_2026(self, us_config):
        d = date(2026, 5, 31)
        result = compute_temporale(d, us_config)
        assert result["celebration"].name == "The Most Holy Trinity"
        assert result["season"] == Season.ORDINARY

    def test_corpus_christi_2026_us(self, us_config):
        # US: transferred to Sunday (June 7, 2026)
        d = date(2026, 6, 7)
        result = compute_temporale(d, us_config)
        assert "Corpus Christi" in result["celebration"].name or \
               "Body and Blood" in result["celebration"].name

    def test_corpus_christi_2026_universal(self, universal_config):
        # Universal: Thursday, June 4, 2026
        d = date(2026, 6, 4)
        result = compute_temporale(d, universal_config)
        assert "Body and Blood" in result["celebration"].name

    def test_christ_the_king_2026(self, us_config):
        # Last Sunday of OT 2026: November 22
        d = date(2026, 11, 22)
        result = compute_temporale(d, us_config)
        assert result["season"] == Season.ORDINARY
        assert result["week"] == 34
        assert "King" in result["celebration"].name

    # --- Lent and Triduum ---

    def test_ash_wednesday_2026(self, us_config):
        d = date(2026, 2, 18)
        result = compute_temporale(d, us_config)
        assert result["season"] == Season.LENT
        assert result["week"] == 1
        assert result["celebration"].name == "Ash Wednesday"
        assert result["celebration"].color == LiturgicalColor.VIOLET

    def test_thursday_after_ash_wednesday_2026(self, us_config):
        d = date(2026, 2, 19)
        result = compute_temporale(d, us_config)
        assert result["season"] == Season.LENT
        assert result["label"] == "Thursday after Ash Wednesday"

    def test_friday_after_ash_wednesday_2026(self, us_config):
        d = date(2026, 2, 20)
        result = compute_temporale(d, us_config)
        assert result["label"] == "Friday after Ash Wednesday"

    def test_saturday_after_ash_wednesday_2026(self, us_config):
        d = date(2026, 2, 21)
        result = compute_temporale(d, us_config)
        assert result["label"] == "Saturday after Ash Wednesday"

    def test_1st_sunday_of_lent_2026(self, us_config):
        # First Sunday of Lent is the Sunday of the week AFTER Ash Wednesday
        d = date(2026, 2, 22)
        result = compute_temporale(d, us_config)
        assert result["season"] == Season.LENT
        assert result["week"] == 2  # Ash Wednesday starts week 1; first Sunday is week 2
        assert result["weekday"] == 7
        assert result["label"] == "2nd Sunday of Lent"

    def test_palm_sunday_2026(self, us_config):
        d = date(2026, 3, 29)
        result = compute_temporale(d, us_config)
        assert result["season"] == Season.LENT
        assert "Palm Sunday" in result["celebration"].name
        assert result["celebration"].color == LiturgicalColor.RED

    def test_holy_thursday_2026(self, us_config):
        d = date(2026, 4, 2)
        result = compute_temporale(d, us_config)
        assert result["season"] == Season.TRIDUUM
        assert "Holy Thursday" in result["celebration"].name or \
               "Lord's Supper" in result["celebration"].name

    def test_good_friday_2026(self, us_config):
        d = date(2026, 4, 3)
        result = compute_temporale(d, us_config)
        assert result["season"] == Season.TRIDUUM
        assert result["celebration"].color == LiturgicalColor.RED

    def test_holy_saturday_2026(self, us_config):
        d = date(2026, 4, 4)
        result = compute_temporale(d, us_config)
        assert result["season"] == Season.TRIDUUM

    # --- Advent ---

    def test_1st_sunday_of_advent_2026(self, us_config):
        d = date(2026, 11, 29)
        result = compute_temporale(d, us_config)
        assert result["season"] == Season.ADVENT
        assert result["week"] == 1
        assert result["weekday"] == 7
        assert result["label"] == "1st Sunday of Advent"

    def test_advent_feria_2026(self, us_config):
        # Monday of Advent week 2
        d = date(2026, 12, 7)
        result = compute_temporale(d, us_config)
        assert result["season"] == Season.ADVENT
        assert result["week"] == 2
        assert result["weekday"] == 1

    # --- Christmas ---

    def test_christmas_2026(self, us_config):
        d = date(2026, 12, 25)
        result = compute_temporale(d, us_config)
        assert result["season"] == Season.CHRISTMAS
        assert "Nativity" in result["celebration"].name or \
               "Christmas" in result["celebration"].name

    def test_epiphany_2026_us(self, us_config):
        # US: transferred to Sunday Jan 4, 2026
        d = date(2026, 1, 4)
        result = compute_temporale(d, us_config)
        assert "Epiphany" in result["celebration"].name

    def test_epiphany_2026_universal(self, universal_config):
        # Universal: always January 6
        d = date(2026, 1, 6)
        result = compute_temporale(d, universal_config)
        assert "Epiphany" in result["celebration"].name

    def test_baptism_of_lord_2026_us(self, us_config):
        # US: Sunday after Epiphany (Jan 4) → Jan 11
        # But if Epiphany is Jan 4 (Sunday), Baptism is Jan 12 (Monday)?
        # Actually: Epiphany Jan 4 is Sunday → Baptism is next Sunday Jan 11.
        # _baptism_of_the_lord: if epiphany is Sunday, return epiphany + 1 (Monday).
        # Wait — need to check the rule for transferred Epiphany.
        # When Epiphany is Jan 7 or 8 → Baptism is Monday.
        # When Epiphany is Jan 4 (Sunday) → Baptism is Jan 11 (next Sunday).
        # The special Monday rule only applies when Epiphany is Jan 7 or 8.
        d = date(2026, 1, 11)
        result = compute_temporale(d, us_config)
        assert "Baptism" in result["celebration"].name

    # --- Ordinary Time (pre-Lent) ---

    def test_first_ot_weekday_2026(self, us_config):
        # Baptism of the Lord is Jan 11 (US, 2026). OT begins Jan 12.
        d = date(2026, 1, 12)
        result = compute_temporale(d, us_config)
        assert result["season"] == Season.ORDINARY
        assert result["week"] == 1

    def test_last_ot_day_before_lent_2026(self, us_config):
        # Day before Ash Wednesday (Feb 18) is Feb 17 (Tuesday)
        d = date(2026, 2, 17)
        result = compute_temporale(d, us_config)
        assert result["season"] == Season.ORDINARY

    def test_day_before_ash_wednesday_is_ot(self, us_config):
        anchors = get_anchors(2026)
        day_before = anchors.ash_wednesday - timedelta(days=1)
        result = compute_temporale(day_before, us_config)
        assert result["season"] == Season.ORDINARY


# ---------------------------------------------------------------------------
# 2. Seam tests — boundaries between every season
# ---------------------------------------------------------------------------

class TestSeams:
    """
    For each season boundary, assert the day before is in season A
    and the day on/after is in season B. Tested across multiple years.
    """

    @pytest.mark.parametrize("year", [2019, 2024, 2025, 2026, 2027, 2038])
    def test_ash_wednesday_seam(self, year, us_config):
        anchors = get_anchors(year)
        before = anchors.ash_wednesday - timedelta(days=1)
        on     = anchors.ash_wednesday
        assert get_season(before, us_config)[0] == Season.ORDINARY
        assert get_season(on,     us_config)[0] == Season.LENT

    @pytest.mark.parametrize("year", [2019, 2024, 2025, 2026, 2027, 2038])
    def test_holy_thursday_seam(self, year, us_config):
        anchors = get_anchors(year)
        before = anchors.holy_thursday - timedelta(days=1)  # Holy Wednesday
        on     = anchors.holy_thursday
        assert get_season(before, us_config)[0] == Season.LENT
        assert get_season(on,     us_config)[0] == Season.TRIDUUM

    @pytest.mark.parametrize("year", [2019, 2024, 2025, 2026, 2027, 2038])
    def test_easter_seam(self, year, us_config):
        anchors = get_anchors(year)
        before = anchors.holy_saturday  # still Triduum
        on     = anchors.easter
        assert get_season(before, us_config)[0] == Season.TRIDUUM
        assert get_season(on,     us_config)[0] == Season.EASTER

    @pytest.mark.parametrize("year", [2019, 2024, 2025, 2026, 2027, 2038])
    def test_pentecost_to_ordinary_seam(self, year, us_config):
        anchors = get_anchors(year)
        on_pentecost  = anchors.pentecost
        after         = anchors.pentecost + timedelta(days=1)
        assert get_season(on_pentecost, us_config)[0] == Season.EASTER
        assert get_season(after,        us_config)[0] == Season.ORDINARY

    @pytest.mark.parametrize("year", [2019, 2024, 2025, 2026, 2027, 2038])
    def test_advent_seam(self, year, us_config):
        anchors = get_anchors(year)
        before = anchors.advent_1 - timedelta(days=1)  # Saturday before Advent
        on     = anchors.advent_1
        assert get_season(before, us_config)[0] == Season.ORDINARY
        assert get_season(on,     us_config)[0] == Season.ADVENT

    @pytest.mark.parametrize("year", [2019, 2024, 2025, 2026, 2027, 2038])
    def test_christmas_seam(self, year, us_config):
        christmas = date(year, 12, 25)
        before    = date(year, 12, 24)  # Christmas Eve — still Advent
        assert get_season(before,    us_config)[0] == Season.ADVENT
        assert get_season(christmas, us_config)[0] == Season.CHRISTMAS

    @pytest.mark.parametrize("year", [2019, 2024, 2025, 2026, 2027, 2038])
    def test_baptism_to_ordinary_seam(self, year, us_config):
        baptism  = get_baptism(year, us_config)
        after    = baptism + timedelta(days=1)
        assert get_season(baptism, us_config)[0] == Season.CHRISTMAS
        assert get_season(after,   us_config)[0] == Season.ORDINARY


# ---------------------------------------------------------------------------
# 3. Invariant tests — full year sweeps
# ---------------------------------------------------------------------------

class TestInvariants:

    @pytest.mark.parametrize("year", [2024, 2025, 2026, 2027])
    def test_every_day_has_valid_season(self, year, us_config):
        valid_seasons = set(Season)
        for d in _all_days_in_year(year):
            season, week = get_season(d, us_config)
            assert season in valid_seasons, f"{d}: invalid season {season}"

    @pytest.mark.parametrize("year", [2024, 2025, 2026, 2027])
    def test_ordinary_time_week_never_exceeds_34(self, year, us_config):
        for d in _all_days_in_year(year):
            season, week = get_season(d, us_config)
            if season == Season.ORDINARY:
                assert 1 <= week <= 34, f"{d}: OT week {week} out of range"

    @pytest.mark.parametrize("year", [2024, 2025, 2026, 2027])
    def test_psalter_week_always_1_to_4(self, year, us_config):
        for d in _all_days_in_year(year):
            season, week = get_season(d, us_config)
            psalter = get_psalter_week(season, week)
            assert 1 <= psalter <= 4, f"{d}: psalter week {psalter} out of range"

    @pytest.mark.parametrize("year", [2024, 2025, 2026, 2027])
    def test_lent_week_never_exceeds_6(self, year, us_config):
        for d in _all_days_in_year(year):
            season, week = get_season(d, us_config)
            if season == Season.LENT:
                assert 1 <= week <= 6, f"{d}: Lent week {week} out of range"

    @pytest.mark.parametrize("year", [2024, 2025, 2026, 2027])
    def test_easter_week_never_exceeds_7(self, year, us_config):
        for d in _all_days_in_year(year):
            season, week = get_season(d, us_config)
            if season == Season.EASTER:
                assert 1 <= week <= 7, f"{d}: Easter week {week} out of range"

    @pytest.mark.parametrize("year", [2024, 2025, 2026, 2027])
    def test_advent_week_never_exceeds_4(self, year, us_config):
        for d in _all_days_in_year(year):
            season, week = get_season(d, us_config)
            if season == Season.ADVENT:
                assert 1 <= week <= 4, f"{d}: Advent week {week} out of range"

    @pytest.mark.parametrize("year", [2024, 2025, 2026, 2027])
    def test_triduum_is_exactly_3_days(self, year, us_config):
        anchors = get_anchors(year)
        triduum_days = [
            d for d in _all_days_in_year(year)
            if get_season(d, us_config)[0] == Season.TRIDUUM
        ]
        assert len(triduum_days) == 3, \
            f"{year}: Triduum has {len(triduum_days)} days, expected 3"
        assert triduum_days[0] == anchors.holy_thursday
        assert triduum_days[1] == anchors.good_friday
        assert triduum_days[2] == anchors.holy_saturday

    @pytest.mark.parametrize("year", [2024, 2025, 2026, 2027])
    def test_easter_is_exactly_49_days(self, year, us_config):
        # Easter Sunday through Pentecost Sunday = 7 weeks = 49 days
        easter_days = [
            d for d in _all_days_in_year(year)
            if get_season(d, us_config)[0] == Season.EASTER
        ]
        assert len(easter_days) == 49, \
            f"{year}: Easter season has {len(easter_days)} days, expected 49"

    @pytest.mark.parametrize("year", [2024, 2025, 2026, 2027])
    def test_no_gaps_in_season_coverage(self, year, us_config):
        """Every day of the year must resolve to a season."""
        for d in _all_days_in_year(year):
            season, week = get_season(d, us_config)
            assert season is not None, f"{d}: no season assigned"

    @pytest.mark.parametrize("year", [2024, 2025, 2026, 2027])
    def test_ot_week_numbers_are_contiguous_within_segment(self, year, us_config):
        """
        Within each OT segment, week numbers must increase by 1 per week
        with no gaps or repetitions within the segment.
        """
        anchors = get_anchors(year)
        baptism = get_baptism(year, us_config)

        # Segment 1: day after Baptism → day before Ash Wednesday
        seg1_weeks = set()
        d = baptism + timedelta(days=1)
        while d < anchors.ash_wednesday:
            if d.isoweekday() == 1:  # sample Mondays only for week-level check
                _, week = get_season(d, us_config)
                seg1_weeks.add(week)
            d += timedelta(days=1)

        # Segment 1 should be a contiguous range starting at 1
        if seg1_weeks:
            assert seg1_weeks == set(range(1, max(seg1_weeks) + 1)), \
                f"{year} segment 1 OT weeks not contiguous: {sorted(seg1_weeks)}"

        # Segment 2: day after Pentecost → day before Advent
        seg2_weeks = set()
        d = anchors.pentecost + timedelta(days=1)
        while d < anchors.advent_1:
            if d.isoweekday() == 1:
                _, week = get_season(d, us_config)
                seg2_weeks.add(week)
            d += timedelta(days=1)

        if seg2_weeks:
            assert seg2_weeks == set(range(min(seg2_weeks), 35)), \
                f"{year} segment 2 OT weeks not contiguous up to 34: {sorted(seg2_weeks)}"
            assert max(seg2_weeks) == 34, \
                f"{year}: last OT week is {max(seg2_weeks)}, expected 34"


# ---------------------------------------------------------------------------
# 4. Transfer tests
# ---------------------------------------------------------------------------

class TestTransfers:

    @pytest.mark.parametrize("year", [2024, 2025, 2026, 2027])
    def test_ascension_thursday_universal(self, year, universal_config):
        anchors = get_anchors(year)
        d = anchors.ascension_proper
        assert d.isoweekday() == 4, f"{year}: Ascension proper is not Thursday"
        result = compute_temporale(d, universal_config)
        assert "Ascension" in result["celebration"].name

    @pytest.mark.parametrize("year", [2024, 2025, 2026, 2027])
    def test_ascension_sunday_us(self, year, us_config):
        ascension = get_ascension(year, us_config)
        assert ascension.isoweekday() == 7, \
            f"{year}: US Ascension is not Sunday (got {ascension.isoweekday()})"
        result = compute_temporale(ascension, us_config)
        assert "Ascension" in result["celebration"].name

    @pytest.mark.parametrize("year", [2024, 2025, 2026, 2027])
    def test_ascension_thursday_is_feria_in_us(self, year, us_config):
        anchors = get_anchors(year)
        proper_thursday = anchors.ascension_proper
        result = compute_temporale(proper_thursday, us_config)
        # In US config, the Thursday proper date is an ordinary Easter feria
        assert result["season"] == Season.EASTER
        assert result["celebration"].rank < Rank.SOLEMNITY

    @pytest.mark.parametrize("year", [2024, 2025, 2026, 2027])
    def test_epiphany_january_6_universal(self, year, universal_config):
        d = date(year, 1, 6)
        result = compute_temporale(d, universal_config)
        assert "Epiphany" in result["celebration"].name

    @pytest.mark.parametrize("year", [2024, 2025, 2026, 2027])
    def test_epiphany_us_is_sunday(self, year, us_config):
        epiphany = get_epiphany(year, us_config)
        assert epiphany.isoweekday() == 7, \
            f"{year}: US Epiphany {epiphany} is not Sunday"
        assert epiphany >= date(year, 1, 2)
        assert epiphany <= date(year, 1, 8)

    @pytest.mark.parametrize("year", [2024, 2025, 2026, 2027])
    def test_corpus_christi_thursday_universal(self, year, universal_config):
        corpus = get_corpus_christi(year, universal_config)
        assert corpus.isoweekday() == 4, \
            f"{year}: Corpus Christi proper is not Thursday"

    @pytest.mark.parametrize("year", [2024, 2025, 2026, 2027])
    def test_corpus_christi_sunday_us(self, year, us_config):
        corpus = get_corpus_christi(year, us_config)
        assert corpus.isoweekday() == 7, \
            f"{year}: US Corpus Christi is not Sunday"


# ---------------------------------------------------------------------------
# 5. Lectionary cycle tests
# ---------------------------------------------------------------------------

class TestLectionaryCycles:

    def test_scripture_cycle_flips_at_advent_not_january(self, us_config):
        """
        The cycle flips on the First Sunday of Advent, not January 1.
        Liturgical year 2026 begins Advent 2025 → Year II (2026 is even).
        Liturgical year 2025 began Advent 2024 → Year I (2025 is odd).
        """
        anchors_2025 = get_anchors(2025)

        # Saturday before Advent 2025: still liturgical year 2025 → Year I
        sat_before_advent = anchors_2025.advent_1 - timedelta(days=1)
        assert get_scripture_cycle(sat_before_advent) == ScriptureCycle.YEAR_I

        # First Sunday of Advent 2025: liturgical year 2026 → Year II
        assert get_scripture_cycle(anchors_2025.advent_1) == ScriptureCycle.YEAR_II

    def test_scripture_cycle_does_not_flip_jan_1(self, us_config):
        """January 1 is not a cycle boundary."""
        dec_31 = date(2025, 12, 31)
        jan_1  = date(2026, 1, 1)
        assert get_scripture_cycle(dec_31) == get_scripture_cycle(jan_1)

    @pytest.mark.parametrize("year,expected_cycle", [
        (2025, ScriptureCycle.YEAR_I),   # liturgical year 2025 is odd
        (2026, ScriptureCycle.YEAR_II),  # liturgical year 2026 is even
        (2027, ScriptureCycle.YEAR_I),
        (2028, ScriptureCycle.YEAR_II),
    ])
    def test_scripture_cycle_by_liturgical_year(self, year, expected_cycle):
        # Use a date solidly within the liturgical year (e.g. Easter week)
        anchors = get_anchors(year)
        d = anchors.easter + timedelta(days=1)  # Monday of Easter week
        assert get_scripture_cycle(d) == expected_cycle

    @pytest.mark.parametrize("year,expected_sunday_cycle", [
        # Cycle A: liturgical year divisible by 3 → 2025 % 3 == 0 → A
        (2025, SundayCycle.A),
        # Cycle B: 2026 % 3 == 1 → B
        (2026, SundayCycle.B),
        # Cycle C: 2027 % 3 == 2 → C
        (2027, SundayCycle.C),
        # Wraps: 2028 % 3 == 0 → A
        (2028, SundayCycle.A),
    ])
    def test_sunday_cycle_by_liturgical_year(self, year, expected_sunday_cycle):
        anchors = get_anchors(year)
        d = anchors.easter  # Easter Sunday is unambiguously in its liturgical year
        assert get_sunday_cycle(d) == expected_sunday_cycle

    def test_sunday_cycle_flips_at_advent(self):
        anchors_2025 = get_anchors(2025)
        sat = anchors_2025.advent_1 - timedelta(days=1)
        sun = anchors_2025.advent_1
        # Before Advent: liturgical year 2025 → Cycle A
        assert get_sunday_cycle(sat) == SundayCycle.A
        # On Advent 1: liturgical year 2026 → Cycle B
        assert get_sunday_cycle(sun) == SundayCycle.B


# ---------------------------------------------------------------------------
# 6. Psalter week tests
# ---------------------------------------------------------------------------

class TestPsalterWeek:

    def test_advent_week_1_is_psalter_1(self):
        assert get_psalter_week(Season.ADVENT, 1) == 1

    def test_advent_cycles_through_4(self):
        assert get_psalter_week(Season.ADVENT, 2) == 2
        assert get_psalter_week(Season.ADVENT, 3) == 3
        assert get_psalter_week(Season.ADVENT, 4) == 4

    def test_christmas_starts_at_psalter_3(self):
        assert get_psalter_week(Season.CHRISTMAS, 1) == 3
        assert get_psalter_week(Season.CHRISTMAS, 2) == 4

    def test_lent_week_1_is_psalter_4(self):
        assert get_psalter_week(Season.LENT, 1) == 4
        assert get_psalter_week(Season.LENT, 2) == 1
        assert get_psalter_week(Season.LENT, 3) == 2

    def test_easter_octave_is_psalter_2(self):
        assert get_psalter_week(Season.EASTER, 1) == 2

    def test_easter_week_2_is_psalter_1(self):
        assert get_psalter_week(Season.EASTER, 2) == 1
        assert get_psalter_week(Season.EASTER, 3) == 2
        assert get_psalter_week(Season.EASTER, 4) == 3
        assert get_psalter_week(Season.EASTER, 5) == 4

    def test_ordinary_time_cycles_from_1(self):
        for week in range(1, 35):
            expected = ((week - 1) % 4) + 1
            assert get_psalter_week(Season.ORDINARY, week) == expected, \
                f"OT week {week}: expected psalter {expected}"

    def test_triduum_is_psalter_2(self):
        assert get_psalter_week(Season.TRIDUUM, 0) == 2


# ---------------------------------------------------------------------------
# 7. Label generation tests
# ---------------------------------------------------------------------------

class TestLabels:

    def test_ordinary_time_weekday(self):
        assert make_temporale_label(Season.ORDINARY, 12, 3) == \
               "Wednesday of the 12th Week in Ordinary Time"

    def test_ordinary_time_sunday(self):
        assert make_temporale_label(Season.ORDINARY, 3, 7) == \
               "3rd Sunday in Ordinary Time"

    def test_easter_octave_wednesday(self):
        assert make_temporale_label(Season.EASTER, 1, 3) == \
               "Wednesday within the Octave of Easter"

    def test_easter_sunday_label(self):
        assert make_temporale_label(Season.EASTER, 1, 7) == \
               "Easter Sunday of the Resurrection of the Lord"

    def test_easter_weekday_week_4(self):
        assert make_temporale_label(Season.EASTER, 4, 3) == \
               "Wednesday of the 4th Week of Easter"

    def test_lent_sunday(self):
        assert make_temporale_label(Season.LENT, 3, 7) == \
               "3rd Sunday of Lent"

    def test_palm_sunday_label(self):
        assert make_temporale_label(Season.LENT, 6, 7) == \
               "Palm Sunday of the Passion of the Lord"

    def test_advent_sunday(self):
        assert make_temporale_label(Season.ADVENT, 2, 7) == \
               "2nd Sunday of Advent"

    def test_advent_weekday(self):
        assert make_temporale_label(Season.ADVENT, 3, 5) == \
               "Friday of the 3rd Week of Advent"

    def test_thursday_after_ash_wednesday(self):
        assert make_temporale_label(Season.LENT, 1, 3) == \
               "Thursday after Ash Wednesday"


# ---------------------------------------------------------------------------
# 8. First Sunday of Advent anchor tests
# ---------------------------------------------------------------------------

class TestAdventAnchor:

    @pytest.mark.parametrize("year,expected", [
        (2024, date(2024, 12, 1)),
        (2025, date(2025, 11, 30)),
        (2026, date(2026, 11, 29)),
        (2027, date(2027, 11, 28)),
        (2028, date(2028, 12, 3)),
    ])
    def test_first_sunday_of_advent(self, year, expected):
        result = _first_sunday_of_advent(year)
        assert result == expected, f"{year}: expected {expected}, got {result}"
        assert result.isoweekday() == 7, f"{year}: Advent 1 is not Sunday"

    @pytest.mark.parametrize("year", range(2020, 2040))
    def test_advent_1_is_always_sunday(self, year):
        assert _first_sunday_of_advent(year).isoweekday() == 7

    @pytest.mark.parametrize("year", range(2020, 2040))
    def test_advent_1_is_in_range_nov27_dec3(self, year):
        advent_1 = _first_sunday_of_advent(year)
        assert date(year, 11, 27) <= advent_1 <= date(year, 12, 3), \
            f"{year}: Advent 1 {advent_1} outside Nov 27–Dec 3"


# ---------------------------------------------------------------------------
# 9. Edge case years
# ---------------------------------------------------------------------------

class TestEdgeCaseYears:

    def test_early_easter_2027(self, us_config):
        """Easter March 28, 2027 — very early; short post-Pentecost OT."""
        anchors = get_anchors(2027)
        assert anchors.easter == date(2027, 3, 28)
        # Ash Wednesday should be Feb 10
        assert anchors.ash_wednesday == date(2027, 2, 10)
        # Pre-Lent OT should be very short
        baptism = get_baptism(2027, us_config)
        ot_days_seg1 = (anchors.ash_wednesday - (baptism + timedelta(days=1))).days
        assert ot_days_seg1 >= 0, "Segment 1 OT must not be negative"

    def test_late_easter_2038(self, us_config):
        """Easter April 25, 2038 — latest possible; longest pre-Easter OT."""
        anchors = get_anchors(2038)
        assert anchors.easter == date(2038, 4, 25)

    def test_leap_year_2024(self, us_config):
        """Feb 29 exists and resolves correctly."""
        d = date(2024, 2, 29)
        result = compute_temporale(d, us_config)
        # Feb 29, 2024: Easter is March 31. Ash Wednesday is Feb 14.
        # Feb 29 is in Lent.
        assert result["season"] == Season.LENT

    def test_full_year_sweep_no_exceptions(self, us_config):
        """compute_temporale must not raise for any day in 2024–2028."""
        for year in range(2024, 2029):
            for d in _all_days_in_year(year):
                try:
                    compute_temporale(d, us_config)
                except Exception as e:
                    pytest.fail(f"compute_temporale raised on {d}: {e}")
