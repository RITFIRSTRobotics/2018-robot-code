"""
Watchdog for the robots (to kill the motors if the FMS becomes disconnected)

:author: Connor Henley @thatging3rkid
"""
import time
from threading import Thread

from robot import WATCHDOG_TIME
import libs.piconzero as piconzero


class Watchdog(Thread):

    def __init__(self, logger):
        Thread.__init__(self)
        self.counter = 0
        self._logger = logger

    def run(self):
        self.counter += 1
        if self.counter > WATCHDOG_TIME:
            piconzero.cleanup()
            self._logger.error("watchdog timed out")

        time.sleep(1)

    def reset(self):
        self.counter = 0
