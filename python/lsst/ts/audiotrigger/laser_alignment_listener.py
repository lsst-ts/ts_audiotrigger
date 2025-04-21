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


__all__ = ["LaserAlignmentListener"]

import asyncio
import functools
import json
import logging
import pathlib
from importlib import resources as impresources

import jsonschema
import numpy as np
import pigpio
import sounddevice as sd
from lsst.ts import tcpip, utils
from scipy.fftpack import fft

from . import schemas
from .constants import THRESHOLD
from .enums import Relay
from .mocks import MockPio, MockSoundDevice


class LaserAlignmentListener:
    """Implement the laser alignment script.

    Parameters
    ----------
    log : `logging.log`
        Log object
    port : `int`, optional
        Port that the server will be hosted on, default 1883
    host : `str`, optional
        IP the server will be hosted on, default tcpip.DEFAULT_LOCALHOST
    encoding : `str`, optional
        Encoding used for the packets
    terminator : `bytes`, optional
        Terminating character used for packets
    sample_record_dur : `float`, optional
        Sample recording duration
    input : `int`, optional
        Index of sound device input
    output : `int`, optional
        Index of sound device output
    fs : `int`, optional
        Sample frequency
    simulation_mode : `bool`, optional
        If class is being simulated

    Attributes
    ----------
    log : `logging.Logger`
        Log instance.
    simulation_mode : `bool`
        Is in simulation mode.
    relay_gpio : `int`
        The gpio pin instance.
    configured : `bool`
        Is the server configured.
    input : `int`
        The audio input id for recording.
    output : `int`
        The audio output id for playback.
    sample_record_dur : `int`
        The amount of time to record the microphone.
    mock_sd : MockSd`
        The mock sounddevice, only initialized in simulation mode.
    fs : `int`
        The sample rate.
    pi : `pi.Pi`
        The pi gpio daemon instance.
    count_threshold : `int`
        The threshold to trigger the interlock.
    count : `int`
        The amount of times the threshold has been reached.
    """

    def __init__(
        self,
        log: logging.Logger | None = None,
        port: int | None = 18840,
        host: str | None = tcpip.DEFAULT_LOCALHOST,
        encoding: str = tcpip.DEFAULT_ENCODING,
        terminator: bytes = tcpip.DEFAULT_TERMINATOR,
        sample_record_dur: float = 0.1,
        input: int = 0,
        output: int = 4,
        fs: int | None = None,
        simulation_mode: bool = False,
        disable_microphone: bool = False,
    ):
        self.log = log
        self.disable_microphone = disable_microphone
        self.simulation_mode = simulation_mode
        self.input = input
        self.output = output
        self.sample_record_dur = sample_record_dur
        if self.simulation_mode:
            self.mock_sd = MockSoundDevice()
            self.fs = None
            self.pi = MockPio()
        else:
            if not self.disable_microphone:
                sd.default.device = (input, output)
                if fs is None:
                    self.fs = sd.query_devices(input)["default_samplerate"]
                else:
                    self.fs = fs
            self.pi = pigpio.pi()

        self.relay_gpio = 7
        self.configured = True

        # Declare how many iterations have to be
        # above the threshold to shut off the laser
        self.count_threshold = 7
        self.count = 0
        self.error_validator = jsonschema.Draft7Validator(
            json.load(pathlib.Path(impresources.files(schemas) / "error.json").open())
        )
        self.set_interrupt_status_validator = jsonschema.Draft7Validator(
            json.load(
                pathlib.Path(
                    impresources.files(schemas) / "set_interrupt_state.json"
                ).open()
            )
        )
        self.interrupt_status_validator = jsonschema.Draft7Validator(
            json.load(
                pathlib.Path(
                    impresources.files(schemas) / "interrupt_status.json"
                ).open()
            )
        )
        self.start_laser_task = utils.make_done_future()
        self.log_server = tcpip.OneClientServer(
            host=tcpip.LOCAL_HOST, port=18840, log=self.log
        )

    # TODO: DM-47286 Add configure method

    async def start(self, **kwargs):
        """Start the laser alignment analysis task."""
        await self.log_server.start_task
        await self.open_laser_interrupt()
        if not self.start_laser_task.done():
            self.start_laser_task.cancel()
        if not self.disable_microphone:
            self.start_laser_task = asyncio.create_task(
                self.laser_alignment_task(self.sample_record_dur, self.fs)
            )

    async def stop(self):
        """Stop the laser alignment analysis task."""
        notyet_cancelled = self.start_laser_task.cancel()
        if notyet_cancelled:
            await self.start_laser_task
        await self.close_laser_interrupt()

    async def write_if_connected(self, str):
        """Write if connected."""
        if self.log_server.connected:
            await self.log_server.write_json(str)

    async def record_data(self, duration, fs):
        """Records sample data from microphone.

        Parameters
        ----------
        duration : `float`
            The amount of time to record.
        fs : `int`
            The hertz of the sample.
        """
        self.log.debug("Check input settings")

        loop = asyncio.get_running_loop()

        if self.simulation_mode:
            data = np.zeros(shape=(150, 2))
        else:
            await loop.run_in_executor(
                None,
                functools.partial(
                    sd.check_input_settings,
                    device=self.input,
                    samplerate=fs,
                    channels=1,
                ),
            )
            data = await loop.run_in_executor(
                None,
                functools.partial(
                    sd.rec,
                    frames=int(duration * fs),
                    samplerate=fs,
                    channels=1,
                    blocking=True,
                ),
            )
        self.log.debug(f"Starting to record for {duration} seconds")
        return data

    async def analyze_data(self, data, fs):
        """Analyze the data from the sample.

        Parameters
        ----------
        data : `np.ndarray`
            The numpy array data from the recording.
        fs : `int`
            Number of samples.

        Returns
        -------
        `bool`
            Hit the threshold.
        """
        try:
            # average the tracks
            a = data.T[0]
            self.log.debug(f"a: {a}")
            # Make the array an even size
            if (len(a) % 2) != 0:
                self.log.debug(f"Length of a is {len(a)}, removing last value")
                a = a[0:-1]
                self.log.debug(f"Length of a is now {len(a)}")

            # sample points
            N = len(a)
            self.log.debug(f"N: {N}")
            # sample spacing
            T = 1.0 / fs
            self.log.debug(f"T: {T}")

            yf0 = fft(a)
            self.log.debug(f"yf0: {yf0}")
            # but only need half the array
            yf = yf0[: N // 2]
            self.log.debug(f"yf: {yf}")
            xf = np.linspace(0.0, 1.0 / (2.0 * T), N // 2)
            self.log.debug(f"xf: {xf}")

            psd = abs((2.0 / N) * yf) ** 2.0

            # check if signal is detected
            # threshold is in sigma over the range of 950-1050 Hz

            self.log.debug(
                f"Median of frequency vals are {(np.median(xf[(xf > 995) * (xf < 1005)])):0.2f}"
            )
            psd_at_1kHz = np.max(psd[(xf > 995) * (xf < 1005)])
            bkg = np.median(psd[(xf > 950) * (xf < 1050)])

            self.log.debug(
                f"PSD max value in frequency window of 995-1050 Hz is {(psd_at_1kHz / bkg):0.2f} sigma"
            )

            self.log.debug(f"Median value over range from 900-1000 Hz is {bkg:0.2E}")
            condition = (psd_at_1kHz) > THRESHOLD * bkg
            return condition
        except Exception as e:
            self.log.error(f"handle_data excepted: {e}")
            return False

    async def set_relay(self, setting: int):
        """Set the relay.

        Parameters
        ----------
        setting : `int`
            Set the relay on or off.
        """
        if not self.pi.connected:
            msg = {
                "id": "error",
                "code": 1,
                "message": "Not configured properly before actuating relay.",
            }
            try:
                self.error_validator.validate(msg)
            except Exception:
                raise
            await self.write_if_connected(msg)
            raise ValueError("Not configured properly before actuating relay")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, functools.partial(self.pi.write, self.relay_gpio, setting)
        )

    async def set_relay_on(self):
        """Set the relay on."""
        await self.set_relay(Relay.ON)

    async def set_relay_off(self):
        """Set the relay off."""
        await self.set_relay(Relay.OFF)

    async def open_laser_interrupt(self):
        """Open the laser interrupt/interlock."""
        await self.set_relay_off()
        self.log.info("Laser interrupt opened")
        msg = {"id": "set_interrupt_state", "value": "open"}
        try:
            self.set_interrupt_status_validator.validate(msg)
        except Exception:
            raise Exception("Msg not valid.")
        await self.write_if_connected(msg)

    async def close_laser_interrupt(self):
        """Close the laser interrupt/interlock."""
        await self.set_relay_on()
        self.log.info("Laser Interrupt Activated, laser propagation disabled")
        msg = {"id": "set_interrupt_state", "value": "close"}
        try:
            self.set_interrupt_status_validator.validate(msg)
        except Exception:
            raise Exception("Msg not valid.")
        await self.write_if_connected(msg)

    async def restart(self):
        """Restart the laser interrupt."""
        self.log.info("Reset button pushed")
        msg = {"id": "set_interrupt_state", "value": "reset"}
        try:
            self.set_interrupt_status_validator(msg)
        except Exception:
            raise Exception("Msg not valid.")
        await self.write_if_connected(msg)
        await self.open_laser_interrupt()

    async def get_relay_status(self) -> bool:
        """Get the relay status."""
        # bits are flipped since self.relay.value returns a 0
        # when it's able to propagate
        loop = asyncio.get_running_loop()
        pin_value = await loop.run_in_executor(
            None, functools.partial(self.pi.read, self.relay_gpio)
        )
        match pin_value:
            case 1:
                value = "closed"
            case 0:
                value = "opened"
            case _:
                pass
        msg = {"id": "interrupt_status", "value": value}
        try:
            self.interrupt_status_validator.validate(msg)
        except Exception:
            raise Exception("msg not valid.")
        await self.write_if_connected(msg)
        return not pin_value

    async def handle_interlock(self, data_result):
        """Handle the interlock.

        Parameters
        ----------
        data_result : `bool`
            Threshold hit.
        """
        if data_result and self.count > self.count_threshold - 1:
            self.log.warning("Detected misalignment in audible safety circuit")
            await self.close_laser_interrupt()
            self.log.warning("Interlock sleeping for 10 seconds...")
            await asyncio.sleep(10)
            self.log.warning("Interlock re-opening now...")
            await self.open_laser_interrupt()
            self.count = 0
        elif data_result:
            self.log.info(f"Experienced value above threshold {self.count+1} times")
            self.count += 1
        else:
            self.count = 0

    async def laser_alignment_task(
        self, time: float | None = None, fs: float | None = None
    ):
        """Record the data from the microphone and analyze it.

        Parameters
        ----------
        time : `float`
            Duration of sample.
        fs : `float`
            The number of samples per second.
        """
        if time is None:
            time = self.sample_record_dur
        if fs is None:
            fs = self.fs
        try:
            self.log.info("Starting monitoring task")

            # Loop forever
            while True:
                data = await self.record_data(time, fs)
                result = await self.analyze_data(data, fs)
                await self.handle_interlock(result)

        except Exception as e:
            await self.write_if_connected(f"LI: Exception: Main task excepted: {e}")
            self.log.exception(f"Main task excepted: {e}")
