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

__all__ = ["MockPio", "MockSoundDevice", "MockThermalSensor"]

import random
from collections import OrderedDict

import numpy as np

MAX_PI_GPIOS = 32


class MockPio:
    def __init__(self):
        self.gpios = [0 for _ in range(MAX_PI_GPIOS)]
        self._connected = True

    @property
    def connected(self):
        return self._connected

    def write(self, gpio: int, setting: int | bool):
        if gpio not in range(MAX_PI_GPIOS):
            raise ValueError
        self.gpios[gpio] = setting

    def read(self, gpio: int):
        if gpio not in range(MAX_PI_GPIOS):
            raise ValueError
        return self.gpios[gpio]


class MockSoundDevice:
    def __init__(self):
        self._default_device = (None, None)

        self.microphone_devicelist_dict = {
            "name": "microphone",
            "hostapi": None,
            "max_input_channels": 1,
            "max_output_channels": 0,
            "default_low_input_latency": 0,
            "default_low_output_latency": 0,
            "default_high_input_latency": 0,
            "default_high_output_latency": 0,
            "default_samplerate": 44100,
        }

        self.device_list = [None, None, self.microphone_devicelist_dict]

        # generate audio data
        self.data = [0 for _ in range(44100)]

    def query_devices(self, input: int):

        if input not in range(len(self.device_list)):
            raise ValueError

        return self.device_list[input]

    def check_input_settings(
        self,
        device=None,
        channels=None,
        dtype=None,
        extra_settings=None,
        samplerate=None,
    ):
        # if settings valid, do nothing
        # if not, raise exception
        pass

    def rec(
        self,
        frames=None,
        samplerate=None,
        channels=None,
        dtype=None,
        out=None,
        mapping=None,
        blocking=False,
        **kwargs,
    ):
        returned_data = self.data
        if len(self.data) > frames:
            # data is too long
            returned_data = self.data[:frames]
        elif len(self.data) < frames:
            # data too short, pad with 0s
            returned_data = self.data + [0 for _ in range(frames - len(self.data))]

        generated_data = np.ndarray(
            shape=(2, 2), buffer=np.array(returned_data), dtype=np.float32
        )
        return generated_data

    def fill_with_random_data(self, rangelow, rangehigh, frames):
        self.data = [random.randrange(rangelow, rangehigh) for _ in range(frames)]

    def fill_with_data(self, data):
        self.data = data


class MockThermalSensor:
    def __init__(self):
        self._inWaiting = 0
        self.sensor_dict = OrderedDict(
            {
                "C01": "Ambient",
                "C02": "Laser",
                "C03": "FC",
                "C04": "A",
                "C05": "B",
                "C06": "C",
                "C07": "D",
                "C08": "E",
            }
        )
        self.data_dict = OrderedDict(
            {
                "C01": 0,
                "C02": 0,
                "C03": 0,
                "C04": 0,
                "C05": 0,
                "C06": 0,
                "C07": 0,
                "C08": 0,
            }
        )

    def inWaiting(self):
        return self._inWaiting

    def inject_data(self, data, dict_position=None):
        if dict_position:
            if dict_position in self.data_dict:
                self.data_dict[dict_position] = data
            else:
                raise ValueError
        else:
            for sensor in self.data_dict:
                self.data_dict[sensor] = data

    def read(self, amount: int = 0):
        # These will need to be in some configuration file
        generated_read_string = "something\n"
        for sensor in self.sensor_dict:
            generated_read_string = (
                f"{generated_read_string}{sensor}={self.data_dict[sensor]},"
            )
        generated_read_string = generated_read_string + "\nsomething               "
        generated_read_string = generated_read_string.encode("ISO-8859-1")

        if amount and len(generated_read_string >= amount):
            return generated_read_string[:amount]
        return generated_read_string
