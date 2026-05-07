# Litcal-roman

Roman Catholic liturgical calendar (Ordinary Form) computation in pure Python.

Given a date and a calendar configuration, `litcal-roman` returns the fully resolved liturgical day: the winning celebration after precedence resolution, any displaced celebrations, the liturgical season and week, vestment color, psalter week, and lectionary cycles.

Precedence rules follow the [General Norms for the Liturgical Year and the Calendar](https://www.catholicculture.org/culture/library/view.cfm?id=10842)) (GNLYC), with transfer rules applied per region. Currently only support US region.

> [!NOTE]
> This entire project was vibe-coded over a weekend. I'm *pretty* confident that it's accurate because Claude tested it against four years of data from [Romcal](https://romcal.net/), the software Kenneth G. Bath first wrote in 1993. Even so, it is with great trepidation that I release a calendar (combining the complexities of the civil and liturgical calendar, no less) library into the world. I welcome issues and PRs and have every intention to deliver a quality library, but as the license says, this software is provided "as is."

## Installation

```
# pip

pip install litcal-roman

# uv

uv add litcal-roman
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

When a [temporale](https://en.wikipedia.org/wiki/Temporale) celebration is displaced by a higher-ranked [sanctorale](https://en.wikipedia.org/wiki/Sanctorale) day, it appears in `day.displaced`:

```python
day = get_liturgical_day(date(2026, 6, 22), config)  # Saint Paulinus of Nola, Bishop / Saints John Fisher, Bishop, and Thomas More, Martyrs / 12th Sunday OT
print(day.celebration.name)    # "Saint Paulinus of Nola, Bishop"
print(day.displaced[0].name)   # "Saints John Fisher, Bishop, and Thomas More, Martyrs"
print(day.displaced[1].name)   # "Twelfth Sunday in Ordinary Time"
```

## CalendarConfig

```python
CalendarConfig.universal()   # No transfers, no national propers
CalendarConfig.us()          # USCCB propers + standard US transfers
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

## Changelog

[Changelog](https://github.com/josterpi/litcal-roman/blob/main/CHANGELOG.md)

## License

BSD-3-Clause
