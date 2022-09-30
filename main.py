import socket
import leapseconds
from datetime import datetime
import hardware
import threading
from queue import Queue, Empty

def respond(self, context, value):
    time_utc = datetime.utcnow()
    time_tai = leapseconds.utc_to_tai(time_utc)
    time_iso = time_tai.isoformat()
    response = f"{context}{value} {time_iso}"
    print(f"Sending APECS: {response}")
    self.apecs_socket.sendto(response.encode(), self.apecs_address)

class ApecsListener():
    #This controls everything
    def __init__(self):
        self.apecs_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.apecs_socket.bind(("", 16255))
        self.keep_going = True
        self.operating_parameters = {
            "integrationtime": 0,  #msec
            "blanktime": 0,  # usec
            "numspecchan": 1,
            "synctime": 0,  # usec
            "band1:startchan": "NOT_AVAILABLE",
            "band1:stopchan": "NOT_AVAILABLE",
            "band1:maxnumspecchan": "NOT_AVAILABLE",
            "band1:bandwidth": "160000.0",
            "band1:ifatten": 0,
            "band1:iflevel": 0,
            "numphases": 2,
            "mode": "EXTERNAL",
            "state": "DISABLED",
            "usedsections": 1,
            "usechopper": 0, # not an apex command, but fair game for tests
            "gratingindex": 0,  # same
            "scan_offset":0
        }  # contains all parameters that APECS uses 
        # value = value set by APECS
        self.apecs_address = None
        self.zeus = hardware.ZeusHardwareManager()
        self.obsengine = ObsEngineInterface()
    
    def go(self):
        self.zeus.start()
        self.obsengine.start()
        self.obsengine.query_apecs_scan_num()
        self.zeus.apecs_callback=self.respond
        while self.keep_going: 
            message, address = self.apecs_socket.recvfrom(1024)
            self.apecs_address = address
            messages = message.decode().strip().split("\n")
            for m in messages:
                self.parse_message(m)

    def parse_message(self, message):
        parts = message.strip().split(":")
        print(parts)
        if (parts[0] != "APEX" and parts[0] != "ZSCR") or parts[1] != "ZEUS2BE":
            print(f"ignoring odd message {message}")
            return
        relevant_info = message.replace("APEX:ZEUS2BE:", '').strip()
        if '?' in relevant_info:
            return_val = self.get_parameter(relevant_info)
        elif " " in relevant_info:
            return_val = self.set_parameter(relevant_info)
        else:
            return_val = self.execute(relevant_info.lower())
            return # execute does its own response

        respond(self.apecs_socket,self.apecs_address,f"{parts[0]}:{parts[1]}:", return_val)

    def set_parameter(self, message):
        param, value = message.split(' ')
        cmdless_param = param.replace("cmd", "")
        self.operating_parameters[cmdless_param.lower()] = value
        return f"{param} {value}"

    def get_parameter(self, message):
        param = message.strip('?')
        if param.lower() == "gratingindex":
            return f"{param} {self.zeus.grating.idx}"
        try:
            value = self.operating_parameters[param.lower()]
        except KeyError:
            value = "ERROR NOT_IMPLEMENTED"
        return f"{param} {value}"

    def execute(self, command):
        response = command
        self.zeus.apecs_address = self.apecs_address
        if command == "configure":
            self.do_configuration()
            return
        elif command == "gratinggo":
            self.zeus.configure_grating(int(self.operating_parameters["gratingindex"]))
        elif command == "start":
            self.run()
            return
        elif command == "stop":
            self.stop()
        elif command == "abort":
            self.stop()
        elif command == "auto_setup":
            self.zeus.auto_setup()
        else:
            response = response + " ERROR NOT_IMPLEMENTED"
        respond(self.apecs_socket,self.apecs_address,"APEX:ZEUS2BE:", response)

    def do_configuration(self):
        op = self.operating_parameters
        self.zeus.configure_sync(int(op["integrationtime"])*100, 
                                 int(op["synctime"]), 
                                 int(op["blanktime"]),
                                 use_chopper=op["usechopper"]=="1")
        self.obsengine.query_apecs_scan_num()

    def run(self):
        self.operating_parameters["state"] = "ENABLED"
        if self.operating_parameters["usechopper"] == "1":
            filenum = int(self.obsengine.scan_num) + int(self.operating_parameters["scan_offset"])
            self.zeus.take_data(f"skychop_{filenum}_{{num}}")
        else:
            self.zeus.take_data(f"apecs_{self.obsengine.scan_num}_{{num}}")

    def stop(self):
        self.operating_parameters["state"] = "DISABLED"


class ObsEngineInterface(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.apecs_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.scan_num = 0
        self.keep_going = True
        self.q = Queue()
        self.send_addr = ("10.0.2.171",33133)

    def query_apecs_scan_num(self):
        self.q.put("get")

    def _query_apecs_scan_num(self):
        #print("double check obsengine query params")
        #an number via UDP  from the  ObsEngine   
        #(Host control3.apex-telescope.org, UDP Port 33133, 
        #SCPI command "APEX:OBSENGINE:scanNum?”).
        print("queried scan number")
        self.apecs_socket.sendto("APEX:OBSENGINE:scanNum?".encode(), self.send_addr)

    def run(self):
        while self.keep_going:
            try:
                cmd = self.q.get(True, 30)
                if cmd == "get":
                    self._query_apecs_scan_num()
                    data,_=self.apecs_socket.recvfrom(1024)
                    self.scan_num = data.decode().split(" ")[1]
                    print(data)
            except Empty:
                pass


if __name__ == "__main__":
    client = ApecsListener()
    client.go()
