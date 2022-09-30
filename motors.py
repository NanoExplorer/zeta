import time
from vlinx import Vlinx


class MotorError(Exception):
    pass


class Motor(Vlinx):
    def __init__(self, address, port, motor_number):
        """ API for interfacing with ZEUS-2 motorbox 
        ZEUS-2 motorbox uses a vlinx serial-to-tcp server
        for communication.

        :param address: address of motor box vlinx. This can 
            be a DNS-resolvable hostname like zeus2motorbox.apex-telescope.org
            or it can be an IP address.
        :param port: Port the vlinx is listening on. Usually 4000.
        :param motor_number: There are 4 motor controllers on the 
            same serial line, so you need the address of the motor
            that you are going to use. Likely it will be:
            * 1: 40-4K heat switch or grating
            * 3: ADR heat switch
            * 5: chopper wheel

        The object returned will be able to control the motor box
        and provides helpful methods for accomplishing that.
        """
        self.motor = motor_number
        super().__init__(address, port)

    def set_max_speed(self, speed, retries = 2):
        self.repeat_command_until_success(f"M{speed}", retries=retries)

    def set_base_speed(self, speed, retries = 2):
        self.repeat_command_until_success(f"B{speed}", retries=retries)

    def set_acceleration(self, accel, retries = 2):
        self.repeat_command_until_success(f"A{accel}", retries=retries)

    def move_steps(self, direction, nsteps):
        """ move nsteps steps in a direction.
        :param direction: should be a string containing "+" for CW and
            "-" for CCW.
        :param nsteps: is the number of steps to move 
        """
        self.send_command(direction)
        self.send_command(f"N{nsteps}")
        self.send_command("O0")
        self.send_command("G")

    def disable_motor(self):
        self.send_command("O1")

    def get_current_index(self):
        """ Returns the index the controller thinks it is at """
        return self.command_response("VZ")

    def stop(self):
        """ Stops the motor if it is currently moving """
        self.send_command(".")

    def start_slew(self,direction="-"):
        """ Sends the commands necessary for moving the motor to its
        home position / limit switch but does not ensure it gets there """
        self.send_command(direction)  # set direction to negative / clockwise
        self.send_command("O0")  # make sure motor is enabled
        self.send_command("S")  # slew to limit switch      

    def go_home(self,direction="+"):
        self.send_command(direction)
        self.send_command("O0")
        self.send_command("H0")

    def slew_to_hardlimit(self, try_again=True):
        """ Sends the motor to its home position and blocks until it has 
        stopped moving """
        self.start_slew()
        self.wait_for_motor()
        self.send_command("Z0")  # set internal step counter to 0
        at_hard_limit = self.check_hard_limit()
        if not at_hard_limit and try_again:
            self.slew_to_hardlimit(try_again=False)
        elif not at_hard_limit:
            raise MotorError("Could not home motor")

    def wait_for_motor(self):
        """ Blocks until the motor has stopped moving """
        moving = True
        while moving:
            status = self.command_response("VF")
            # status = 1 , moving
            # status = 0 , stopped
            # status = -1, error
            try:
                moving = int(status) > 0
            except ValueError:
                pass
            time.sleep(1)

    def go_to_index(self, index):
        """ Move to a specific index. 
        Note this does NOT take into account the grating
        quirk that we always want to finish by moving in the same
        direction. """
        self.send_command(f"P{index}")
        self.send_command("O0")
        self.send_command("G")

    def check_hard_limit(self):
        """ Returns the status of the limit switch.
        :return: 1 if the motor is at the limit, 0 if it is not. """
        hardlimit, softlimit = self.check_limits()
        return hardlimit

    def get_limit_binary(self):
        limit = int(self.command_response("L0"))
        return limit

    def check_limits(self):
        limits = self.get_limit_binary()
        #hooray for bit hacking. apparently LSB is hardlimit and 
        # second bit is soft limit. There are probably others too...
        # The manual is no help at all. it says LSB is soft and MSB is hard...
        # Comments from old program say that is probably wrong.
        not_hardlimit = 1 & limits
        not_softlimit = 2 & limits
        hardlimit = not not_hardlimit
        softlimit = not not_softlimit
        return hardlimit, softlimit

    def check_error(self):
        """ Should return 0 unless there's an error 
        known error codes:
        * 8192 = motor running
        """
        err = int(self.command_response("!"))
        # 8192 means the motor is running...

        return err

    def command_response(self,cmd):
        """ Sends a command and listens for a response """
        self.flush()
        self.send_command(cmd)
        return self.listen()

    def send_command(self, command):
        """ Send a command directly to the motor box.
        You need to know what the command is since many
        of them are very arcane """
        message = f"@{self.motor}{command}\r"
        self.send(message)
        time.sleep(0.1)

    def send_command_check_error(self, command):
        self.send_command(command)
        return self.command_response("!")

    def repeat_command_until_success(self, command, retries=2):
        err = self.send_command_check_error(command)
        
        if err!="0" and retries > 0:
            self.repeat_command_until_success(command, retries=retries-1)
            print(f"Motor box error: {repr(err)}")
        elif err!="0" and retries == 0:
            raise MotorError(f"could not execute command {command}")
