import motors
import time

CHOPPER_ADDR = 5
MOTORS_IP = "10.0.6.165"
#MOTORS_IP = "10.0.7.215"
MOTORS_PORT = 4000
STEPS_PER_CHOP = 560


class Chopper(motors.Motor):
    def __init__(self):
        super().__init__(MOTORS_IP, MOTORS_PORT, CHOPPER_ADDR)
        self.run_steps = 0
        self.ready = False
        self.chop_freq_hz = 0
        self.run_time_s = 0
        self.open=False

    def load_saved_params(self):
        self.setup_chopper(self.chop_freq_hz, self.run_time_s)

    def setup_chopper(self, chop_freq_hz, run_time_s):
        self.chop_freq_hz = chop_freq_hz
        self.run_time_s = run_time_s
        if not 0.25 < chop_freq_hz < 3.5:
            self.ready = False
            raise ValueError("Invalid chop frequency")
        max_speed = int(chop_freq_hz * STEPS_PER_CHOP)
        base_speed = max(77, max_speed // 3)
        # apparently base speed should be between 77 and 3500
        print(f"chopper speeds (base,max):{base_speed},{max_speed}")
        self.set_base_speed(base_speed)
        self.set_max_speed(max_speed)
        self.set_acceleration(10)
        self.run_steps = round(run_time_s * max_speed)
        self.ready = True

    def run_chopper(self):
        if self.ready:
            self.open=False
            self.move_steps("+", self.run_steps)
        else:
            raise RuntimeError("Chopper not ready and cannot move!")

    def set_default_speed(self):
        self.set_base_speed(300)
        self.set_max_speed(800)
        self.set_acceleration(10)

    def open_chopper(self, disable=True, reload_params=True):
        if not self.open:
            self.set_default_speed()
            self.go_home(direction="-")
            self.wait_for_motor()
            self.move_steps("-", 40)
            self.wait_for_motor()
            if disable:
                time.sleep(1)
                self.disable_motor()
            if reload_params and self.ready:
                self.load_saved_params()
            self.open=True

    def close_chopper(self, disable=True, reload_params=True):
        self.open=False
        self.open_chopper(disable=False, reload_params=False)
        self.move_steps("-", 320)
        self.wait_for_motor()
        if disable:
            time.sleep(1)
            self.disable_motor()
        if reload_params and self.ready:
            self.load_saved_params()


if __name__ == "__main__":
    if input("Run chopper tests? [y/n]") != 'y':
        exit()

    print("init chopper")

    c = Chopper()
    # c.set_default_speed()
    # print("open chopper")
    # c.open_chopper()
    #time.sleep(10)
    #print("close chopper")
    #c.close_chopper()
    #c.setup_chopper(1, 6 + 3) # 1 Hz 6 sec (plus some for the road)

    #c.run_chopper()
    #print(c.check_error())
    #c.wait_for_motor()
    c.stop()
