# zeta
ZEUS-2 Control and Data Interface for APEX

## APECS control of ZEUS-2
The program defined in `main.py` initializes all of the ZEUS-2 hardware and then opens a UDP 
listener to catch any commands sent by APECS. It supports many of the core APECS commands
but not all yet. 

In addition, it has several custom commands that are necessary but not supported by APECS. These
commands can be sent to the instrument using the script `commander.py` in the manual_commands directory.

### File naming
All files are now named according to the scan number in the APEX observing log. Data collected on-sky
with the APEX wobbler will be recorded into files `apecs_nnnnn_mmmm` where n=APEX scan number and m=subscan no.
Data collected with the chopper wheel will be called `skychop_nnnnn_mmmm`. The script `commander.py` 
also allows you to increment the APEX scan number by one when performing skychop calibration before
a scan.

## Data upload to APECS
The `apecs_server.py` program will listen for connections from the APECS FitsWriter. Once it has received
a connection, it will open up the data file that is currently being written and begin uploading 
partially-reduced data to APECS. The data reduction can handle atmospheric noise and detector temperature
instabalities, and is very fast, eliminating complications from time-out errors.

## Real-Time Data Inspection
The script `plot_most_recent_file.py` will open an interactive plot that will automatically update
to depict data from the most recent subscan. You can click on pixels in the 2-d array map screen
in order to plot their time series in the bottom panel.

## Synchronous data acquisition
All data is taken using the MCE Sync Box and Meinberg Clock Card. This means we always have time-stamps
for each data frame. This also includes "total power" or "stare" data that is taken without chopping or
wobbling. 

## Future Plans
It should now be possible to integrate a grating calibration algorithm into the control software directly.
This will allow us not only to tune the grating by simply specifying the wavelength needed, but also to 
accept wavelength tuning commands from APECS in the near future.

Hopefully we can also further automate the rebiasing procedure so that we can bias totally automatically
when APECS asks us to "tune" our system. 

We will work with the APEX team to implement these features and achieve much better integration.
