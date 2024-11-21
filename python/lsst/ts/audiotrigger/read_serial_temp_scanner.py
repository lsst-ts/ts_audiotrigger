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

__all__ = ["SerialTemperatureScanner"]

import asyncio
import functools
import logging
from collections import OrderedDict

import pigpio
from lsst.ts import tcpip
from lsst.ts.ess import common, controller

from .enums import Fan
from .mocks import MockPio

MIN = 19
MAX = 25
SENSOR_INDEX = 0


async def callback(data):
    SerialTemperatureScanner.data = data


class SerialTemperatureScanner(tcpip.OneClientServer):
    """This is the class that implements the Serial Temperature Scanner script.

    Class to readout temperature sensors from serial device for laser
    thermal monitoring and extra fan cooling.

    Parameters
    ----------
    logger : `logging.Logger`
        logger object
    port : `int`, optional
        port that the server will be hosted on, default 1883
    host : `str`, optional
        IP the server will be hosted on, default tcpip.DEFAULT_LOCALHOST
    encoding : `str`, optional
        Encoding used for the packets
    terminator: `bytes`, optional
        terminating character used for packets
    sample_wait_time: `int`, optional
        time to wait between getting temperature samples
    serial: `serial` or `None`, optional
        serial object that the temperature scanner device is connected
    temperature_windows: `int`, optional
        Amount of temperature windows to average for rolling avg window

    Attributes
    ----------
    log : logging.Logger
        Log instance.
    simulation_mode : bool
        Is the temperature scanner in simulation mode.
    serial : serial.Serial
        The serial port instance.
    sensor_dict : dict
        The sensor information.
    sample_wait_time : int
        The wait time between getting samples.
    fan_sensor : str
        The fan sensor.
    fan_gpio : None
        The fan gpio id.
    fan_turn_on_temp : int
        The temperature to turn on the fan.
    fan_turn_off_temp : int
        The temperature to turn off the fan.
    latest_data : dict
        The latest sensor data.
    rolling_temperature : int
        The last read temperature.
    pi : pi.Pi
        The pi gpio daemon client.
    configured : bool
        Is the server configured.
    first_run : bool
        Is the first run.
    encoding : str
        The string encoding type.
    port : int
        The port.
    host : str
        The host.
    loop : asyncio.Loop
        The current running async loop.
    """

    data = None

    def __init__(
        self,
        log: logging.Logger | None = None,
        port: int | None = 18830,
        host: str | None = tcpip.DEFAULT_LOCALHOST,
        encoding: str = tcpip.DEFAULT_ENCODING,
        terminator: bytes = tcpip.DEFAULT_TERMINATOR,
        sample_wait_time: int = 1,
        temperature_windows: int = 8,
        simulation_mode=False,
    ):
        self.log = log
        self.simulation_mode = simulation_mode

        super().__init__(
            log=self.log,
            port=port,
            host=host,
            connect_callback=None,
            monitor_connection_interval=0,
            name="",
            encoding=encoding,
            terminator=terminator,
        )
        self.sensor_dict = {}
        self.sample_wait_time = sample_wait_time

        # Fan sensor
        self.fan_sensor = ""
        self.fan_gpio = None
        self.fan_turn_on_temp = 0
        self.fan_turn_off_temp = 0

        self.latest_data = {sensor_name: 0 for sensor_name in self.sensor_dict}
        self.rolling_temperature = [0 for _ in range(temperature_windows)]

        if self.simulation_mode:
            self.pi = MockPio()
        else:
            self.pi = pigpio.pi()

        self.configured = False
        self.first_run = True
        self.encoding = encoding
        self.port = port
        self.host = host
        self.loop = asyncio.get_running_loop()
        self.error_validator = None
        self.config()

    def config(self):
        """Configure the temperature scanner."""
        # TODO: DM-47286 Get config from runner service.
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
        )  # These will need to be in some configuration file

        # Define serial connection
        if self.simulation_mode:
            self.serial = common.device.MockDevice(
                name="Mock Fan Control sensors",
                device_id="/dev/ttyUSB0",
                sensor=common.sensor.TemperatureSensor(log=self.log, num_channels=8),
                callback_func=callback,
                log=self.log,
            )
        else:
            self.serial = controller.device.RpiSerialHat(
                name="Fan Control sensors",
                device_id="/dev/ttyUSB0",
                sensor=common.sensor.TemperatureSensor(log=self.log, num_channels=8),
                baud_rate=19200,
                callback_func=callback,
                log=self.log,
            )

        # fan sensor
        self.fan_sensor = "Ambient"
        self.fan_gpio = 4
        self.fan_turn_on_temp = 25
        hysteresis = 2
        self.fan_turn_off_temp = self.fan_turn_on_temp - hysteresis
        self.configured = True

    async def start(self, **kwargs):
        """Start reading the temperature channels."""
        self.task = asyncio.ensure_future(self.serial_temperature_task())
        await self.serial.open()
        await super().start(**kwargs)

    async def close(self):
        self.task.cancel()
        await self.serial.close()
        await super().close()

    async def write_if_connected(self, string_to_write):
        """Write message if connected."""
        if self.simulation_mode:
            return
        if self.connected:
            await self.write_json(string_to_write)

    async def set_fan(self, setting):
        """Set the fan on/off.

        Parameters
        ----------
        setting : `Fan`
            Turn the fan on or off.
        """
        if not self.pi.connected:
            raise ValueError("Not configured properly before actuating fan")
        match setting:
            case Fan.ON:
                value = "on"
            case Fan.OFF:
                value = "off"
            case _:
                raise Exception("Value is not valid.")
        msg = {"id": "set_fan", "value": value}
        if not self.simulation_mode:
            async with tcpip.Client(
                host=tcpip.LOCAL_HOST, port=8080, log=self.log
            ) as client:
                await client.write_json(msg)
        await self.loop.run_in_executor(
            None, functools.partial(self.pi.write, self.fan_gpio, setting)
        )

    async def set_fan_on(self):
        """Turn the fan on."""
        await self.set_fan(Fan.ON)

    async def set_fan_off(self):
        """Turn the fan off."""
        await self.set_fan(Fan.OFF)

    async def check_temp(self, data):
        ambient = data["telemetry"]["sensor_telemetry"][SENSOR_INDEX]
        if ambient <= self.fan_turn_off_temp:
            await self.set_fan_off()
        if ambient >= self.fan_turn_on_temp:
            await self.set_fan_on()

    async def publish_data(self, data):
        await self.write_json(data)

    async def serial_temperature_task(self):
        """Get incoming data and publish through the server."""
        # Read sensors
        # wait for sample_wait_time between readings

        while True:
            try:
                self.log.debug(self.data)
                if self.data is not None:
                    self.log.debug(self.data)
                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self.check_temp(self.data))
                        tg.create_task(self.publish_data(self.data))
            except Exception as e:
                self.log.warning(f"Main task excepted {e}")
            self.log.info(f"Waiting {self.sample_wait_time} seconds")
            await asyncio.sleep(self.sample_wait_time)
