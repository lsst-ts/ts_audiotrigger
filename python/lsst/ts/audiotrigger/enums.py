__all__ = ["Relay", "Fan"]

import enum


class Relay(enum.IntEnum):
    """Relay values."""

    ON = 1
    """Interlock disengaged."""
    OFF = 0
    """Interlock engaged."""


class Fan(enum.IntEnum):
    """Fan setting values."""

    ON = 1
    """Turn fan on."""
    OFF = 0
    """Turn fan off."""
