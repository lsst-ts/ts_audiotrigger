__all__ = ["execute_runner", "Runner"]

import argparse
import asyncio
import json
import logging
import pathlib
from importlib import resources as impresources

import jsonschema
from lsst.ts import utils

from . import schemas
from .constants import SLEEP
from .laser_alignment_listener import LaserAlignmentListener
from .read_serial_temp_scanner import SerialTemperatureScanner


def execute_runner():
    """Execute the runner service."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulation-mode", action="store_true")
    parser.add_argument("--disable-microphone", action="store_true")
    parser.add_argument("--lal-log-port", default=18840, type=int)
    args = parser.parse_args()
    asyncio.run(amain(args))


async def amain(args):
    logging.basicConfig(
        format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
        level=logging.INFO,
    )
    log = logging.getLogger(__name__)
    runner = Runner(
        log=log,
        disable_microphone=args.disable_microphone,
        simulation_mode=args.simulation_mode,
    )
    run_task = asyncio.create_task(runner.run())
    await run_task


class Runner:
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

    def __init__(self, log, disable_microphone, simulation_mode, lal_log_port) -> None:
        self.log = log
        self.disable_microphone = disable_microphone
        self.simulation_mode = simulation_mode
        self.lal_log_port = lal_log_port
        self.laser_alignment = None
        self.serial_scanner = None
        self.run_task = utils.make_done_future()
        self.validator = jsonschema.Draft7Validator(
            schema=json.load(
                pathlib.Path(impresources.files(schemas) / "heartbeat.json").open()
            )
        )

    def configure(self, config):
        # TODO: DM-47286 Add configure method and schema
        pass

    async def run(self):
        self.laser_alignment = LaserAlignmentListener(
            log=self.log,
            simulation_mode=self.simulation_mode,
            disable_microphone=self.disable_microphone,
            port=self.lal_log_port,
        )
        self.serial_scanner = SerialTemperatureScanner(
            log=self.log, simulation_mode=self.simulation_mode
        )
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.serial_scanner.start())
            tg.create_task(self.laser_alignment.start())

        while True:
            try:
                await asyncio.sleep(SLEEP)
            except asyncio.CancelledError:
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(self.serial_scanner.stop())
                    tg.create_task(self.laser_alignment.stop())
                self.log.info("Tasks closed.")
                raise
            finally:
                pass
