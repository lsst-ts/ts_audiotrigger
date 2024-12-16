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

__all__ = ["SerialTemperatureScanner", "run_serial_temperature_scanner"]

import argparse
import asyncio
import functools
import logging
import logging.config

import pigpio
from lsst.ts import tcpip, utils
from lsst.ts.ess import common, controller

from .constants import (
    BAUDRATE,
    FAN_GPIO_PIN,
    SENSOR_INDEX,
    SERIAL_PORT,
    TURN_OFF_TEMP,
    TURN_ON_TEMP,
)
from .enums import Fan
from .mocks import MockPio


async def callback(data):
    SerialTemperatureScanner.data = data


def run_serial_temperature_scanner():
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulate", action="store_true")
    args = parser.parse_args()
    asyncio.run(amain(args))


async def amain(args):
    sts = SerialTemperatureScanner(
        log=logging.getLogger(__name__), simulation_mode=args.simulate
    )
    await sts.start()
    await sts.start_task
    while True:
        await asyncio.sleep(1)


class FanControlServer(tcpip.OneClientServer):
    def __init__(self, port=18830):
        super().__init__(host="0.0.0.0", port=port, log=logging.getLogger(__name__))


class EssServer(tcpip.OneClientServer):
    def __init__(self, port=15000):
        super().__init__(host="0.0.0.0", port=port, log=logging.getLogger(__name__))


class SerialTemperatureScanner:
    """This is the class that implements the Serial Temperature Scanner script.

    Class to readout temperature sensors from serial device for laser
    thermal monitoring and extra fan cooling.

    Parameters
    ----------
    log : `logging.Logger`
        logger object
    simulation_mode: `boolean`
        Should the device startup in simulation mode.


    Attributes
    ----------
    log : logging.Logger
        Log instance.
    simulation_mode : bool
        Is the temperature scanner in simulation mode.
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
    pi : pi.Pi | MockPio
        The pi gpio daemon client.
    configured : bool
        Is the server configured.
    first_run : bool
        Is the first run.
    loop : asyncio.Loop
        The current running async loop.
    error_validator : `None`
        The jsonschema validator for error messages.
    fan_control_server : `FanControlServer`
        The service that handles turning the fan on/off.
    ess_server : `EssServer`
        The service that handles sending data to the ESS client.
    start_task : `asyncio.Future`
        Promise to see that start method is executed.
    temperature_task : `asyncio.Future`
        Promise to see that serial_temperature_task is executed.
    serial : `MockDevice` | `RpiSerialHat` | None
        The serial device to read the sensor data.
    """

    def __init__(
        self,
        log: logging.Logger | None = None,
        simulation_mode=False,
    ):
        self.log = log
        self.simulation_mode = bool(simulation_mode)
        self.sample_wait_time = 1

        # Fan sensor
        self.fan_gpio = FAN_GPIO_PIN
        self.fan_turn_on_temp = TURN_ON_TEMP
        self.fan_turn_off_temp = TURN_OFF_TEMP
        if self.simulation_mode:
            self.pi = MockPio()
        else:
            try:
                self.pi = pigpio.pi()
            except Exception:
                self.log.exception("Failed to connect to pigpiod.")
                raise
        self.loop = asyncio.get_running_loop()
        self.error_validator = None
        self.fan_control_server = FanControlServer()
        self.ess_server = EssServer()
        self.start_task = utils.make_done_future()
        self.temperature_task = utils.make_done_future()
        self._data = None
        self.serial = None
        self.log.info("SerialTemperatureScanner configured.")

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, new_data):
        self._data = new_data

    def construct_serial(self):
        """Construct the device class used to communicate with serial port."""
        device_id = SERIAL_PORT
        sensor = common.sensor.TemperatureSensor(log=self.log, num_channels=8)
        callback_func = callback
        log = self.log
        baud_rate = BAUDRATE
        kwargs = {
            "name": "Fan Control Sensors",
            "device_id": device_id,
            "sensor": sensor,
            "callback_func": callback_func,
            "log": log,
            "baud_rate": baud_rate,
        }
        if self.simulation_mode:
            name = "Mock Fan Control sensors"
            device_class = common.device.MockDevice
            kwargs["name"] = name
            kwargs.pop("baud_rate")
        else:
            device_class = controller.device.RpiSerialHat
        try:
            self.serial = device_class(**kwargs)
        except Exception:
            self.log.exception("Failed to create serial device.")
            raise

    async def start(self):
        """Start reading the temperature channels."""
        self.construct_serial()
        await self.serial.open()
        await asyncio.gather(
            self.fan_control_server.start_task,
            self.ess_server.start_task,
        )
        self.temperature_task = asyncio.ensure_future(self.serial_temperature_task())

    async def close(self):
        """Close running tasks."""
        self.temperature_task.cancel()
        await asyncio.gather(
            self.serial.close(),
            self.fan_control_server.close(),
            self.ess_server.close(),
        )

    async def set_fan(self, setting):
        """Set the fan on/off.

        Parameters
        ----------
        setting : `Fan`
            Turn the fan on or off.
        """
        if not self.pi.connected:
            raise RuntimeError("Pigpiod not connected.")
        match setting:
            case Fan.ON:
                value = "on"
            case Fan.OFF:
                value = "off"
            case _:
                raise RuntimeError("Value is not valid.")
        msg = {"id": "set_fan", "value": value}
        reading = await self.loop.run_in_executor(
            None, functools.partial(self.pi.read, self.fan_gpio)
        )
        if reading != setting:
            await self.loop.run_in_executor(
                None, functools.partial(self.pi.write, self.fan_gpio, setting)
            )
            if self.fan_control_server.connected:
                await self.fan_control_server.write_json(msg)

    async def set_fan_on(self):
        """Turn the fan on."""
        await self.set_fan(Fan.ON)

    async def set_fan_off(self):
        """Turn the fan off."""
        await self.set_fan(Fan.OFF)

    async def check_temp(self, data):
        """Check the ambient sensor temperature and turn the fan on/off.

        Parameters
        ----------
        data : `dict`
            The data received from the ESS device.
        """
        ambient = data["telemetry"]["sensor_telemetry"][SENSOR_INDEX]
        if ambient <= self.fan_turn_off_temp:
            await self.set_fan_off()
        if ambient >= self.fan_turn_on_temp:
            await self.set_fan_on()

    async def publish_data(self, data):
        """Publish the data through the ESS server.

        Parameters
        ----------
        data : `dict`
            The data recieved from the ESS device.
        """
        if self.ess_server.connected:
            array = data["telemetry"]["sensor_telemetry"]
            line = ""
            for idx, value in enumerate(array):
                line += f"C0{idx}={value},"
            line = line[:-1]
            await self.ess_server.write_str(line)

    async def serial_temperature_task(self):
        """Get incoming data and publish through the server."""
        # Read sensors
        # wait for sample_wait_time between readings
        self.log.info("Starting Serial Temperature loop.")
        while True:
            try:
                if self.data is not None:
                    self.log.debug(self.data)
                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self.check_temp(self.data))
                        tg.create_task(self.publish_data(self.data))
            except Exception:
                self.log.exception("Temperature loop failed.")
            self.log.debug(f"Waiting {self.sample_wait_time} seconds")
            await asyncio.sleep(self.sample_wait_time)
