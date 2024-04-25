# This file is part of ts_audio_trigger.
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
import asyncio

import numpy as np
from scipy.fftpack import fft


from lsst.ts.interlockmonitor.read_serial_temp_scanner import SerialTemperatureScanner, FAN_OFF, FAN_ON

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.DEBUG
)

PathT: TypeAlias = str | pathlib.Path

# Standard timeout in seconds
TIMEOUT = 5


class SerialTempScannerTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.log = logging.getLogger()
        self.data_dir = pathlib.Path(__file__).parent / "data" / "config"

    async def test_read_serial_temp_scanner(self):
        temp_scanner_task = SerialTemperatureScanner(log=self.log,
                                                     simulation_mode=True)
        
         #inject good data
        temp_scanner_task.serial.inject_data(data=temp_scanner_task.fan_turn_off_temp, dict_position="C01")

        #update data
        await temp_scanner_task.get_data()
        await temp_scanner_task.handle_data(temp_scanner_task.latest_data)

        #confirm gpio status
        assert temp_scanner_task.pi.read(temp_scanner_task.fan_gpio) == FAN_OFF

        #inject bad data
        temp_scanner_task.serial.inject_data(data=temp_scanner_task.fan_turn_on_temp, dict_position="C01")

        #update data
        await temp_scanner_task.get_data()
        await temp_scanner_task.handle_data(temp_scanner_task.latest_data)

        #confirm gpio status
        assert temp_scanner_task.pi.read(temp_scanner_task.fan_gpio) == FAN_ON

