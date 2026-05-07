# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-04

Initial alpha release.

### Added
- Temporale: moveable feast computation (Advent, Christmas, Lent, Easter, Ordinary Time)
- Temporale: liturgical color and rank rules
- Sanctorale: YAML-backed fixed-date calendar loader with `LORD_FEAST` rank support
- Calendar: precedence resolver and transfer rules for feast day conflicts
- US regional calendar (USCCB propers)
- romcal fixture cross-validation test suite (290 tests)
- Public API (`get_liturgical_day`, `CalendarConfig`) via `__init__.py`
- Makefile, ruff, and mypy configuration
- BSD license
- README
- CHANGELOG
- `__version__` attribute to public API
- Repository URL in project metadata

[0.1.0]: https://github.com/josterpi/litcal-roman/releases/tag/v0.1.0
