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

import logging
import pathlib
import unittest
from typing import TypeAlias

import numpy as np
from lsst.ts.audiotrigger import LaserAlignmentListener, Relay

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s", level=logging.DEBUG
)

PathT: TypeAlias = str | pathlib.Path

# Standard timeout in seconds
TIMEOUT = 5


class LaserAlignmentTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.log = logging.getLogger()
        self.data_dir = pathlib.Path(__file__).parent / "data" / "config"

    @unittest.skip("Not sure how to mock yet.")
    async def test_laser_interlock_trigger(self) -> None:
        laser_task = LaserAlignmentListener(
            log=self.log,
            simulation_mode=True,
        )

        # inject good values
        # good_data = [0 for _ in range(44100)]
        # laser_task.mock_sd.fill_with_data(data=good_data)
        num_samples = 44100
        frequency = 1000
        sampling_rate = 44100.0
        amplitude = 40
        sine_wave = [
            amplitude * np.sin(2 * np.pi * x * frequency / sampling_rate)
            for x in range(5 * num_samples)
        ]
        laser_task.mock_sd.fill_with_data(sine_wave)

        for _ in range(laser_task.count_threshold + 1):
            data = await laser_task.record_data(
                laser_task.sample_record_dur, laser_task.fs
            )
            self.log.debug(f"data is: {data}")
            result = await laser_task.analyze_data(data, laser_task.fs)
            self.log.debug(f"result is: {result}")
            await laser_task.handle_interlock(result)

        # test relay status
        relay_status = await laser_task.get_relay_status()
        assert relay_status == Relay.ON

        # inject bad values
        num_samples = 44100
        frequency = 1000
        sampling_rate = 44100.0
        sine_wave = [
            0.5 * np.sin(2 * np.pi * x * frequency / sampling_rate)
            for x in range(5 * num_samples)
        ]
        laser_task.mock_sd.fill_with_data(sine_wave)

        for _ in range(laser_task.count_threshold + 1):
            data = await laser_task.record_data(
                laser_task.sample_record_dur, laser_task.fs
            )
            result = await laser_task.analyze_data(data, laser_task.fs)
            self.log.debug(f"{result=}")
            await laser_task.handle_interlock(result)

        # test relay status
        relay_status = await laser_task.get_relay_status()
        assert relay_status == Relay.OFF
