from glob import glob
import os
import zeustools as zt
import numpy as np
import matplotlib.pyplot as plt

def get_recent_file():
    path = "/data/cryo/current_data/" 
    files = glob(path + "*.run")
    modtimes = [os.path.getmtime(file) for file in files]
    most_recent_modtime = max(modtimes)
    file = modtimes.index(most_recent_modtime)
    return files[file].replace(".run","")


if __name__ == "__main__":
    am = zt.ArrayMapper()
    last_iplot = None
    f=""
    while True:
        x = get_recent_file()
        if x==f:
            #print("sleeping")
            plt.gcf().canvas.draw_idle()
            plt.gcf().canvas.start_event_loop(5)
            continue
        try:
            mce = zt.mce_data.SmallMCEFile(x)

        except:
            plt.gcf().canvas.draw_idle()
            plt.gcf().canvas.start_event_loop(5)
            continue
        nframes = int(mce.runfile.data["FRAMEACQ"]["DATA_FRAMECOUNT"].strip())
        if mce.Read(row_col=True).data.shape[2]<nframes-1:
            plt.gcf().canvas.draw_idle()
            plt.gcf().canvas.start_event_loop(5)
            continue
        else:
            f = x
            print(f"reading {f}")

        if "bias_step" in f:
            iplot = zt.bs_interactive_plotter_factory(mce,didi=True)
        elif "iv" in f:
            iplot = zt.iv_tools.InteractiveIVPlotter(f)
        else:
            mcedata = mce.Read(row_col=True)
            cube = mcedata.data
            chop = mcedata.chop
            cube = np.ma.array(cube)
            ts = np.genfromtxt(x+".ts")[:,1]
            try:

                chops = zt.numba_reduction.offset_data_reduction(chop,cube)
                det_array = np.median(chops, axis=2)
                print("chopped")
            except Exception as e:
                print(e)
                det_array = np.std(cube, axis=2)
            
            print(cube[am.phys_to_mce(30,0,400)])
            cube[:,:,chop==1] = zt.nd_reject_outliers(cube[:,:,chop==1],MAD_chop=10)
            cube[:,:,chop==0] = zt.nd_reject_outliers(cube[:,:,chop==0],MAD_chop=10)
            print(cube[am.phys_to_mce(30,0,400)])
            cube.fill_value=np.nan
            iplot = zt.plotting.ZeusInteractivePlotter(det_array,cube,ts=ts)
        if last_iplot is not None:
            #print(np.ma.array(det_array))
            # iplot.data = np.ma.array(det_array)
            # iplot.cube = cube
            # iplot.ts=np.arange(cube.shape[2])
            last_iplot.ax2.clear()
            last_iplot.ax.clear()
            last_iplot.cb.remove()
            # iplot.redraw_top_plot()
            # iplot.bottom_plot()
            #print(iplot.data)
            iplot.fig = last_iplot.fig
            iplot.ax = last_iplot.ax
            iplot.ax2 = last_iplot.ax2
            iplot.click_loc=last_iplot.click_loc
            iplot.markersize = 45
            iplot.linewidth=0.5
            iplot.interactive_plot()
            iplot.bottom_plot()
            last_iplot = iplot
            print(iplot.check_for_errors())
        else:
            last_iplot = iplot
            last_iplot.debug=True
            last_iplot.figsize = (6,6)
            last_iplot.markersize = 45
            iplot.linewidth=0.5
            last_iplot.interactive_plot()
            plt.ion()

            last_iplot.fig.show()



    

