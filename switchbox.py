from vlinx import Vlinx

SWITCH_BOX_IP = "10.0.6.166"
SWITCH_BOX_PORT = 4000


class Switchbox(Vlinx):
    def __init__(self):
        super().__init__(SWITCH_BOX_IP, SWITCH_BOX_PORT)
        self.state = self.get_state()

    def set_apex(self):
        # "B" position
        self.send("\x02")
        self.state = "B (APEX)"

    def set_labchop(self):
        # "A" position
        self.send("\x01")
        self.state = "A (chop)"

    def get_state(self):
        self.flush()

        self.send("\x10")
        value = self.listen()
        if 'A' in value:
            return 'A (chop)'
        elif 'B' in value:
            return 'B (APEX)'
        else:
            return value


if __name__ == "__main__":
    print(Switchbox().get_state())
