// frametimes.c  time capture with arguments from zeus2 ops
//
// see showuse
// see capt.c for other functionality available
//
#define PROG_VERSION "2.1" 
// v 2.1: multiple files per mce_run --sequence
// v 1.8: removing ->n chop index for numpy.loadtxt()
// v 1.6: removing optional modes, don't need -c, as constant is the only mode
//
// v 1.4: getting and writing timestamps as fractional seconds since epoch
//
// v 1.1: adding oswarn
//
// v 1.2: adding 'ok' to stdout when ready and waiting for timestamps
//
// Here, get timestamp info into PCPS_HR_TIME structure list.
//
// typedef struct
// {
//   PCPS_TIME_STAMP tstamp = utin32_t sec, frac;
//   int32_t utc_offs;
//   PCPS_TIME_STATUS_X status;  // = uint16_t  extended status flags
//   uint8_t signal;             // for ucap, the channel number
// } PCPS_HR_TIME;

/* ****************************************
//  Local/MbgMon/mbgmon.exe + help
//  Local/MbgSdk/mbgsdk.chm = help
//  Local/MbgSdk/c/demo/mbgdevio/mbgdevio_demo.c
// ****************************************
 TCR167PCI IRIG Synchronized PCI Slot Card
 S/N 027911003930 <- from packing slip

   From MbgSdk/c/demo/mbgdevio/mbgdevio_demo.c :

When using the time capture inputs:

- The corresponding DIP switches on the card must be set to the "ON" position
in order to wire the input pins to the capture circuitry. See the user manual
for the correct DIP switches. 

js ed. This is for DB9 configuration, 
        not for time captures cap0, cap1 which are on the strip.

- Capture events are stored in the on-board FIFO, and entries can be retrieved
from the FIFO in different ways. Once an entry has been retrieved it is removed
from the FIFO, so if several ways or applications are used at the same time
to retrieve capture events from the FIFO then capture events may be missed by
one application since they have already been retrieved by another application. 

- The card provides 2 physical serial interfaces either of which may have been
configured to send a serial ASCII string automatically whenever a capture
event has occurred. Of course this would also remove those capture events
from the FIFO buffer. So the settings of both serial ports should be checked
to make sure none of the serial ports have been configured to send the capture
string automatically. This has to be done only once for a card since
the setting is saved in non-volatile memory. 
* ******************************************* 
     from tcr167pci.pdf
Contact strip provides four (4) TTL inputs.
CAP0 and CAP1 can be used to capture asynchronous time events, timestamps
 readable via PCI-bus (or serial interface).
Other two TTL inputs can be read via PCI-bus.

                              bnc   bnc
       serial                 __     __
        ____                 |  |   |  |
  _____|    |________________|  |___|  |___|_
|   |          |            |    | |    |   |
|   |          |            |out | | in |   |
|    ----------              ----   ----    |
|                                           |
|                 o GND                     |
| capture input 1 o CAP1                    |
| capture input 0 o CAP0                    |
|gen purp input 0 o GP0                     |
|gen purp input 1 o GP1                     |
|                 o GND                     |
|                                           |
     capture string: 
 
      CHx_tt.mm.jj_hh:mm:ss.fffffff<CR><LF> << assume German tt=day? jj=year?
      CHx_dd.mm.yy_hh:mm:ss.fffffff<CR><LF>

        x = 0|1 = CAP0|CAP1
        _ == ' '
        dd = 01..31
        mm = 01..12
        yy = 00..99
        hh = 00..23
        mm = 00..59
        ss = 00..59 or 60 while leap second
        fffffff = sec fraction (7 digits)

 access: mbg_get_ucap_entries() used, max
         mbg_get_ucap_event()   tstamp, channel, etc.
         mbg_clr_ucap_buff()    clear

* ********* */
// INCLUDE += d:/Local/MbgSdk/c/mbglib/include
// LIBS = d:/Local/MbgSdk/c/mbglib/lib/msc/mbgdevio.lib,mbgutil.lib

#include <mbgdevio.h>
#include <pcpsutil.h>
// #include <toolutil.h>
 
#include <time.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/time.h> // gettimeofday()
#include <math.h>

/** Number of memory mapped time reads */
#define MAX_MEM_MAPPED_CNT 20 
#define MAX_CAPT_LIST 680

#define CHANNEL 0  // there are two (2) capture input channels on board,
             // zues2 uses channel 0 from the MCE SyncBox
        // Detection of triggers on other channel are commented in file output.

// input arguments
char outfilespec[200]; // Output MCE pixel file spec + ".ts", for timestamps
char datafilespec[200]; // program arg
int  seqindex;
int NFramestotal;
int NFramesperpos;
int NFramesperfile;
PCPS_HR_TIME TShrtimes[682]; // max card list is 680
MBG_DEV_HANDLE MBGdh;

int constantly; // legacy use, now the only mode

char DeviceInfoString[80];
char DriverInfoString[80];
char ebuf[256];

static int n_sec_change = 0;
int BufOFFSET = 0;

// stats
int events_usec[MAX_CAPT_LIST];
int events_count;
double events_avrg_usec;
double events_dusec[MAX_CAPT_LIST];
double events_stdev_usec;
double events_freq;

#define MAX_GET_TIMES 256

// protos
// int writeTSfile(char *outfilespec, int nf, int nfperpos,\
//                  int ntimestamps, PCPS_HR_TIME *hrtimes);
int getTSconstantly(void);
// int getTSallatonce(void);
void oswarn(int nsec, char *msg);
int oswarned;

////////////////////
// error handling
static /*HDR*/
void err_msg( const char *msg )
{
  // fprintf( stderr, "** %s: %i\n", msg, GetLastError() );
  sprintf(ebuf, "** %s\n", msg);
  fputs(ebuf, stderr);
  oswarn(0, ebuf);
}  // err_msg

static /*HDR*/
void sprint_drvr_info(char *sout) // used only on device open error
{
  int rc;
  PCPS_DRVR_INFO drvr_info;
  MBGdh = mbg_open_device( 0 );
  
  if ( MBGdh == MBG_INVALID_DEV_HANDLE )
  {
    err_msg( "FT:open irig dev" );
    exit( 1 );
  }

  rc = mbg_get_drvr_info(MBGdh, &drvr_info );

  mbg_close_device( &MBGdh );

  if ( rc != PCPS_SUCCESS )
  {
    err_msg( "FT:read drvr info" );
    exit( 1 );
  }

  sprintf(sout,  "Kernel driver: %s v%i.%02i",
          drvr_info.id_str,
          drvr_info.ver_num / 100,
          drvr_info.ver_num % 100
        );

}  // print_drvr_info

static /*HDR*/
char *sprint_hr_time( char *s, const PCPS_HR_TIME *t )
{
  const char *cp = "UTC";
  
  if ( t->status & PCPS_SCALE_TAI )
    cp = "TAI";
  else
    if ( t->status & PCPS_SCALE_GPS )
      cp = "GPS";

  sprintf( s, "%08lX.%08lX %s%+ld sec, status: %04Xh  RF sig: %d", 
           (long)t->tstamp.sec,    // 
           (long)t->tstamp.frac,   // sec and frac is everything in tstamp
           cp,
           (long)t->utc_offs,
           t->status,
           t->signal  // relative RF signal level
         );

  return s;

}  // sprint_hr_time

// THIS IS USED TO PRINT FRAME-START-PULSE-CAPTURE TIMESTAMP FILE
// floating point seconds since epoch
static /*HDR*/
char *sprint_hr_cap_time( char *s, const PCPS_HR_TIME *t )
{
  time_t timet;
  double fract, totsec;
  // integer seconds since epoch
  timet = t->tstamp.sec;
  // fractional second since timet
  fract = (double)t->tstamp.frac / (double)0xffffffff;
  // total
  totsec = (double)timet + fract;
  // ascii
  sprintf(s, "%14.4f", totsec);
  return s;
}  // sprint_hr_time

//////////////////////////////////////////////////////////////////////////
// return count of captures presently in card
// return -1 error
int capturecount(void)
{
  int ret = 0;
  PCPS_UCAP_ENTRIES ents;
  
  if (MBG_SUCCESS != mbg_get_ucap_entries(MBGdh, &ents))
  {
    puts("GETTIMES FAILURE: mbg_get_ucap_entries()");
    ret = -1;
  }
  return ents.used;
}

//////////////////////////////////////////////////////////////////////////
// store capture info into list of hrtimes
int get_n_captures(int ncapts, PCPS_HR_TIME *hrtimes)
{
  int i;

  for (i=0; i<ncapts; i++)
  {
    //  retrieve an event from the list
    if (MBG_SUCCESS != mbg_get_ucap_event(MBGdh, &hrtimes[i])) 
    { // hrtimes[i].xxx = error-indicator... <<<<<<<<<<<<<<<<<<<< implement?
      printf("GETTIMES FAILURE: mbg_get_ucap_event(),  ts %d of %d\n",
                                                               i+1, ncapts);
      return -1;
    }
  }
  return 0;
}

void oswarn(int tosec, char *msg)
{
   int ret;
   char *ptr, buf[320];
   oswarned = 1;
   puts(msg);
   ptr = msg;
   while (*ptr)
   {
     if (*ptr == ' ') *ptr = '_';
     ptr++;
   }
   sprintf(buf, "oswarn r FRAME-TIMES %d.0 \"%s\"\n", tosec, msg);
   ret = system(buf);
   if (ret)
     printf("FRAME-TIMES system() returned=%d, calling: %s\n", ret, buf);
}

/**
  There are 3 functions to deal with the capture events:

  mbg_clr_ucap_buff() clears the on-board FIFO buffer
  mbg_get_ucap_entries() returns the maximum number of entries
    and the currently saved number of entries in the buffer
  mbg_get_ucap_event() retrieves a capture event from the
    on-board FIFO, or 0000.0000 if the FIFO buffer is empty.
*/

void showuse(char *cmd)
{
 printf("use: %s datafile nf nfperblank [nfperfile]\n", cmd);
   puts("   to write datafile.ts timestamp file");
   puts(" datafile    full path to MCE pixel-data file, current acquisition");
   puts(" nf          total number of frames in current acquisition");
   puts(" nfperblank  frames per chop position");
   puts(" [nfperfile  frames per file]");
 printf("                                                           v %s\n", 
                                                             PROG_VERSION);
}

int main( int argc, char* argv[] )
{
  int i, nc, count, prenc, nframes;
  int ndevices, ret;
  char buf[256];
  
  int argx = 1;
  if (argc < 4)
  { showuse(argv[0]);
    return 1;
  }

 
  if (argv[argx][0] == '-')
  { char *ptr = &argv[argx++][1];
    while (*ptr)
    {
      switch (*ptr++)
      {
        case 'c' : constantly = 1; // legacy support, this is the only mode
        default  : break;
      }
    }
  }

  // THIS IS NEC... fflush(stdout) DIDNT WORK, 
  // for (i=0; i<1000; i++) puts("ok"); DIDNT WORK
  // fflush(NULL) DIDNT WORK
  setbuf(stdout, NULL); // disable buffering

  // sprintf(TSOutfilespec, "%s.ts", argv[argx++]);
  strcpy(datafilespec, argv[argx++]);
  NFramestotal = atoi(argv[argx++]);
  NFramesperpos = atoi(argv[argx++]);
  if (argc > argx)
    NFramesperfile = atoi(argv[argx++]);

  if (NFramesperfile == NFramestotal)
    NFramesperfile = 0;

  // DONT PRINT ANYTHING UNTIL 'ok\n' in constant-readout-mode
  //
  // TODO: change all to stderr and reserve stdout for 'ok' status (?)
  
  
  if (PCPS_SUCCESS != mbgdevio_check_version(MBGDEVIO_VERSION))
  {
    printf("The installed MBGDEVIO DLL API version %X\n"
           "is not compatible with API version %X required by this program.\n",
           mbgdevio_get_version(),
           MBGDEVIO_VERSION);
    exit(1);
  }

  ndevices = mbg_find_devices();

  if ( ndevices == 0 )
  {
    printf( "No radio clock found.\n" );
    return 1;
  }
  /////
  MBGdh = mbg_open_device(0); // ASSUMES ONE (1) MEINBERG DEVICE!
    
  if (MBG_INVALID_DEV_HANDLE == MBGdh)
  { err_msg( "FT:open irig dev" );
    sprint_drvr_info(DriverInfoString);
    return 1;
  }

  ////////////////////////////////////////////////////////////////////////
  mbg_clr_ucap_buff(MBGdh);         // clear the IRIG on-board FIFO buffer
  ////////////////////////////////////////////////////////////////////////
  BufOFFSET = 0;
  ret = capturecount();
  if (0 != ret)
  { 
    mbg_clr_ucap_buff(MBGdh);         // clear the IRIG on-board FIFO buffer
    ret = capturecount();
    if (0 != ret)
    {
      // printf("ZFRAMETIMES WARNING: time count = %d after clearing twice\n", ret);
      // printf("ZFRAMETIMES attempting to work around...\n", ret);
      BufOFFSET = ret;
    }
  }

  ret = getTSconstantly();

  // DONE
mainerr:
  mbg_close_device( &MBGdh );   
  return ret;
}

// int writeTSfile(char *outfilespec, int nf, int nfperpos, int nhrtimes, PCPS_HR_TIME *hrtimes)
// {
//   int i, pmi, chopcycle;
//   char pm, buf[128];
//   printf("OPENING %s\n", outfilespec);
//   FILE *outf = fopen(outfilespec, "w");
//   if (NULL == outf)
//   {
//     printf("GETTIMES FAILURE: can't open %s for writing\n", outfilespec);
//     return -1;
//   }
// 
//   printf("writing...\n");
//   fprintf(outf, "# Timestamps file: %s\n", outfilespec);
//   fprintf(outf, "## %d dataframes\n", nf);
//   fprintf(outf, "## %d fperchoppos\n", nfperpos);
//   fprintf(outf, "## %d ts\n", nhrtimes);
//   printf("wrote...\n");
//   fflush(outf);
// 
//   pm = '+';
//   pmi = 1;
//   chopcycle = 0;
//   for (i=0; i<nhrtimes; i++)
//   {
//      if (!((i+1)%nfperpos))
//      { pmi = pmi ? 0 : 1;
//        pm = pmi ? '+' : '-';
//        if (!pmi) 
//          chopcycle++;
//        printf("-------- chop cycle %d %c\n", chopcycle, pm);
//      }
//      sprint_hr_cap_time(buf, &hrtimes[i]);
//      fprintf(outf, "%3d  %s\n", i, buf);
//   }
//   fclose(outf);
//   return 0;
// }
// 
// int getTSallatonce(void)
// {
//   int i, prenc, nc = 0;
//   int count = 0;
//   int nframes = NFramestotal;
// 
//   printf("ok\n");
// 
//   if (nframes > 680) // max in buffer
//     nframes = 680;
//   while (nc < nframes && count++ < 100)
//   {  prenc = nc;
//      nc = capturecount();
//      if (nc > prenc)
//        for (i=0; i<(nc-prenc); i++)
//          printf(".");
//      usleep(100000);
//   }
//   if (!nc)
//   { sprintf(ebuf, "ERROR with timestamps: no events after 10 sec\n");
//     puts(ebuf);
//     oswarn(0, ebuf);
//     return -1;
//   }
//   printf("\n");
// 
//   if (get_n_captures(nc, TShrtimes))
//   { 
//     printf("GETTIMES FAILURE: get_n_captures(, nc=%d, ...)\n", nc);
//     return  -1;  // NO, write error info to normal output file... <<<<<<<<<<<<<<<<<<
//   }
//   writeTSfile(TSOutfilespec, nframes, NFramesperpos, nc, TShrtimes);
//   return 0;
// }

int getTSconstantly(void)
{
  int i, nc;
  int ncmax = 0, nctot = 0;
  int zcount = 0, chophalves = 0;
  int nwrit = 0;
  char buf[128];
  FILE *outf;

  if (!NFramesperfile)
     sprintf(outfilespec, "%s.ts", datafilespec);
  else
     sprintf(outfilespec, "%s.%03d.ts", datafilespec, seqindex);

  outf = fopen(outfilespec, "w");
  if (NULL == outf)
  {  printf("Timestamps: can't open %s for writing!\n", outfilespec);
     return -1;
  }
  fprintf(outf, "# this timestamps file: %s\n", outfilespec);
  fprintf(outf, "## dataframes = %d  frames/choppos = %d   ", 
         NFramesperfile ? NFramesperfile : NFramestotal, NFramesperpos);
  // NOTE NO \n IN PREV FPRINTF... for continuation with TZOFFSET below

  printf("ok\n"); // signal on pipe
  while (nctot < NFramestotal)
  {  
     nc = capturecount();
     if (nc < 1)
     {
       usleep(10000); // 10 ms
       if (++zcount > 400) // 4 sec
       { 
         goto zfwarning;
       }
       continue;
     }
     zcount = 0;  // reset
     if (nc > ncmax) ncmax = nc;
     ///////////////////////////////////////////////////////////////////////////
     if (get_n_captures(nc, TShrtimes)) // get timestamps from board FIFO
     { 
        sprintf(ebuf, "get_n_captures(, nc=%d, ...)\n", nc);
        puts(ebuf);
        oswarn(0, ebuf);
        return -1;  // NO, write error info to normal output file... <<<<<<<<<<
     }

     if (0 == nctot)
     {
        fprintf(outf, "TZOFFSET = %dm   STATBITS = %04x\n",
                             TShrtimes[0].utc_offs, TShrtimes[0].status);
     }

     ///////////////////////////////////////////////////////////////////////////
     for (i=0; i<nc; i++)                      // write to file
     {
        sprint_hr_cap_time(buf, &TShrtimes[i]);
        nctot++;
        // if (!((nctot++)%NFramesperpos))
        // {
        //   chophalves++; // for appending in output string, 
        //                //  also phase per allatonce (if allatonce is even used)
        //   fprintf(outf, "%4d  %s  ->%d\n", nwrit++, buf, chophalves);
        // }
        // else fprintf(outf, "%4d  %s\n", nwrit++, buf);
        fprintf(outf, "%4d  %s\n", nwrit++, buf);
        if (NFramesperfile && (!(nctot % NFramesperfile)) && nctot<NFramestotal)
        {
           fclose(outf);
           sprintf(outfilespec, "%s.%03d.ts", datafilespec, ++seqindex);
           outf = fopen(outfilespec, "w");
           if (NULL == outf)
           {  printf("Timestamps: can't open %s for writing!\n",outfilespec);
              return -1;
           }
           fprintf(outf, "# this timestamps file: %s\n", outfilespec);
           fprintf(outf, "## dataframes = %d  frames/choppos = %d\n", 
                                      NFramesperfile , NFramesperpos);
        }
     }
  }
zfwarning:
  // fprintf(outf, "# max ts fifo fill: %d of 680\n", ncmax);
  // fprintf(outf, "#      chop halves: %d\n", chophalves);
  fclose(outf);
//fprintf(stderr, "*************** ZFRAMETIMES closed %s with %d timestamps\n",
//                                          TSOutfilespec, nwrit);
  if (nctot < NFramestotal)
  {
   sprintf(ebuf, "NFrames expected = %d, got %d  (?)\n",
                                     NFramestotal, nctot);
   puts(ebuf);
   // oswarn(0, ebuf);
  }
  return 0;  // oswarned;
}
//      #define'd in /usr/local/include/mbglib/pcpsdefs.h
// Bit masks used with both PCPS_TIME_STATUS and PCPS_TIME_STATUS_X
// PCPS_FREER     0x01  // DCF77 clock running on xtal */
                             // GPS receiver has not verified its position */
// PCPS_DL_ENB    0x02  // daylight saving enabled */
// PCPS_SYNCD     0x04  // clock has sync'ed at least once after pwr up */
// PCPS_DL_ANN    0x08  // a change in daylight saving is announced */
// PCPS_UTC       0x10  // a special %UTC firmware is installed */
// PCPS_LS_ANN    0x20  // leap second announced */
                             // (requires firmware rev. REV_PCPS_LS_ANN_...) */
// PCPS_IFTM      0x40  // the current time was set via PC */
                             // (requires firmware rev. REV_PCPS_IFTM_...) */
// PCPS_INVT      0x80  // invalid time because battery was disconn'd */
// Bit masks used only with PCPS_TIME_STATUS_X
// PCPS_LS_ENB      0x0100  // current second is leap second */
// PCPS_ANT_FAIL    0x0200  // antenna failure */
// PCPS_LS_ANN_NEG  0x0400  // announced leap second is negative */
// PCPS_SCALE_GPS   0x0800  // time stamp is GPS scale */
// PCPS_SCALE_TAI   0x1000  // time stamp is TAI scale */
// Bit masks used only with time stamps representing user capture events
// PCPS_UCAP_OVERRUN      0x2000  // events interval too short */
// PCPS_UCAP_BUFFER_FULL  0x4000  // events read too slow */
// PCPS_SYNC_PZF          0x2000  // same code as PCPS_UCAP_OVERRUN */
// PCPS_IO_BLOCKED        0x8000
