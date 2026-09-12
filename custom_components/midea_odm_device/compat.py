"""Compatibility aliases for deprecated Home Assistant constants."""
from homeassistant.const import MAJOR_VERSION, MINOR_VERSION

if (MAJOR_VERSION, MINOR_VERSION) >= (2026, 7):
    from homeassistant.const import (  # pylint: disable=E0611
        UnitOfDensity,
        UnitOfRatio,
    )

    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER = UnitOfDensity.MICROGRAMS_PER_CUBIC_METER
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER = UnitOfDensity.MILLIGRAMS_PER_CUBIC_METER
    CONCENTRATION_PARTS_PER_MILLION = UnitOfRatio.PARTS_PER_MILLION
else:
    from homeassistant.const import (  # type: ignore[no-redef]
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
        CONCENTRATION_PARTS_PER_MILLION,
    )
