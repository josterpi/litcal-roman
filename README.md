# litcal-roman

Roman Catholic liturgical calendar computation for Python.

Given a date and a calendar configuration, `litcal-roman` returns the fully resolved liturgical day: the winning celebration after precedence resolution, any displaced celebrations, the liturgical season and week, vestment color, psalter week, and lectionary cycles.

Precedence rules follow the [General Norms for the Liturgical Year and the Calendar](https://www.catholicculture.org/culture/library/view.cfm?id=10842)) (GNLYC), with transfer rules applied per region.

## Installation

```
pip install litcal-roman
```

Requires Python 3.12+.

## Quick start

```python
from datetime import date
from litcal_roman import get_liturgical_day, CalendarConfig

config = CalendarConfig.us()
day = get_liturgical_day(date(2026, 3, 29), config)

print(day.celebration.name)   # "Palm Sunday of the Passion of the Lord"
print(day.season)             # Season.LENT
print(day.celebration.color)  # LiturgicalColor.RED
print(day.sunday_cycle)       # SundayCycle.B
```

When a sanctorale celebration is displaced by a higher-ranked temporale day, it appears in `day.displaced`:

```python
day = get_liturgical_day(date(2026, 6, 22), config)  # Immaculate Heart / 12th Sunday OT
print(day.celebration.name)    # "Twelfth Sunday in Ordinary Time"
print(day.displaced[0].name)   # "Immaculate Heart of the Blessed Virgin Mary"
```

## CalendarConfig

```python
CalendarConfig.universal()   # No transfers, no national propers
CalendarConfig.us()          # USCCB propers + standard US transfers (default)
```

The US configuration transfers Ascension to the 7th Sunday of Easter, Epiphany to the nearest Sunday, and Corpus Christi to the Sunday after Trinity Sunday. These can be overridden individually:

```python
config = CalendarConfig(
    region="us",
    transfer_ascension=False,   # keep Ascension on Thursday
    transfer_epiphany=True,
    transfer_corpus_christi=True,
)
```

## LiturgicalDay fields

| Field | Type | Description |
|---|---|---|
| `date` | `date` | Civil date |
| `season` | `Season` | Liturgical season |
| `week` | `int` | Week within the season |
| `weekday` | `int` | ISO weekday (1=Mon, 7=Sun) |
| `psalter_week` | `int` | Week of the four-week Psalter (1–4) |
| `celebration` | `Celebration` | Winning celebration after precedence resolution |
| `displaced` | `tuple[Celebration, ...]` | Celebrations that lost precedence, descending by rank |
| `scripture_cycle` | `ScriptureCycle` | Year I or II (weekday lectionary) |
| `sunday_cycle` | `SundayCycle` | Cycle A, B, or C (Sunday lectionary) |
| `region` | `str` | Region key used to produce this day |

## Types

All enums and dataclasses are available under `litcal_roman.models`:

```python
from litcal_roman import models

models.Season.LENT
models.Rank.SOLEMNITY
models.LiturgicalColor.WHITE
models.SundayCycle.A
models.ScriptureCycle.YEAR_I
```

Or import directly:

```python
from litcal_roman.models import Season, Rank, LiturgicalColor
```

## Regions

| Key | Description |
|---|---|
| `"universal"` | General Roman Calendar, no transfers |
| `"us"` | USCCB propers, US transfer rules |

## License

BSD-3-Clause
