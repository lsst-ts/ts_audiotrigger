

MAX_PI_GPIOS = 32


class MockPio:
    def __init__(self):
        self.gpios = [0 for _ in range(MAX_PI_GPIOS)]
        self._connected = True

    @property
    def connected(self):
        return self._connected

    def write(self, gpio : int, setting : int | bool):
        if gpio not in range(MAX_PI_GPIOS):
            raise ValueError
        self.gpios[gpio] = setting

    def read(self, gpio : int):
        if gpio not in range(MAX_PI_GPIOS):
            raise ValueError
        return self.gpios[gpio]