# This file is part of ts_audio_trigger.
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


__all__ = ["LaserAlignmentListener", "execute_laser_alignment_listener"]

import asyncio
import functools
import logging

import matplotlib.pyplot as plt
import numpy as np
import pigpio
import sounddevice as sd
from lsst.ts import tcpip
from scipy.fftpack import fft
#from .mock_pigpio import MockPio
#from .mock_sounddevice import MockSoundDevice

RELAY_ON = 1
RELAY_OFF = 0

#TODO put back in mock stuff for unit testing


class LaserAlignmentListener(tcpip.OneClientServer):
    """This is the class that implements the laser alignment script.

    Parameters
    ----------
    log : `logging.log`
        log object
    port : `int`, optional
        port that the server will be hosted on, default 1883
    host : `str`, optional
        IP the server will be hosted on, default tcpip.DEFAULT_LOCALHOST
    encoding : `str`, optional
        Encoding used for the packets
    terminator: `bytes`, optional
        terminating character used for packets
    sample_record_dur: `float`, optional
        sample recording duration
    input: `int`, optional
        index of sd device input
    output: `int`, optional
        index of sd device output
    fs: `int`, optional
        sample frequency
    simulation_mode: `bool`, optional
        if class is being simulated
    """

    def __init__(
        self,
        log: logging.Logger | None = None,
        port: int | None = 1883,
        host: str | None = tcpip.DEFAULT_LOCALHOST,
        encoding: str = tcpip.DEFAULT_ENCODING,
        terminator: bytes = tcpip.DEFAULT_TERMINATOR,
        sample_record_dur: float = 0.1,
        input: int = 0,
        output: int = 4,
        fs: int | None = None,
        simulation_mode: bool = False,
    ):
        self.log = log

        self.simulation_mode = simulation_mode
        if self.simulation_mode == False:
            super().__init__(
                log=self.log,
                host=host,
                port=port,
                connect_callback=None,
                monitor_connection_interval=0,
                name="",
                encoding=encoding,
                terminator=terminator,
            )

        self.relay_gpio = None
        self.configured = False

        self.input = input
        self.output = output
        self.sample_record_dur = sample_record_dur
        #self.mock_sd = MockSoundDevice()

        if self.simulation_mode == True:
            if fs is None:
                pass
            else:
                self.fs = fs
        else:
            sd.default.device = (input, output)
            if fs is None:
                self.fs = sd.query_devices(input)["default_samplerate"]
            else:
                self.fs = fs

        self.relay_gpio = 7
        self.configured = True
        if self.simulation_mode == True:
            pass
        else:
            self.pi = pigpio.pi()

        # Declare how many iterations have to be
        # above the threshold to shut off the laser
        self.count_threshold = 7  # 10
        self.count = 0

    async def amain(self):
        """Script amain"""
        await self.open_laser_interrupt()
        await self.laser_alignment_task(self.sample_record_dur, self.fs)

    async def write_if_connected(self, str):
        if self.connected:
            self.write_str(str)

    async def record_data(self, duration, fs):
        """Records sample data from sd device"""
        self.log.debug("Check input settings")

        loop = asyncio.get_running_loop()

        if self.simulation_mode == True:
            pass
        else:
            await loop.run_in_executor(
                None,
                functools.partial(
                    sd.check_input_settings, device=self.input, samplerate=fs, channels=1
                ),
            )
        self.log.debug(f"Starting to record for {duration} seconds")

        if self.simulation_mode == True:
            data = 0 
        else:
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
        return data

    async def analyze_data(self, data, fs):
        try:
            """analyzes all sound data and determines if there is a problem"""
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
            threshold = 10

            self.log.debug(
                f"Median of frequency vals are {(np.median(xf[(xf > 995) * (xf < 1005)])):0.2f}"
            )
            psd_at_1kHz = np.max(psd[(xf > 995) * (xf < 1005)])
            bkg = np.median(psd[(xf > 950) * (xf < 1050)])

            self.log.debug(
                f"PSD max value in frequency window of 995-1050 Hz is {(psd_at_1kHz / bkg):0.2f} sigma"
            )

            self.log.debug(f"Median value over range from 900-1000 Hz is {bkg:0.2E}")
            condition = (psd_at_1kHz) > threshold * bkg
            if condition:
                return True
            else:
                return False
        except Exception as e:
            self.log.error(f"handle_data excepted: {e}")
            return False

    def plot_data(self, data, fs, xf, yf, psd):
        length = data.shape[0] / fs

        plt.clf()
        time = np.linspace(0.0, length, data.shape[0])
        plt.subplot(1, 3, 1)
        plt.plot(time, data[:, 0], label="Left channel")
        plt.plot(time, data[:, 1], label="Right channel")
        plt.xlim(0, 1e-2)
        plt.xlabel("Time [s]")
        plt.ylabel("Amplitude")

        plt.subplot(1, 3, 2)
        plt.plot(xf, psd, ".-")
        plt.xlim(0, 1300)
        plt.xlabel("Frequency (Hz)")
        plt.ylabel("PSD [units TBD]")
        plt.draw()
        plt.pause(0.001)

        plt.subplot(1, 3, 3)
        plt.plot(xf, psd, ".-")
        plt.xlim(900, 1100)
        plt.xlabel("Frequency (Hz)")
        plt.ylabel("PSD [units TBD]")
        plt.draw()
        plt.pause(0.001)

    async def set_relay(self, setting: int):
        if not self.configured and not self.pi.connected:
            await self.write_if_connected(
                "LI: Error: Not configured properly before actuating relay"
            )
            raise ValueError("Not configured properly before actuating relay")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, functools.partial(self.pi.write, self.relay_gpio, setting)
        )

    async def set_relay_on(self):
        await self.set_relay(RELAY_ON)

    async def set_relay_off(self):
        await self.set_relay(RELAY_OFF)

    async def open_laser_interrupt(self):
        await self.set_relay_off()
        self.log.info("Laser interrupt opened")
        await self.write_if_connected("LI: Opened")

    async def close_laser_interrupt(self):
        await self.set_relay_on()
        self.log.info("Laser Interrupt Activated, laser propagation disabled")
        await self.write_if_connected("LI: Closed")

    async def restart(self):
        self.log.info("Reset button pushed")
        await self.write_if_connected("LI: Reset button pushed")
        await self.open_laser_interrupt()

    async def get_relay_status(self) -> bool:
        # bits are flipped since self.relay.value returns a 0
        # when it's able to propagate
        loop = asyncio.get_running_loop()
        pin_value = await loop.run_in_executor(
            None, functools.partial(self.pi.read, self.relay_gpio)
        )
        return not pin_value
    
    async def handle_interlock(self, data_result):
        if data_result and self.count > self.count_threshold - 1:
            self.log.warning(
                "Detected misalignment in audible safety circuit"
            )
            await self.close_laser_interrupt()
            self.log.warning("Interlock sleeping for 10 seconds...")
            await asyncio.sleep(10)
            self.log.warning("Interlock re-opening now...")
            await self.open_laser_interrupt()
            self.count = 0
        elif data_result:
            self.log.info(
                f"Experienced value above threshold {self.count+1} times"
            )
            self.count += 1
        else:
            self.count = 0

    async def laser_alignment_task(
        self, time: float | None = None, fs: float | None = None
    ):
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


async def start_laser_task(log):
    laser_task = LaserAlignmentListener(log=log)
    await laser_task.amain()
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, laser_task.amain)

def execute_laser_alignment_listener():
    """This a script for the raspberry pi running alongside the TunableLaser
    CSC This script's purpose is to listen for 1kHz laser misalignment and
    activate an interlock
    """
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.DEBUG,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    log = logging.getLogger(__name__)
    log.propagate = True
    asyncio.run(start_laser_task(log))


    #laser_task = LaserAlignmentListener(log=log)
    #loop = asyncio.new_event_loop()
    #asyncio.set_event_loop(loop)
    #loop.run_until_complete(laser_task.amain())
    #asyncio.run(laser_task.amain(index=None))

if __name__ == "__main__":
    execute_laser_alignment_listener()
