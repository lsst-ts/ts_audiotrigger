import argparse
import asyncio
import json
import logging
import pathlib
from importlib import resources as impresources

import jsonschema
from lsst.ts import tcpip, utils

from . import schemas
from .constants import SLEEP

# from .laser_alignment_listener import LaserAlignmentListener
from .read_serial_temp_scanner import SerialTemperatureScanner


def execute_runner():
    """Execute the runner service."""
    parser = argparse.ArgumentParser()
    parser.parse_args()
    asyncio.run(amain())


async def amain():
    return Runner()


class Runner(tcpip.OneClientServer):
    """Implement a runner service that controls two services.

    Executes the laser alignment and read_thermal_scanner services.

    Attributes
    ----------
    log : `logging.Logger`
        Log instance.
    laser_alignment : `None`
        Laser alignment instance.
    serial_scanner : `None`
        Serial scanner instance.
    heartbeat_task : `asyncio.Future`
        Heartbeat publisher task.
    """

    def __init__(self) -> None:
        self.log = logging.getLogger(__name__)
        self.laser_alignment = None
        self.serial_scanner = None
        self.heartbeat_task = utils.make_done_future()
        self.validator = jsonschema.Draft7Validator(
            schema=json.load(
                pathlib.Path(impresources.files(schemas) / "heartbeat.json").open()
            )
        )
        super().__init__(host=tcpip.LOCAL_HOST, port=8080, log=self.log)

    def configure(self, config):
        # TODO: DM-47286 Add configure method and schema
        pass

    async def start(self, **kwargs):
        """Start the services.

        Parameters
        ----------
        kwargs : `dict`
            Any arguments that can be passed to asyncio.create_server.
        """
        # self.laser_alignment = LaserAlignmentListener(log=self.log)
        self.serial_scanner = SerialTemperatureScanner(log=self.log)
        self.heartbeat_task = asyncio.ensure_future(self.heartbeat())
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.serial_scanner.start_task)
        await super().start(kwargs=kwargs)

    async def close(self):
        """Close the services."""
        await asyncio.gather(
            [
                self.laser_alignment.close(),
                self.serial_scanner.close(),
                self.heartbeat_task.cancel(),
            ]
        )
        await super().close()

    async def heartbeat(self):
        """Send heartbeat message indicating liveness."""
        while True:
            msg = {"id": "heartbeat", "value": "alive"}
            try:
                self.validator.validate(msg)
            except Exception:
                pass
            await self.write_json(msg)
            await asyncio.sleep(SLEEP)
