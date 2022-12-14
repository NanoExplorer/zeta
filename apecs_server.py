import socketserver
import time
from glob import glob
import leapseconds
import os
import numpy as np
import datetime
from zeustools import mce_data
import struct
import zeustools as zt
from zeustools import numba_reduction
import socket

APECS_FRAME_STRUCTURE = struct.Struct('<8s I 8s 28s I I I I I I f') 
# I don't really know about this but it's little endian encoded 
# it starts with 8char string "EEEIF   " followed by the integer 76
# and the 8char string "ZEUS2BE "
# Then you have the 28 character string "TIMESTAMPISOGPS "
# Then apparently the integration time as an integer in microseconds?
# followed by the phase integer 1 or 2
# then 4 integers ==1
# and then the data as a float.

def get_recent_file():
    connection_time = datetime.datetime.utcnow()
    conn_time_gps = leapseconds.utc_to_gps(connection_time)
    conn_timestamp_gps = conn_time_gps.replace(tzinfo=datetime.timezone.utc).timestamp()
    path = "/data/cryo/current_data/" 
    old_file = True
    # find the correct data file based on timestamps
    while old_file:
        files = glob(path + "*.ts")
        files = sorted(files)[::-1]
        for file in files:
            modified_time = os.path.getmtime(file)
            if modified_time > time.time() - 9:
                print(f"{file} was modified recently...")
                ts = np.genfromtxt(file, invalid_raise=False)
                try:
                    firsttime = ts[0, 1] 

                    if firsttime > conn_timestamp_gps-1:
                        try:
                            mce_data.SmallMCEFile(file.replace(".ts", ""))
                            old_file = False
                        except:
                            continue
                        return file
                except IndexError:
                    pass
        print("no new files...")
        time.sleep(1)


def read_as_much_as_possible(data_file):
    ts = np.genfromtxt(data_file+'.ts', invalid_raise=False)[:, 1]
    frames_ready = len(ts)
    mcedata = mce_data.SmallMCEFile(data_file)
    data = mcedata.Read(row_col=True)
    cube = data.data
    chop = data.chop
    if cube.shape[2] < frames_ready:
        frames_ready = cube.shape[2]
        ts = ts[0:frames_ready]
    elif cube.shape[2] > frames_ready:
        cube = cube[:, :, 0:frames_ready]
        chop = chop[0:frames_ready]
    #print(cube.shape)
    #print(frames_ready)
    d = numba_reduction.offset_data_reduction(chop, cube)
    return d, chop, ts, frames_ready


def get_struct(ts, itime, chop, data, i):
    ts_datetime = datetime.datetime.utcfromtimestamp(ts[i])
    timestamp = ts_datetime.isoformat()[:24]+"GPS "
    itimeus = int(itime[i]*1e6)
    pfstring = f"{timestamp} {itimeus} {int(chop[i])} {data}"

    print(pfstring)
    encoded_frame=APECS_FRAME_STRUCTURE.pack(
        'EEEIF   '.encode(), 
        76, 
        'ZEUS2BE '.encode(),
        timestamp.encode(),
        itimeus,
        int(chop[i]),
        1, 1, 1, 1,
        data)
    return encoded_frame, pfstring


def keep_reading_file(data_file, mce_px, callback):
    mcedata = mce_data.SmallMCEFile(data_file)
    nframes = int(mcedata.runfile.data["FRAMEACQ"]["DATA_FRAMECOUNT"].strip())

    frames_sent = 0
    lines_sent = 0
    with open(data_file+".pf", 'w') as pf:
        while frames_sent < nframes-1:
            print(frames_sent)
            d, chop, ts, frames_ready = read_as_much_as_possible(data_file)
            #print(d[1,1])
            chunked_ts, chunked_chop = numba_reduction.chunk_data_1d(chop, ts)
            ts_for_apex = numba_reduction.reduce_chunks_1d(chunked_ts)
            chop_for_apex = np.array(chunked_chop) + 1
            itime_for_apex = [c[-1] - c[0] for c in chunked_ts]
            # print(len(chunked_ts[-1]),len(chunked_ts[-2]))
            lines_to_send = d.shape[2]*2
            if len(chunked_ts[-1]) < len(chunked_ts[-2]):
                lines_to_send -= 1 
            for i in range(lines_sent, lines_to_send):
                if chop_for_apex[i] == 1:
                    data_for_apex = 1
                else:
                    data_for_apex = []
                    for px in mce_px:
                        data_for_apex.append(d[px][i//2])
                    data_for_apex = np.mean(data_for_apex)

                encoded_frame, pfstring = get_struct(
                    ts_for_apex,
                    itime_for_apex,
                    chop_for_apex,
                    data_for_apex,
                    i
                )
                pf.write(pfstring+'\n')
                callback(encoded_frame)
                lines_sent += 1
            frames_sent = frames_ready   
            time.sleep(0.5)


class ApecsRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            print("Apex data connected!")
            am = zt.ArrayMapper()
            correct_ts_file = get_recent_file()
            data_file = correct_ts_file.replace(".ts", "")

            pxs = np.genfromtxt("px.cfg", dtype=int)
            if len(pxs.shape) == 1:
                pxs = [pxs]
            print(pxs)
            mce_px = []
            for px in pxs:
                mce_px.append(am.phys_to_mce(px[0], px[1], px[2]))
            keep_reading_file(data_file, mce_px, self.sender)
        
        except BrokenPipeError:
            print("Disconnected")

    def sender(self, frame):
        self.request.sendall(frame)


class NonBlockingTCPServer(socketserver.TCPServer):
    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)


if __name__ == "__main__":
    with NonBlockingTCPServer(('0.0.0.0',25144),ApecsRequestHandler) as server:
        server.serve_forever()
