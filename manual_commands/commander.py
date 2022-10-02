from gooey import Gooey, GooeyParser
import socket
import time


@Gooey(program_name="Zeus-2 Commands",
       show_sidebar=True,
       advanced=True)  #,return_to_config=True)
def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    addr = ("10.0.2.143", 16255)
    s.sendto("APEX:ZEUS2BE:GratingIndex?".encode(), addr)
    data,_=s.recvfrom(1024)

    gi = str(data.decode().split(" ")[1])

    parser = GooeyParser(description="Zeus-2 Commands")
    sp = parser.add_subparsers(help="idk", dest="sp")
    sc = sp.add_parser("Skychop", help="run skychops")

    sc.add_argument('--duration', gooey_options={'label':"Duration"}, widget="IntegerField", help="skychop duration in seconds",default=6)
    sc.add_argument('--efficiency', gooey_options={'label':"Efficiency"}, widget="DecimalField", help="skychop efficiency fraction",default=0.5)
    sc.add_argument('--frequency', gooey_options={'label':"Chopper frequency"}, widget="DecimalField", help="skychop chopper frequency in Hz",default=1)
    sc.add_argument('--scan-name-offset', gooey_options={'label':"Scan number offset"}, widget="IntegerField", help="Offset the scan number used for the file name",default=0)

    bs = sp.add_parser("Biasstep", help="run bias steps")
    bs.add_argument('--step-size', gooey_options={'label':"Step size"}, widget="IntegerField", help="bias step depth in DAC units",default = 20)
    bs.add_argument('--bs-duration', gooey_options={'label':"Duration"}, widget="IntegerField", help="duration of bias step data",default=10)

    gt = sp.add_parser("Grating", help="control Grating")

    gt.add_argument('--index', widget="IntegerField", help="grating index to go to",gooey_options={
        'initial_value': gi,
        'min': 1, 
        'max': 3000, 
        'label':"Index", 
        'increment': 1  
    })

    auto = sp.add_parser("Autosetup", help="Run an Auto Setup")
    autoopt=auto.add_mutually_exclusive_group()
    autoopt.add_argument("--Only-Auto-Setup", gooey_options={'label':"Auto setup only"}, help="Perform just an autosetup, nothing else",action="store_true")
    autoopt.add_argument("--Crash-Reset", gooey_options={'label':"MCE Crash Reset"}, help="Whether to also perform an MCE crash reset.",action="store_true")
    autoopt.add_argument("--Firmware-Reset", gooey_options={'label':"MCE Firmware Reset"}, help="Whether to also perform an MCE firmware reset (needed only on first boot of the MCE)",action="store_true")
    
    args = parser.parse_args()

    print(args)

#     if args.sp=="Grating":
#         print(f"sending grating to {args.index}")
#         s.sendto(f"APEX:ZEUS2BE:GratingIndex {args.index}".encode(), addr)
#         s.sendto("APEX:ZEUS2BE:GratingGo".encode(), addr)
#         time.sleep(2)
#     elif args.sp=="Skychop":
#         synctime = int(1/float(args.frequency)/2*1e6)
#         blanktime = int(synctime*float(args.efficiency))
#         s.sendto(f"""APEX:ZEUS2BE:cmdIntegrationTime {int(args.duration)*10}
# APEX:ZEUS2BE:cmdBlankTime {blanktime}
# APEX:ZEUS2BE:cmdSyncTime {synctime}
# APEX:ZEUS2BE:cmdMode EXTERNAL
# APEX:ZEUS2BE:cmdNumPhases 2
# APEX:ZEUS2BE:cmdUsedSections 1
# APEX:ZEUS2BE:BAND1:cmdBandWidth 160000.0
# APEX:ZEUS2BE:BAND1:cmdNumSpecChan 1
# APEX:ZEUS2BE:usechopper 1
# APEX:ZEUS2BE:scan_offset {args.scan_name_offset}
# APEX:ZEUS2BE:configure""".encode(), addr)
#         time.sleep(2)
#         s.sendto("APEX:ZEUS2BE:start".encode(), addr)
#         time.sleep(int(args.duration)+2)
#         s.sendto("""APEX:ZEUS2BE:usechopper 0
# APEX:ZEUS2BE:scan_offset 0""".encode(), addr)
#     elif args.sp == "Autosetup":
#         s.sendto("APEX:ZEUS2BE:auto_setup".encode(), addr)

if __name__=="__main__":

    main()