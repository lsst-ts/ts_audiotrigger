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
from types import SimpleNamespace
from typing import TypeAlias
from unittest.mock import ANY, AsyncMock, MagicMock

import yaml
from lsst.ts.audiotrigger import Fan, SerialTemperatureScanner
from lsst.ts.ess.common.data_client import ControllerDataClient

PathT: TypeAlias = str | pathlib.Path

# Standard timeout in seconds
TIMEOUT = 5


class SerialTempScannerTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.log = logging.getLogger()
        self.data_dir = pathlib.Path(__file__).parent / "data" / "config"

    def get_config(self, filename):
        with open(self.data_dir / filename) as f:
            config = yaml.safe_load(f.read())
        return SimpleNamespace(**config)

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
        await temp_scanner_task.close()

    async def test_ess_client(self):
        temp_scanner = SerialTemperatureScanner(log=self.log, simulation_mode=True)
        config = self.get_config("ess.yaml")
        evt_sensor_status = AsyncMock()
        await temp_scanner.start_task
        await asyncio.sleep(1)
        tel_temperature = AsyncMock()
        tel_temperature.DataType = MagicMock(
            return_value=SimpleNamespace(
                temperatureItem=temp_scanner.data["telemetry"]["sensor_telemetry"]
            )
        )
        topics_data = {
            "tel_temperature": tel_temperature,
            "evt_sensorStatus": evt_sensor_status,
        }
        topics = SimpleNamespace(**topics_data)
        async with ControllerDataClient(
            config=config, topics=topics, log=self.log, simulation_mode=1
        ):
            await asyncio.sleep(2)
            tel_temperature.set_write.assert_called_with(
                sensorName=config.devices[0]["name"],
                timestamp=ANY,
                temperatureItem=ANY,
                numChannels=8,
                location=config.devices[0]["location"],
            )
        await temp_scanner.close()
