import socket
import time

VERBOSE = True

class Vlinx:
    """ Provides a basic and hopefully extensible basis for 
    communicating with devices via Vlinx Serial Servers"""
    def __init__(self,address,port):
        self.address = address
        self.port = port
        self.socket = socket.create_connection((address, port))
        self.socket.settimeout(0.1)

    def __del__(self):
        self.socket.close()

    def send(self, message):
        """ Send a message to the Vlinx. You need to make sure it has
        everything it needs, including line endings!"""
        # print(f"sending message {message}")
        if VERBOSE:
            print(f"vlinx sending {repr(message)} to {self.address}")
        self.socket.send(message.encode())
        time.sleep(0.1)  # ensure that we don't overwhelm the vlinx

    def listen(self):
        """ Listen for any data that may be sent by the vlinx
        to the client """
        data = ''
        while '\r' not in data:
            try:
                data = data + self.socket.recv(4096).decode()
                if VERBOSE:
                    print(f"got data {repr(data)}")
            except socket.error:
                return data
        return data.strip()

    def flush(self):
        """ Gets rid of any data that may be sitting around in the pipeline..."""
        try:
            self.socket.settimeout(0.1)
            self.socket.recv(4096)
        except TimeoutError:
            pass
        except socket.timeout:
            pass
        finally:
            self.socket.settimeout(3)
