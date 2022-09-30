from mce_control import mce_control

def compute_paramters_from_apecs(integrationtime,
                                 blanktime,
                                 synctime):
    int_time_us = integrationtime*1000
    mce = mce_control()
    # internal_frame_rate = mce.mux_rate() # Hz
    readout_rate = mce.readout_rate() # Hz
    chop_duration = blanktime+synctime # us, duration of one chop phase
    num_phases = int_time_us / chop_duration
    on_time = num_phases * synctime
    frames = on_time * 1e6 * readout_rate

    frames_per_phase = synctime * 1e6 * readout_rate

    return frames, frames_per_phase, readout_rate



