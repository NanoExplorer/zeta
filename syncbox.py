import serial

SYNC_BOX_COM = "/dev/ttyS5"


class Syncbox:
    def __init__(self):
        self.com = serial.Serial(port=SYNC_BOX_COM, timeout=1)
        self.numrows = 33
        self.rowlen = 50
        self.mode = 'rt'
        self.data_rate = 1000
        self.set_num_rows(self.numrows)
        self.set_row_len(self.rowlen)

    def __del__(self):
        self.com.close()

    def set_num_rows(self, numrows):
        self.com.write(f"nr {numrows}\r\n".encode())
        self.numrows = numrows

    def set_row_len(self, rowlen):
        self.com.write(f"rl {rowlen}\r\n".encode())
        self.rowlen = rowlen

    def use_dv(self):
        # In this mode we listen for arduino pulses and use those
        # to syncronize the mce and the clock card
        self.com.write("rt\r\n".encode())
        self.mode = 'rt'

    def free_run(self, data_rate=1000):
        # In this mode the sync box is constantly commanding the 
        # MCE to take data. I have not quite figured out the 
        # data_rate parameter.
        self.com.write(f"fr {data_rate}\r\n".encode())
        self.mode = 'fr'
        self.data_rate = data_rate

    def go(self):
        self.com.write("go\r\n".encode())

    def stop(self):
        self.com.write("stop\r\n".encode())

    def reset(self):
        self.com.write("re\r\n".encode())

    # def get_hardware_params(self):
    #     old program didn't have this and it wasn't an issue
    #     self.com.write("?\r\n")
    #     data = self.com.readlines()
    #     for line in data:
    #         print(line)

