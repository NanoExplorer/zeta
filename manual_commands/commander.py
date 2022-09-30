from gooey import Gooey, GooeyParser
import socket
import time

@Gooey(program_name="Zeus-2 Commands",
       show_sidebar=True,advanced=True)#,return_to_config=True)
def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    addr = ("10.0.2.143", 16255)
    s.sendto("APEX:ZEUS2BE:GratingIndex?".encode(), addr)
    data,_=s.recvfrom(1024)

    print(data)
    gi = int(data.decode().split(" ")[1])
    
    parser = GooeyParser(description="Zeus-2 Commands")
    sp = parser.add_subparsers(help="idk",dest="sp")
    sc=sp.add_parser("Skychop",help="run skychops")

    sc.add_argument('--duration', widget="IntegerField", help="skychop duration in seconds",default=6)
    sc.add_argument('--efficiency', widget="DecimalField", help="skychop efficiency fraction",default=0.5)
    sc.add_argument('--frequency', widget="DecimalField", help="skychop chopper frequency in Hz",default=0.5)

    bs = sp.add_parser("Biasstep",help="run bias steps")
    bs.add_argument('--step-size', widget="IntegerField", help="bias step depth in DAC units",default = 20)
    bs.add_argument('--bs-duration',widget="IntegerField", help="duration of bias step data",default=10)

    gt = sp.add_parser("Grating",help="control Grating")
    gt.add_argument('--index',widget="IntegerField",help="grating index to go to",default=gi)

    args = parser.parse_args()
    print(args)
    if args.sp=="Grating":
        print(f"sending grating to {args.index}")
        s.sendto("APEX:ZEUS2BE:GratingIndex {args.index}".encode(), addr)
        s.sendto("APEX:ZEUS2BE:GratingGo".encode(), addr)
    elif args.sp=="Skychop":
        synctime = int(1/args.frequency/2*1e6)
        blanktime = int(synctime*(1/args.efficiency))
        s.sendto(f"""APEX:ZEUS2BE:cmdIntegrationTime {args.duration*10}
APEX:ZEUS2BE:cmdBlankTime {blanktime}
APEX:ZEUS2BE:cmdSyncTime {synctime}
APEX:ZEUS2BE:cmdMode EXTERNAL
APEX:ZEUS2BE:cmdNumPhases 2
APEX:ZEUS2BE:cmdUsedSections 1
APEX:ZEUS2BE:BAND1:cmdBandWidth 160000.0
APEX:ZEUS2BE:BAND1:cmdNumSpecChan 1
APEX:ZEUS2BE:usechopper 1
APEX:ZEUS2BE:configure""")
        time.sleep(2)
        s.sendto("APEX:ZEUS2BE:start")
        time.sleep(args.duration+2)


if __name__=="__main__":
    main()