import motors

GRATING_ADDR = 1
MOTORS_IP = "10.0.6.165"
MOTORS_PORT = 4000
BASE_SPEED = 500
MAX_SPEED = 1500
ACCELERATION = 20
MAX_INDEX = 2845


class Grating(motors.Motor):
    def __init__(self):
        super().__init__(MOTORS_IP, MOTORS_PORT, GRATING_ADDR)
        self.set_max_speed(MAX_SPEED)
        self.set_base_speed(BASE_SPEED)
        self.set_acceleration(ACCELERATION)
        self.idx = int(self.get_current_index())
        limit = self.check_hard_limit()
        if self.idx == 0 and not limit:
            self.slew_to_hardlimit()

    def grating_go_to_index(self, index):
        """ This is the method you should use to move the grating.
        It makes sure to approach the desired index from the correct
        direction for repeatability """
        idx_now = int(self.get_current_index())
        if idx_now == index:
            return
        elif idx_now > index:
            self.go_to_index(index+1)
            self.wait_for_motor()
        else:
            self.go_to_index(index+71)
            self.wait_for_motor()
            self.go_to_index(index+1)
            self.wait_for_motor()
        self.idx = int(self.get_current_index())


if __name__ == "__main__":

    if input("run grating tests?[y/n]") == "y":
        g = Grating()
        print(f"Current index is {g.get_current_index()}")
        print("going home")

        g.slew_to_hardlimit()
        print("grating index: {idx} (should be 0)")
        print("slewing to grating index 500 (should go back and forth")

        g.grating_go_to_index(500)
        print(f"Current index is {g.get_current_index()}")
