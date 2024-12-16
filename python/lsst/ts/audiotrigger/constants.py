# This file is part of ts_audiotrigger.
#
# Developed for the Vera Rubin Observatory Telescope and Site Software.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

__all__ = [
    "MAX_PI_GPIOS",
    "SLEEP",
    "THRESHOLD",
    "TEMPERATURE_MIN",
    "TEMPERATURE_MAX",
    "SENSOR_INDEX",
]

MAX_PI_GPIOS = 32
"""Maximum number of pi GPIO pins."""
SLEEP = 1
"""Default sleep timer."""
THRESHOLD = 10
"""Threshold over which misalignment of laser beam occurs."""
TEMPERATURE_MIN = 19
"""Minimum temperature for the ambient sensor for the fan to stop."""
TEMPERATURE_MAX = 25
"""Maximum temperature for the ambient sensor for the fan to start."""
SENSOR_INDEX = 0
"""The index for ambient temperature sensor."""
BAUDRATE = 19200
"""Serial port baud rate."""
FAN_GPIO_PIN = 4
"""Fan control GPIO pin."""
TURN_ON_TEMP = 24
"""Turn on the fan at or above this temperature. (Deg_C)"""
TURN_OFF_TEMP = 22
"""Turn off the fan at or below this temperature. (Deg_C)"""
SERIAL_PORT = "/dev/ttyUSB_lower_right"
"""Serial port file descriptor."""
