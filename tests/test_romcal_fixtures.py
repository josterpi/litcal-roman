"""
tests/test_romcal_fixtures.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Cross-validate get_liturgical_day against romcal.net CSV exports.

Fixtures are NOT committed to the repository.  To run these tests:
  1. Go to romcal.net → Calendar → CSV
  2. Download each year and save as tests/fixtures/<year>.csv
  3. Run: pytest tests/test_romcal_fixtures.py

Tests are skipped when the file is absent.
"""

import csv
from datetime import date, datetime
from pathlib import Path

import pytest

from litcal_roman.calendar import get_liturgical_day
from litcal_roman.models import CalendarConfig, LiturgicalColor, Rank

_US = CalendarConfig.us()

_FIXTURES_DIR = Path(__file__).parent / "fixtures"

TEST_YEARS = [2024, 2025, 2026, 2027]

def _parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        return datetime.strptime(s, "%m/%d/%Y").date()


_ROMCAL_COLOR = {
    "White":  LiturgicalColor.WHITE,
    "Green":  LiturgicalColor.GREEN,
    "Red":    LiturgicalColor.RED,
    "Purple": LiturgicalColor.VIOLET,
    "Violet": LiturgicalColor.VIOLET,
    "Rose":   LiturgicalColor.ROSE,
}

# Minimum rank expected for each romcal rank label.
_ROMCAL_MIN_RANK = {
    "Solemnity":      Rank.SOLEMNITY,       # includes TRIDUUM and EASTER_SUNDAY
    "Memorial":       Rank.MEMORIAL,
    "Opt. Mem.":      Rank.OPTIONAL_MEMORIAL,
    "Commem.":        Rank.OPTIONAL_MEMORIAL,  # Lenten commemoration; GNLYC allows Memorial to remain
    "Weekday":        Rank.FERIA,
    "Feast":          Rank.FEAST,           # saints' feasts (apostles, etc.)
    "F. of the Lord": Rank.FEAST,           # feasts of the Lord; ours may be LORD_FEAST (≥ FEAST)
    "Sunday":         Rank.FEAST,           # OT Sunday = FEAST; others = SOLEMNITY
    "Ash Wednesday":  Rank.SOLEMNITY,
    "Holy Week":      Rank.FERIA,           # Holy Mon/Tue/Wed are ordinary ferias
    "Triduum":        Rank.TRIDUUM,
}

# Labels where the rank must be an exact match, not just a minimum.
# "Commem." is excluded: romcal demotes Lenten obligatory memorials to
# commemorations, but the current GNLYC permits them to remain at Memorial rank.
_EXACT_RANK = {"Memorial", "Opt. Mem.", "Weekday", "Feast", "Holy Week"}


def _load_rows(year: int) -> list[dict]:
    path = _FIXTURES_DIR / f"{year}.csv"
    if not path.exists():
        return []
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.mark.parametrize("year", TEST_YEARS)
def test_rank_against_romcal(year):
    rows = _load_rows(year)
    if not rows:
        pytest.skip(f"fixture tests/fixtures/{year}.csv not found")

    failures: list[str] = []
    for row in rows:
        d = _parse_date(row["Date"])
        label = row["Rank"].strip()

        min_rank = _ROMCAL_MIN_RANK.get(label)
        if min_rank is None:
            failures.append(f"{d}: unrecognised romcal rank {label!r}")
            continue

        ld = get_liturgical_day(d, _US)
        actual = ld.celebration.rank

        # romcal labels multi-celebration rows (Celebration contains ";") as "Opt. Mem."
        # regardless of winner rank — use min check for those rows.
        multi = ";" in row.get("Celebration", "")
        use_exact = label in _EXACT_RANK and not multi

        if use_exact:
            ok = actual == min_rank
        else:
            ok = actual >= min_rank

        if not ok:
            failures.append(
                f"{d}: rank {actual!s} "
                f"{'!=' if use_exact else '<'} "
                f"expected {min_rank!s} "
                f"(romcal: {label!r}, won: {ld.celebration.name!r})"
            )

    assert not failures, f"{len(failures)} rank failures in {year}:\n" + "\n".join(failures)


@pytest.mark.parametrize("year", TEST_YEARS)
def test_color_against_romcal(year):
    rows = _load_rows(year)
    if not rows:
        pytest.skip(f"fixture tests/fixtures/{year}.csv not found")

    failures: list[str] = []
    for row in rows:
        d = _parse_date(row["Date"])
        romcal_color_str = row["Color"].strip()

        expected = _ROMCAL_COLOR.get(romcal_color_str)
        if expected is None:
            failures.append(f"{d}: unrecognised romcal color {romcal_color_str!r}")
            continue

        ld = get_liturgical_day(d, _US)
        actual = ld.celebration.color

        if actual != expected:
            failures.append(
                f"{d}: color {actual!s} != expected {expected!s} "
                f"(romcal: {romcal_color_str!r}, won: {ld.celebration.name!r})"
            )

    assert not failures, f"{len(failures)} color failures in {year}:\n" + "\n".join(failures)
