
from collections import OrderedDict


class MockThermalSensor:
    def __init__(self):
        self._inWaiting = 0
        self.sensor_dict = OrderedDict(
                {"C01": "Ambient", "C02": "Laser", "C03": "FC", "C04": "A", "C05": "B", "C06": "C", "C07": "D", "C08": "E"}
        ) 
        self.data_dict = OrderedDict(
                {"C01": 0, "C02": 0, "C03": 0, "C04": 0, "C05": 0, "C06": 0, "C07": 0, "C08": 0}
        )
    
    def inWaiting(self):
        return self._inWaiting
    

    def inject_data(self, data, dict_position=None):
        if dict_position:
            if dict_position in self.data_dict:
                self.data_dict[dict_position] = data
            else:
                raise ValueError
        else:
            for sensor in self.data_dict:
                self.data_dict[sensor] = data
    
    def read(self, amount: int = 0):
        # These will need to be in some configuration file
        generated_read_string = "something\n"
        for sensor in self.sensor_dict:
            generated_read_string = f"{generated_read_string}{sensor}={self.data_dict[sensor]},"
        generated_read_string = generated_read_string + "\nsomething               "
        generated_read_string = generated_read_string.encode("ISO-8859-1")
        
        if amount and len(generated_read_string >= amount):
            return generated_read_string[:amount]
        return generated_read_string
            