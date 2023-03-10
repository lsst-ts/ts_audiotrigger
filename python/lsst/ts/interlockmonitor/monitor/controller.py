# This file is part of ts_interlockmonitor.
#
# Developed for the Vera C. Rubin Observatory Telescope and Site Systems.
# This product includes software developed by the Vera C. Rubin Project
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

import sounddevice as sd
from gpiozero import LED, Button


# TODO DM-38281 Implement laser alignment monitor for triggering the
# interlock when laser is misaligned.
class InterlockMonitor:
    """Implement the laser alignment interlock monitor.
    This class records the frequency(hz) of the laser's alignment through
    a USB microphone which then checks the range of the frequency.
    If the frequency is within a certain range then the laser is considered
    misaligned and should trigger the interlock through the use of a relay
    connected to the interlock via GPIO pins on the Raspberry Pi.
    """

    def __init__(self) -> None:
        self.relay = LED(16)
        self.restart_button = Button(23, pull_up=False)
        self.input = 2
        self.output = 4
        self.fs = sd.query_devices(input)["default_samplerate"]
        self.interval = 0.1

    def restart(self):
        """Restart the interlock relay."""
        self.relay.off()

    @property
    def relay_status(self):
        """Get the current status of the interlock relay.

        1 is interlock engaged (can't propagate laser).
        0 is interlock disengaged (can propagate laser).
        """
        pass

    def record_data(self):
        """Record audio from microphone."""
        pass

    def analyze_data(self):
        """Analyze the frequency(hz) of the audio."""
        pass
