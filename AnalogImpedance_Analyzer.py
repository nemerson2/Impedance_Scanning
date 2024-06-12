"""
   DWF Python Example
   Author:  Digilent, Inc.
   Revision:  2018-07-28

   Requires:                       
       Python 2.7, 3
"""

from ctypes import *
from dwfconstants import *
import math
import time
import sys
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

if sys.platform.startswith("win"):
    dwf = cdll.LoadLibrary("dwf.dll")
elif sys.platform.startswith("darwin"):
    dwf = cdll.LoadLibrary("/Library/Frameworks/dwf.framework/dwf")
else:
    dwf = cdll.LoadLibrary("libdwf.so")

version = create_string_buffer(16)
dwf.FDwfGetVersion(version)
print("DWF Version: "+str(version.value))

hdwf = c_int()
szerr = create_string_buffer(512) #initializae error buffer
print("Opening first device")
dwf.FDwfDeviceOpen(c_int(-1), byref(hdwf)) #connect to waveforms/discovery

#error handling for no device connection
if hdwf.value == hdwfNone.value:
    dwf.FDwfGetLastErrorMsg(szerr)
    print(str(szerr.value))
    print("failed to open device")
    quit()

# this option will enable dynamic adjustment of analog out settings like: frequency, amplitude...
dwf.FDwfDeviceAutoConfigureSet(hdwf, c_int(3)) 

# settings
sts = c_byte()
steps = 150 #steps between frequencies
start = 200000 #start frequency
stop = 300000 #stop frequency
voltage = 5 #stimulus signal amplitude
reference = 1e3 #resistor value in Ohms (want to match to impedance values)

print("Reference: "+str(reference)+" Ohm  Frequency: "+str(start)+" Hz ... "+str(stop/1e3)+" kHz for nanofarad capacitors")
dwf.FDwfAnalogImpedanceReset(hdwf)
dwf.FDwfAnalogImpedanceModeSet(hdwf, c_int(8)) # 0 = W1-C1-DUT-C2-R-GND, 1 = W1-C1-R-C2-DUT-GND, 8 = AD IA adapter, should always use 8 unless you're using custom circuitry
dwf.FDwfAnalogImpedanceReferenceSet(hdwf, c_double(reference)) # reference resistor value in Ohms
dwf.FDwfAnalogImpedanceFrequencySet(hdwf, c_double(start)) # frequency in Hertz
dwf.FDwfAnalogImpedanceAmplitudeSet(hdwf, c_double(voltage)) # 1V amplitude = 2V peak2peak signal
dwf.FDwfAnalogImpedanceConfigure(hdwf, c_int(1)) # start
time.sleep(2)


def impedance_scan(steps, stop, start, hdwf, sts, szerr):
    
    #initialize lists for storing raw data
    rgHz = [0.0]*steps #freq
    rgRs = [0.0]*steps #resistance
    rgXs = [0.0]*steps #reactance
    Z = [0.0]*steps #impedance
    theta = [0.0]*steps #impedance angle

    #initialize impedance vs Hz plot
    x = range(0,steps)
    y = [0]*steps
    plt.ion()
    fig = plt.figure(1)
    ax = fig.add_subplot(111)
    ax.set_xlim(start,stop)
    ax.set_ylim(0,50000)
    # ax.autoscale()
    ax.set_xlabel('freq (Hz)')
    ax.set_ylabel('impedance (z)')
    # plt.plot(rgHz, rgRs, rgHz, rgXs, rgHz, Z)
    # ax = plt.gca()
    # ax.set_xscale('log')
    # ax.set_yscale('log')
    ax.legend(['Rs','Xs', 'Z'])
    mgr1 = plt.get_current_fig_manager()
    line, = ax.plot(rgHz, Z)

    while True:
        for i in range(steps):
            hz = stop * pow(10.0, 1.0*(1.0*i/(steps-1)-1)*math.log10(stop/start)) # exponential frequency steps
            # print("Step: "+str(i)+" "+str(hz)+"Hz")
            rgHz[i] = hz
            dwf.FDwfAnalogImpedanceFrequencySet(hdwf, c_double(hz)) # frequency in Hertz
            # if settle time is required for the DUT, wait and restart the acquisition
            # time.sleep(0.01) 
            # dwf.FDwfAnalogInConfigure(hdwf, c_int(1), c_int(1))
            while True:
                if dwf.FDwfAnalogImpedanceStatus(hdwf, byref(sts)) == 0:
                    dwf.FDwfGetLastErrorMsg(szerr)
                    print(str(szerr.value))
                    quit()
                if sts.value == 2:
                    break
            resistance = c_double()
            reactance = c_double()
            dwf.FDwfAnalogImpedanceStatusMeasure(hdwf, DwfAnalogImpedanceResistance, byref(resistance))
            dwf.FDwfAnalogImpedanceStatusMeasure(hdwf, DwfAnalogImpedanceReactance, byref(reactance))
            rgRs[i] = abs(resistance.value) # absolute resistance value for logarithmic plot
            rgXs[i] = abs(reactance.value) # absolute reactance value for logarthmic plot
            Z[i] = abs(math.sqrt(rgRs[i]**2+rgXs[i]**2))
            theta[i] = math.atan(rgXs[i]/rgRs[i])

            #add impedance data to plot

            
            for iCh in range(2):
                warn = c_int()
                dwf.FDwfAnalogImpedanceStatusWarning(hdwf, c_int(iCh), byref(warn))
                if warn.value:
                    dOff = c_double()
                    dRng = c_double()
                    dwf.FDwfAnalogInChannelOffsetGet(hdwf, c_int(iCh), byref(dOff))
                    dwf.FDwfAnalogInChannelRangeGet(hdwf, c_int(iCh), byref(dRng))
                    if warn.value & 1:
                        print("Out of range on Channel "+str(iCh+1)+" <= "+str(dOff.value - dRng.value/2)+"V")
                    if warn.value & 2:
                        print("Out of range on Channel "+str(iCh+1)+" >= "+str(dOff.value + dRng.value/2)+"V")

        # dwf.FDwfAnalogImpedanceConfigure(hdwf, c_int(0)) # stop
        # dwf.FDwfDeviceClose(hdwf)


            
        df = pd.DataFrame({'Hz':rgHz, 'Rs':rgRs, 'Xs':rgXs, 'Z':Z, 'theta':theta})
        df.to_csv("test.csv", mode='a')

        line.set_ydata(Z)
        line.set_xdata(rgHz)
        fig.canvas.draw()
        fig.canvas.flush_events()

        
        # max_Z = np.max(np.array(Z))
        # print(max_Z)
        # max_idx = np.where(np.array(Z) == max_Z)
        # # print(rgHz[max_idx[0][0]])
        # op_freq = rgHz[max_idx[0][0]]

if __name__=="__main__":
    impedance_scan(steps, stop, start, hdwf, sts, szerr)