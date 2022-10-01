import threading
from queue import Queue, Empty
import syncuino
import syncbox
import switchbox
import grating
import chopper
from mce_control import mce_control
from glob import glob
import subprocess
import traceback
import socket

class ZeusHardwareManager(threading.Thread):
    """ High level interface for all the hardware interfaces for ZEUS-2.
    This is a Thread, so you have to be a little bit careful with it.
    It is recommended not to access any member variables or call any methods
    that begin with underscore ("_"). Instead, the methods that do not
    start with an underscore provide all of the functionality that should
    be needed.

    If you decide to break these rules, acquier the hardware_lock while doing so.
     """
    def __init__(self):
        threading.Thread.__init__(self)
        self.hardware_lock = threading.Lock()
        # acquire this lock if you want to talk to the hardware!
        # it's not recommended, but you can do it.
        self.apecs_callback=None
        self.apecs_address = None
        # Hardware objects
        self.arduino = None
        self.chopper = None
        self.switchbox = None
        self.syncbox = None
        self.grating = None
        self.mce = None
        self.mce_error = False
        # Control queue
        self.q = Queue()

        # Acquisition parameters
        self.use_chopper = False
        self.integration_time = 0  # ms time mce_run should integrate for
        self.sync_time = 0  # us; time for one chopper phase = 1/2f
        self.blank_time = 0  # us; time for the wobbler to move.
        self.do_sync = True
        self.n_frames = 0
        self.filename = ""
        self.reads_per_phase = 0
        self.beams_since_last_configure = 0
        self.want_grating_index = 0

        self.scan_num = 0
        self.keep_going = True
        self.send_addr = ("10.0.2.171",33133)


    def configure_grating(self,idx):
        if self.grating.idx == idx:
            return
        else:
            self.want_grating_index = idx
            self.q.put("grating")

    def configure_sync(
        self, 
        integration_time,
        sync_time, 
        blank_time,
        use_chopper=False
    ):
        """ Use this method to configure the system for synchronous
        acquisition! integration, sync, and blank times can come straight
        from APECS, and you can use this method for chopper acq as well.

        todo: provide calculator from chopper params to apecs-like params
        """
        if not self.mce_error and\
           self.integration_time == integration_time and \
           self.sync_time == sync_time and \
           self.blank_time == blank_time and \
           self.use_chopper == use_chopper and\
           self.do_sync:
            self.apecs_callback(self.apecs_socket,self.apecs_address,"APEX:ZEUS2BE:","configure")
        else:
            self.integration_time = integration_time
            self.sync_time = sync_time
            self.blank_time = blank_time
            self.use_chopper = use_chopper
            self.do_sync = True
            self.q.put("configure")
            self.mce_error = False
        self.beams_since_last_configure=0

    def take_data(self, filename):
        self.filename = filename
        self.q.put("run")

    def auto_setup(self):
        self.q.put("auto_setup")

    def run(self):
        print("Setting Up Equipment!")
        self.apecs_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.arduino = syncuino.Syncuino()
        self.syncbox = syncbox.Syncbox()
        self.mce = mce_control()
        self.chopper = chopper.Chopper()
        self.grating = grating.Grating()
        self.switchbox = switchbox.Switchbox()
        print("Done! Listening for APECS commands.")
        while self.keep_going:
            try:
                cmd = self.q.get(True, 30)
                with self.hardware_lock:
                    if cmd == "configure":
                        self._configure_hw_sync()
                    elif cmd == "run":
                        self._take_data()
                    elif cmd == "grating":
                        self.grating.grating_go_to_index(self.want_grating_index)
                    elif cmd == "auto_setup":
                        self._auto_setup()
            except Empty:
                pass
            except Exception as e:
                print(e)
                traceback.print_tb(e.__traceback__)
                self.chopper.stop() # just in case. It has happened before.
                # For now this will have to do.
                # As we collect errors we can 
                # write methods to handle them.
            if self.mce_error:
                print(self.mce_crash_reset().communicate())

    def _take_data(self):
        # make sure we don't overwrite anything
        print("Got GO command! taking data!")
        f = make_filename(self.filename)
        print(f"Acquiring data into file: {f}.")

        if self.use_chopper:
            self.chopper.run_chopper()
        if self.do_sync:
            self.syncbox.go()
            # start watching the clock card for time stamps
            # to write into .ts file 
            zframetimes = self._open_frametimes(f)
        self.apecs_callback(self.apecs_socket,self.apecs_address,"APEX:ZEUS2BE:","start")
        #start mce_run
        mce_run = self._mce_run(f)

        #wait for go signal from mce_run
        text = ""
        while "acq_go" not in text:
            outs = mce_run.stdout.readline()
            text = outs.decode()
            print(text.strip())
        if self.do_sync:
            self.arduino.go()  # if the arduino starts generating pulses
            # before the MCE actually starts taking data, the MCE will not
            # get the correct number of pulses and will hang.
            print("Arduino is go!")
        print("waiting for mce_run to finish acquiring...")
        
        try:
            output = mce_run.communicate(timeout=self.integration_time/1000 + 2)
            print(output)  # will probably print nothing
        # because usually "acq_go" is the last thing it says
        # But it does print if there are errors
            if "error" in output[0].decode():
                print("MCE error! will need to reset mce!")
                self.mce_error = True
        except subprocess.TimeoutExpired:
            self.mce_error = True
            print("MCE acquire is taking too long! setting error and killing...")
            mce_run.kill()
            print(mce_run.communicate())

        if self.use_chopper:
            self.chopper.stop()
            self.chopper.open_chopper()
        if self.do_sync:
            zframetimes.wait()
            self._make_chop_file(f)
        self._make_hk_file(f)
        print(f"finished acquiring data file {f}.")
        self.beams_since_last_configure += 1

    def _make_chop_file(self,filename):
        c = subprocess.Popen([
            "/usr/local/bin/mcechopfile",
            f"/data/cryo/current_data/{filename}"
        ])
        c.wait()

    def _make_hk_file(self,filename):
        # I apologize from the bottom of my heart 
        # for this implementation.
        with open(f"/data/cryo/current_data/{filename}.hk", 'w') as hkfile:
            if self.use_chopper:
                chop_state="running"
            elif self.chopper.open:
                chop_state="open"
            else:
                chop_state="closed"
            hkfile.write(f"""#ZEUS-2 hk
MCE_cmd  : see runfile
acq_mode : None
int_time     : {self.integration_time}
choppos_frms : {self.reads_per_phase}
repeat_index : 1
gratingindex : {self.grating.idx}
chopper_pos  : {chop_state}
blanksw_pos  : {self.switchbox.state}
# ---- MCE config --- 
sync_acq      : {self.do_sync}
row_len       : 100
num_rows      : 33
row_dly       : 4
data_rate     : 38
sample_dly    : 90
sample_num    : 10
fb_dly        : 18
tes_bias_idle : see runfile
crash         : {self.mce_error}
# ---- APEX ----
beam_number : {self.beams_since_last_configure}
nod_cycle   : {self.beams_since_last_configure//2}
nod_mode    : unknown sorry. If this is a science target then almost certainly.
beam_is_R   : {True if self.beams_since_last_configure%2==1 else False}
# ---- APECS set ----
sync_time    : {self.sync_time}
blank_time   : {self.blank_time}
num_phases   : 2
num_specchan : 1
itime        : {self.integration_time}
# ---- user set ----
object     : None
wavelength : 0.00
at_pixel   : None
chop_freq  : 1/(2*sync_time)""")


    def _mce_run(self, filename):
        mcer = subprocess.Popen([
            "/usr/mce/mce_script/script/mce_run",
            filename,
            str(self.n_frames),
            "s",
            f"--timeout={self.sync_time//500}"],
            stdout = subprocess.PIPE
        )
        return mcer

    def mce_crash_reset(self):
        mcer = subprocess.Popen([
            "/home/mce/.local/bin/mce_auto_crash_reset"],
            stdout = subprocess.PIPE
        )
        return mcer

    def _auto_setup(self):
        a = subprocess.Popen([
            "auto_setup"],
            stdout=subprocess.PIPE
        )
        print(a.communicate()[0].decode())
        if self.do_sync:
            
            self.mce.write("cc", "use_sync", 2)
            self.mce.write("cc", "use_dv", 2)
            self.mce.write("cc", "select_clk", 1)

    def _open_frametimes(self,filename):
        print("opening zframetimes...")
        filename = f"/data/cryo/current_data/{filename}"
        zf = subprocess.Popen([
            "/usr/bin/zframetimes",
            "-c",
            filename,
            str(self.n_frames),
            str(self.reads_per_phase),
            "0"
        ])
        return zf

    def _configure_hw_sync(self):
        print("Got configure")
        on_time_per_phase = self.sync_time - self.blank_time  # us
        num_phases = round(self.integration_time * 1000 / self.sync_time)
        readout_rate = float(self.mce.readout_rate()[0])
        reads_per_phase = round((on_time_per_phase * readout_rate) / 1e6)
        total_reads = num_phases*reads_per_phase
        read_freq = 1/(self.sync_time*2)*1e6
        beam_time = self.integration_time / 1000
        arduino_period = round(1/readout_rate*1e6)

        print(f"""phase time: {on_time_per_phase/1e6}
               phases: {num_phases}
               frames per phase: {reads_per_phase}
               total frames: {total_reads}
               integration time: {beam_time}
               arduino period: {arduino_period}
               """)

        self.arduino.set_period(arduino_period)
        self.arduino.set_frames(reads_per_phase)
        self.arduino.set_n_blanks(num_phases)
        self.arduino.set_n_delays(0)  # I don't know what this is...

        if self.use_chopper:
            self.switchbox.set_labchop()
            print("switch box set to lab")
            self.chopper.setup_chopper(read_freq,
                                       beam_time + 3)
            print("chopper set up complete")
        else:
            self.chopper.open_chopper()
            self.switchbox.set_apex()

        self.syncbox.use_dv()
        print("sync box dv on")
        self.mce.write("cc", "use_sync", 2)
        self.mce.write("cc", "use_dv", 2)
        self.mce.write("cc", "select_clk", 1)
        print("mce in sync mode")
        self.n_frames = round(total_reads)
        self.reads_per_phase = round(reads_per_phase)
        print("We Are Configured!")
        self.apecs_callback(self.apecs_socket,self.apecs_address,"APEX:ZEUS2BE:","configure")

def make_filename(filename):
    if "{num}" in filename:
        path = "/data/cryo/current_data/" 
        files = glob(path + filename.format(num="????"))
        if len(files) == 0:
            no = 0
            print("no files found, starting at 0")
        else:
            lastfile = sorted(files)[-1]
            no = lastfile.replace(path+filename.format(num=""), "")
            no = int(no)+1
        filename = filename.format(num="{:04d}".format(no))
    return filename 