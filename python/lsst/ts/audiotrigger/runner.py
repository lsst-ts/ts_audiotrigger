import argparse
import asyncio
import logging

from lsst.ts import tcpip, utils

from .laser_alignment_listener import LaserAlignmentListener
from .read_serial_temp_scanner import SerialTemperatureScanner


def execute_runner():
    """Execute the runner service."""
    parser = argparse.ArgumentParser()
    parser.parse_args()
    Runner()


class Runner(tcpip.OneClientServer):
    """Implement a runner service that controls two services.

    Executes the laser alignment and read_thermal_scanner services.

    Attributes
    ----------
    log : `logging.Logger`
    laser_alignment : `None`
    serial_scanner : `None`
    heartbeat_task : `asyncio.Future`
    """

    def __init__(self) -> None:
        self.log = logging.getLogger(__name__)
        self.laser_alignment = None
        self.serial_scanner = None
        self.heartbeat_task = utils.make_done_future()

    def configure(self, config):
        pass

    async def start(self, **kwargs):
        """Start the services.

        Parameters
        ----------
        kwargs : `dict`
            Any arguments that can be passed to asyncio.create_server.
        """
        self.laser_alignment = LaserAlignmentListener(log=self.log)
        self.serial_scanner = SerialTemperatureScanner(log=self.log)
        self.heartbeat_task = asyncio.ensure_future(self.heartbeat)
        await asyncio.gather(
            [self.laser_alignment.start_task, self.serial_scanner.start_task]
        )
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
            await self.write_json(msg)
