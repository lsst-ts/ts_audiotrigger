# This file is part of ts_audiotrigger.
#
# Developed for the Vera C. Rubin Observatory Telescope and Site Systems.
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

import asyncio
import logging
import pathlib
import unittest
from typing import TypeAlias

from lsst.ts.audiotrigger import Fan, SerialTemperatureScanner

PathT: TypeAlias = str | pathlib.Path

# Standard timeout in seconds
TIMEOUT = 5


class SerialTempScannerTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.log = logging.getLogger()
        self.data_dir = pathlib.Path(__file__).parent / "data" / "config"

    async def test_read_serial_temp_scanner(self) -> None:
        temp_scanner_task = SerialTemperatureScanner(log=self.log, simulation_mode=True)
        await temp_scanner_task.start_task
        await asyncio.sleep(1)
        assert temp_scanner_task.data is not None
        assert type(temp_scanner_task.data["telemetry"]["sensor_telemetry"][0]) is float
        while temp_scanner_task.pi.read(4) == Fan.OFF:
            await asyncio.sleep(1)
        assert temp_scanner_task.pi.read(4) == Fan.ON
        # The random values of the mock sensor are updated in such a
        # way that this assert can fail.
        # Need to figure out how to test this consistently.
        # assert temp_scanner_task.data["telemetry"]["sensor_telemetry"][0]
        # >= 25
        while temp_scanner_task.pi.read(4) == Fan.ON:
            await asyncio.sleep(1)
        assert temp_scanner_task.pi.read(4) == Fan.OFF
        # The random values of the mock sensor are updated in such a
        # way that this assert can fail.
        # Need to figure out how to test this consistently.
        # assert temp_scanner_task.data["telemetry"]["sensor_telemetry"][0]
        # <= 19
