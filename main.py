import socket
import leapseconds
from datetime import datetime
import hardware
import threading
from queue import Queue, Empty

def respond(sock, addr, context, value):
    """ This function isn't in the class in order to allow 
    different threads to also respond to APECS using their own 
    socket objects"""
    time_utc = datetime.utcnow()
    time_tai = leapseconds.utc_to_tai(time_utc)
    time_iso = time_tai.isoformat()
    response = f"{context}{value} {time_iso}"
    print(f"Sending APECS: {response}")
    sock.sendto(response.encode(), addr)

class ApecsListener():
    """ This is the main class. All instrument control will pass through 
    this class in the form of APECS commands sent to us on port 16255 via UDP.
    For functions that aren't actually commandable by APECS we set up "fake" apecs
    parameters or commands"""
    def __init__(self):
        self.apecs_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.apecs_socket.bind(("", 16255))
        self.keep_going = True
        """ This dictionary contains all the parameters APECS sends us.
        Theoretically it could set new parameters at runtime, but I think that's a
        bad idea so I tried to initialize all of the possible values here.

        I have made some custom values like gratingindex, usechopper, and scan_offset
        in order to command some of the parts of our system that APECS can't (yet!)
        """
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
        """ Set up the hardware management thread, the obsengine thread, and the main
        thread"""
        self.zeus.start()
        self.obsengine.start()
        self.obsengine.query_apecs_scan_num()
        self.zeus.apecs_callback=respond
        while self.keep_going: 
            message, address = self.apecs_socket.recvfrom(1024)
            self.apecs_address = address
            messages = message.decode().strip().split("\n")
            for m in messages:
                self.parse_message(m)

    def parse_message(self, message):
        """ When apecs sends us a message, it can have several different forms.
        Here, we decide what form is being sent and direct the command to the 
        appropriate function.
        If APECS wants to know the value of a current parameter in the backend, 
        it will send 
        APEX:BACKEND:Parameter?
        If APECS wants the backend to take a action it will send
        APEX:BACKEND:Action
        And if it wants to set a parameter it will send
        APEX:BACKEND:Parameter value
        or 
        APEX:BACKEND:CATEGORY:Parameter value

        The old obs program also accepted commands with ZSCR in them, but 
        I don't think we're currently using that.
        """
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
        """ When APECS wants us to set a parameter, it uses the format
        APEX:BACKEND:Parameter Value
        Here, we store all parameters and values in a dictionary.
        """
        param, value = message.split(' ')
        cmdless_param = param.replace("cmd", "")
        self.operating_parameters[cmdless_param.lower()] = value
        return f"{param} {value}"

    def get_parameter(self, message):
        """ When APECS asks for the backend's current configuration,
        look it up in our config dictionary and return its value!"""
        param = message.strip('?')
        if param.lower() == "gratingindex": #Except here, where we don't know
            # the exact state of the hardware. So we query it instead.
            return f"{param} {self.zeus.grating.idx}"
        try:
            value = self.operating_parameters[param.lower()]
        except KeyError:
            value = "ERROR NOT_IMPLEMENTED"
        return f"{param} {value}"

    def execute(self, command):
        """ Executes a command sent by APECS. APECS commands have the format
        APEX:Backend:Command
        with no parameters or question marks."""
        response = command
        if command == "configure":
            self.zeus.apecs_address = self.apecs_address
            self.do_configuration()
            return # configuration may take a sec, so it will tell apecs when it's done
        elif command == "gratinggo": # Custom command not defined by APECS
            self.zeus.configure_grating(int(self.operating_parameters["gratingindex"]))
        elif command == "start":
            self.run()
        elif command == "stop":
            self.stop()
        elif command == "abort":
            self.stop()
        elif command == "auto_setup": # Custom command not defined by apecs
            self.zeus.auto_setup()
        else:
            response = response + " ERROR NOT_IMPLEMENTED"
        respond(self.apecs_socket,self.apecs_address,"APEX:ZEUS2BE:", response)

    def do_configuration(self):
        """ Command the zeus-2 hardware chain to configure itself based on 
        the parameters supplied by the APECS interface."""
        op = self.operating_parameters
        self.zeus.configure_sync(int(op["integrationtime"])*100, 
                                 int(op["synctime"]), 
                                 int(op["blanktime"]),
                                 use_chopper=op["usechopper"]=="1")
        self.obsengine.query_apecs_scan_num()

    def run(self):
        """ 
        Commands the zeus-2 hardware stack to start taking data!
        Also sets the filename that the data will be acquired into.
        For now, the files will be called either "total_power", "skychop", or "apecs"
        depending on what kind of data is being taken. Optionally, skychops can have
        their scan number modified so that they match the desired apecs scan."""
        self.operating_parameters["state"] = "ENABLED"
        if int(self.operating_parameters["blanktime"]) == 0:
            self.zeus.take_data(f"total_power_{self.obsengine.scan_num}_{{num}}")
        elif self.operating_parameters["usechopper"] == "1":
            filenum = int(self.obsengine.scan_num) + int(self.operating_parameters["scan_offset"])
            self.zeus.take_data(f"skychop_{filenum}_{{num}}")
        else:
            self.zeus.take_data(f"apecs_{self.obsengine.scan_num}_{{num}}")

    def stop(self):
        """ For now this does nothing but change the state of the backend.
        Theoretically we could stop mce_run, but usually that requires a lot
        of cleanup"""
        self.operating_parameters["state"] = "DISABLED"


class ObsEngineInterface(threading.Thread):
    """ This class interfaces with the APECS ObsEngine. Right now it has 
    exactly one function: to query the scan number for use in file naming."""
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
