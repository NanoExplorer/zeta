import serial

ARDUINO_COM = '/dev/ttyACM0'

class Syncuino:
    def __init__(self):
        self.com = serial.Serial(port=ARDUINO_COM, timeout=1)

    def __del__(self):
        self.com.close()

    def set_period(self, t_usec):
        self.send_command(f"P{t_usec}")

    def set_frames(self, nframes):
        self.send_command(f"N{nframes}")

    def set_n_blanks(self, nblanks):
        self.send_command(f"B{nblanks}")

    def set_n_delays(self, ndelays):
        self.send_command(f"D{ndelays}")

    def go(self):
        """Arduino will start generating pulses at the next 
        blank signal"""
        self.send_command("G")

    def stop(self):
        self.send_command("S")

    def take(self):
        self.send_command("T")
        #Ignores blank but sends pulses

    def send_command(self, cmd, retries=2):
        self.com.write(f"{cmd}\n".encode())
        response = self.com.readline().decode()
        response = response.strip().replace("fpgv7 got: ", "")
        if response == cmd: 
            return response
        elif retries > 0:
            return self.send_command(cmd, retries-1)
        else:
            raise IOError("Could not communicate with Arduino")



