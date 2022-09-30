import chopper
import syncbox
import switchbox
import syncuino
import subprocess
import threading
from glob import glob
from mce_control import mce_control
#import time
#this script is going to be a mess


def chopper_setup():
    global chop_control 
    chop_control = chopper.Chopper()
    chop_control.setup_chopper(1, 6 + 3)  # 1 Hz 6 sec (plus some for the road)
    chop_control.run_chopper()


def syncbox_setup():
    global sync_control
    sync_control = syncbox.Syncbox()
    sync_control.use_dv()
    sync_control.go()


def switchbox_setup():
    global switch_control
    switch_control = switchbox.SwitchBox()
    switch_control.set_labchop()


def arduino_setup():
    global arduino
    arduino = syncuino.Syncuino()
    arduino.set_period(2508)
    arduino.set_frames(99)
    arduino.set_n_blanks(12)
    arduino.set_n_delays(0)


def mce_setup():
    global mce
    mce = mce_control()
    mce.write("cc", "use_sync", 2)
    mce.write("cc", "use_dv", 2)
    mce.write("cc", "select_clk", 1)


def do_skychop():
    print("set up chopper")
    chop_thread = threading.Thread(target=chopper_setup)
    chop_thread.start()

    print("set up sync box")
    sync_thread = threading.Thread(target=syncbox_setup)
    sync_thread.start()

    print("set up switch box")
    switch_thread = threading.Thread(target=switchbox_setup)
    switch_thread.start()

    print("set up arduino")
    arduino_thread = threading.Thread(target=arduino_setup)
    arduino_thread.start()

    print("set up MCE")
    mce_thread = threading.Thread(target=mce_setup)
    mce_thread.start()

    filename = "skychop_{num}"
    path = "/data/cryo/current_data/" 
    files=glob( path + filename.format(num="????"))
    if len(files)==0:
        no=0
        print("no files found, starting at 0")
    else:
        lastfile = sorted(files)[-1]
        no = lastfile.replace(path+filename.format(num=""),"")
        no = int(no)+1
    filename = filename.format(num="{:04d}".format(no))
    print(f"filename is {filename}")
    for thread in [
        chop_thread,
        sync_thread,
        switch_thread,
        arduino_thread,
        mce_thread
    ]:
        thread.join()

    zframetimes = subprocess.Popen([
        "/usr/bin/zframetimes",
        "-c",
        f"/data/cryo/current_data/{filename}",
        "1188",
        "99",
        "0"
    ])

    print("all systems go")

    print("MCE_RUN!")
    mce_run = subprocess.Popen([
        "/usr/mce/mce_script/script/mce_run",
        filename,
        "1188",
        "s",
        "--no-locking"],
        stdout = subprocess.PIPE
    )
    text = ""
    while "acq_go" not in text:
        outs = mce_run.stdout.readline()
        text = outs.decode()
        print(text)

    print("arduino go")
    arduino.go() # start after mce run is "ready"
    # ready is defined as having said acq_go

    print(mce_run.communicate())
    chop_control.stop()
    chop_control.open_chopper()
    zframetimes.wait()
    chopfile = subprocess.Popen([
        '/usr/local/bin/mcechopfile',
        f'/data/cryo/current_data/{filename}'
    ])
    chopfile.wait()

if __name__ == "__main__":
    do_skychop()
