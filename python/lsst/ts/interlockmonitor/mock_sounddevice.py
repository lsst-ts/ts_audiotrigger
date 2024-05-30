
import numpy as np
import random

class MockSoundDevice:
    def __init__(self):
        self._default_device = (None, None)

        self.microphone_devicelist_dict = {"name" : "microphone", "hostapi" : None, "max_input_channels" : 1, "max_output_channels" : 0, "default_low_input_latency" : 0, "default_low_output_latency" : 0, "default_high_input_latency" : 0, "default_high_output_latency":0, "default_samplerate" : 44100}


        self.device_list = [None, None, self.microphone_devicelist_dict]

        #generate audio data
        self.data = [0 for _ in range(44100)]

                                                                                                                                                 

    def query_devices(self, input:int):
        
        if input not in range(len(self.device_list)):
            raise ValueError

        return self.device_list[input]

    def check_input_settings(self, device=None, channels=None, dtype=None, extra_settings=None, samplerate=None):
            # if settings valid, do nothing
            # if not, raise exception
            pass

    
    def rec(self, frames=None, samplerate=None, channels=None, dtype=None, out=None, mapping=None, blocking=False, **kwargs):
        returned_data = self.data
        if len(self.data) > frames:
            #data is too long
            returned_data = self.data[:frames]
        elif len(self.data) < frames:
            #data too short, pad with 0s
            returned_data = self.data + [0 for _ in range(frames - len(self.data))]
        
        generated_data = np.ndarray(shape=(2, 2), buffer=np.array(returned_data), dtype=np.float32)
        return generated_data
    
    def fill_with_random_data(self, rangelow, rangehigh, frames):
        self.data = [random.randrange(rangelow, rangehigh) for _ in range(frames)]

    def fill_with_data(self, data):
        self.data = data
        