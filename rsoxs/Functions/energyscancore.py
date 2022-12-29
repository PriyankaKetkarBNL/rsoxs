from cycler import cycler
from bluesky.utils import Msg, short_uid as _short_uid
import bluesky.utils as utils
from bluesky.plan_stubs import trigger_and_read
import bluesky.plans as bp
import bluesky.plan_stubs as bps
from bluesky.plan_stubs import (
    checkpoint,
    abs_set,
    sleep,
    trigger,
    read,
    wait,
    create,
    save,
)
from bluesky.preprocessors import rewindable_wrapper, finalize_wrapper
from bluesky.utils import short_uid, separate_devices, all_safe_rewind
from collections import defaultdict
from bluesky import preprocessors as bpp
from bluesky import FailedStatus
import numpy as np
from ophyd import Device
from ophyd.status import StatusTimeoutError
from copy import deepcopy
from ..HW.energy import (
    en,
    mono_en,
    epu_gap,
    grating_to_250,
    grating_to_rsoxs,
    grating_to_1200,
    set_polarization,
)
from ..HW.energy import (
    Mono_Scan_Speed_ev,
    Mono_Scan_Start,
    Mono_Scan_Start_ev,
    Mono_Scan_Stop,
    Mono_Scan_Stop_ev,
)
from ..HW.motors import (
    sam_X,
    sam_Y,
    sam_Z,
    sam_Th,
)
from sst_hw.mirrors import mir3
from ..HW.detectors import waxs_det, saxs_det
from ..HW.signals import DiodeRange,Beamstop_WAXS,Beamstop_SAXS,Izero_Mesh,Sample_TEY
from ..HW.lakeshore import tem_tempstage
from ..Functions.alignment import rotate_now
from ..Functions.common_procedures import set_exposure
from sst_hw.diode import (
    Shutter_open_time,
    Shutter_control,
    Shutter_enable,
    Shutter_trigger,
    shutter_open_set
)
from sst_funcs.printing import run_report


run_report(__file__)


SLEEP_FOR_SHUTTER = 1


def cleanup():
    # make sure the shutter is closed, and the scanlock if off after a scan, even if it errors out
    yield from bps.mv(en.scanlock, 0)
    yield from bps.mv(Shutter_control, 0)


def one_trigger_nd_step(detectors, step, pos_cache):
    """
    Inner loop of an N-dimensional step scan

    This is the default function for ``per_step`` param in ND plans.

    Parameters
    ----------
    detectors : iterable
        devices to read
    step : dict
        mapping motors to positions in this step
    pos_cache : dict
        mapping motors to their last-set positions
    """

    def move():
        yield from checkpoint()
        grp = short_uid("set")
        for motor, pos in step.items():
            if pos == pos_cache[motor]:
                # This step does not move this motor.
                continue
            yield from abs_set(motor, pos, group=grp)
            pos_cache[motor] = pos
        yield from wait(group=grp)

    motors = step.keys()
    yield from move()
    detectors = separate_devices(detectors)  # remove redundant entries
    rewindable = all_safe_rewind(detectors)  # if devices can be re-triggered
    detector_with_shutter, *other_detectors = detectors
    grp = short_uid("trigger")

    def inner_trigger_and_read():
        """
        This was copied with local changes from the body of
        bluesky.plan_stubs.trigger_and_read.
        """
        no_wait = True
        for obj in other_detectors:
            if hasattr(obj, "trigger"):
                no_wait = False
                yield from trigger(obj, group=grp)
        # Skip 'wait' if none of the devices implemented a trigger method.
        if not no_wait:
            yield from wait(group=grp)
        yield from create("primary")
        ret = {}  # collect and return readings to give plan access to them
        for obj in detectors:
            reading = yield from read(obj)
            if reading is not None:
                ret.update(reading)
        yield from save()
        return ret

    yield from trigger(detector_with_shutter, group=grp)
    yield from sleep(SLEEP_FOR_SHUTTER)
    return (yield from rewindable_wrapper(inner_trigger_and_read(), rewindable))


# @dark_frames_enable
def en_scan_core(
    signals=None,
    dets=None,
    energy=None,
    energies=None,
    times=None,
    enscan_type=None,
    lockscan = True,
    pol=0,
    temp=None,
    temp_wait=0, # negative no wait at all, anything positive is wait for ramp and this amount of minutes
    temp_ramp=10,
    grating="no change",
    master_plan=None,
    angle=None,
    sim_mode=False,
    n_exp=1,
    md=None,
    **kwargs #extraneous settings from higher level plans are ignored
):
    # grab locals
    if signals is None:
        signals = []
    if dets is None:
        dets = []
    if energies is None:
        energies = []
    if times is None:
        times = []
    if md is None:
        md = {}
    if energy is None:
        energy = en
    arguments = dict(locals())
    del arguments["md"]  # no recursion here!
    arguments["signals"] = [signal.name for signal in arguments["signals"]]
    arguments["energy"] = arguments["energy"].name
    if md is None:
        md = {}
    md.setdefault("plan_history", [])
    md["plan_history"].append({"plan_name": "en_scan_core", "arguments": arguments})
    md.update({"plan_name": enscan_type, "master_plan": master_plan,'plan_args' :arguments })
    # print the current sample information
    # sample()  # print the sample information  Removing this because RE will no longer be loaded with sample data
    # set the exposure times to be hinted for the detector which will be used

    # validate inputs
    valid = True
    validation = ""
    newdets = []
    detnames = []
    for det in dets:
        if not isinstance(det, Device):
            try:
                det_dev = globals()[det]
                newdets.append(det_dev)
                detnames.append(det_dev.name)
            except Exception:
                valid = False
                validation += f"detector {det} is not an ophyd device\n"
        else:
            newdets.append(det)
            detnames.append(det.name)
    if len(newdets) < 1:
        valid = False
        validation += "No detectors are given\n"
    if min(energies) < 70 or max(energies) > 2200:
        valid = False
        validation += "energy input is out of range for SST 1\n"
    if grating == "1200":
        if min(energies) < 150:
            valid = False
            validation += "energy is to low for the 1200 l/mm grating\n"
    elif grating == "250":
        if max(energies) > 1000:
            valid = False
            validation += "energy is too high for 250 l/mm grating\n"
    elif grating == "rsoxs":
        if max(energies) > 1000:
            valid = False
            validation += "energy is too high for 250 l/mm grating\n"
    else:
        valid = False
        validation += "invalid grating was chosen"
    if max(times) > 10:
        valid = False
        validation += "exposure times greater than 10 seconds are not valid\n"
    if pol < -1 or pol > 180:
        valid = False
        validation += f"polarization of {pol} is not valid\n"
    if not isinstance(energy, Device):
        valid = False
        validation += f"energy object {energy} is not a valid ophyd device\n"
    if angle is not None:
        if -155 > angle or angle > 195:
            valid = False
            validation += f"angle of {angle} is out of range\n"
    if temp is not None:
        if 0<temp<350:
            valid = False
            validation += f"temperature of {temp} is out of range\n"
        if temp_wait > 30:
            valid = False
            validation += f"temperature wait time of {temp_wait} minutes is too long\n"
        if 0.1 > temp_ramp or temp_ramp > 100:
            valid = False
            validation += f"temperature ramp speed of {temp_ramp} is not True/False\n"
    if 1000 < n_exp < 1:
        valid = False
        validation += f'number of exposures {n_exp} is unreasonable\n'
    if sim_mode:
        if valid:
            retstr = f"scanning {detnames} from {min(energies)} eV to {max(energies)} eV on the {grating} l/mm grating\n"
            retstr += f"    in {len(times)} steps with exposure times from {min(times)} to {max(times)} seconds\n"
            return retstr
        else:
            return validation

    if not valid:
        raise ValueError(validation)
    if angle is not None:
        print(f'moving angle to {angle}')
        yield from rotate_now(angle)
    for det in newdets:
        det.cam.acquire_time.kind = "hinted"
    # set the grating
    if 'hopg_loc' in md.keys():
        print('hopg location found')
        hopgx = md['hopg_loc']['x']
        hopgy = md['hopg_loc']['y']
        hopgth = md['hopg_loc']['th']
    else:
        print('no hopg location found')
        hopgx = None
        hopgy = None
        hopgth = None
    print(f'checking grating is {grating}')
    if grating == "1200":
        yield from grating_to_1200(hopgx=hopgx,hopgy=hopgy,hopgtheta=hopgth)
    elif grating == "250":
        yield from grating_to_250(hopgx=hopgx,hopgy=hopgy,hopgtheta=hopgth)
    elif grating == "rsoxs":
        yield from grating_to_rsoxs(hopgx=hopgx,hopgy=hopgy,hopgtheta=hopgth)
    # set the polarization
    yield from set_polarization(pol)
    # set up the scan cycler
    sigcycler = cycler(energy, energies)
    shutter_times = [i * 1000 for i in times]
    yield from bps.mv(energy.scanlock, 0)
    yield from bps.sleep(0.5)
    try:
        yield from bps.mv(energy, energies[0],timeout=20)  # move to the initial energy (unlocked)
    except StatusTimeoutError:
        print("energy took a long time to move to starting energy")
        pass
    except FailedStatus:
        print("energy failed to move the first time")
        pass
    yield from bps.mv(energy, energies[0])

    if lockscan:
        yield from bps.mv(energy.scanlock, 1)  # lock the harmonic, grating, m3_pitch everything based on the first energy
    old_n_exp = {}
    for det in newdets:
        old_n_exp[det.name] = det.number_exposures
        det.number_exposures = n_exp
        sigcycler += cycler(det.cam.acquire_time, times.copy())
    sigcycler += cycler(Shutter_open_time, shutter_times)

    if temp is not None:
        if temp_ramp is not None:
            print(f'setting ramp speed to {temp_ramp}deg/min')
            yield from bps.mv(tem_tempstage.ramp_speed,temp_ramp)
            yield from bps.sleep(0.5) # make sure the controller has time to change
        if temp_wait>=0:
            print(f'ramping temperature to {temp} and waiting {temp_wait*60} seconds')
            yield from bps.mv(tem_tempstage,temp) # set the temp stage and wait
            yield from bps.sleep(temp_wait*60)
        else:
            print(f'starting temperature ramp to {temp} and continuing')
            yield from bps.mv(tem_tempstage.setpoint,temp) # set the temp stage and move on

    yield from bp.scan_nd(newdets + signals, sigcycler, md=md)
    yield from cleanup()
    for det in newdets:
        det.number_exposures = old_n_exp[det.name]


def new_en_scan_core(
    dets=None,    # a list of detectors to run at each step - get from md by default
    energy=None,  # optional energy object to set energy commands to - sets to energy by default, but allows for simulation
    lockscan = True, # whether to lock the harmonic and other energy components during a scan
    grating="no change", # what grating to use for this scan

    energies=None,# a list of energies to run through in the inner loop
    times=None,   # exposure times for each energy (same length as energies) (cycler add to energies)

    polarizations=None, # polarizations to run as an outer loop (cycler multiply with previous)
    
    locations=None,       # locations to run together as an outer loop  (cycler multiply with previous) list of location dicts
    temperatures=None,       # locations to run as an outer loop  (cycler multiply with previous generally, but optionally add to locations - see next)

    temps_with_locations = False, # indicates to move locations and temperatures at the same time, not multiplying exposures (they must be the same length!)

    enscan_type=None,     # optional extra string name to describe this type of scan - will make timing
    master_plan=None,   # if this is lying within an outer plan, that name can be stored here
    sim_mode=False,  # if true, check all inputs but do not actually run anything
    md=None,  # md to pass to the scan
    **kwargs #extraneous settings from higher level plans are ignored
):
    # grab locals
    if signals is None:
        signals = []
    if dets is None:
        if md['RSoXS_Main_DET'] == 'WAXS':
            dets = ['waxs_det']
        else:
            dets = ['saxs_det']
    if energies is None:
        energies = []
    if times is None:
        times = []
    if polarizations is None:
        polarizations = []
    if locations is None:
        locations = []
    if temperatures is None:
        temperatures = []
    if md is None:
        md = {}
    if energy is None:
        energy = en
    arguments = dict(locals())
    del arguments["md"]  # no recursion here!
    arguments["signals"] = [signal.name for signal in arguments["signals"]]
    arguments["energy"] = arguments["energy"].name
    if md is None:
        md = {}
    md.setdefault("plan_history", [])
    md["plan_history"].append({"plan_name": "en_scan_core", "arguments": arguments})
    md.update({"plan_name": enscan_type, "master_plan": master_plan,'plan_args' :arguments })
    # print the current sample information
    # sample()  # print the sample information  Removing this because RE will no longer be loaded with sample data
    # set the exposure times to be hinted for the detector which will be used

    # validate inputs
    valid = True
    validation = ""
    newdets = []
    detnames = []
    for det in dets:
        if not isinstance(det, Device):
            try:
                det_dev = globals()[det]
                newdets.append(det_dev)
                detnames.append(det_dev.name)
            except Exception:
                valid = False
                validation += f"detector {det} is not an ophyd device\n"
        else:
            newdets.append(det)
            detnames.append(det.name)
    if len(newdets) < 1:
        valid = False
        validation += "No detectors are given\n"
    if min(energies) < 70 or max(energies) > 2200:
        valid = False
        validation += "energy input is out of range for SST 1\n"
    if grating == "1200":
        if min(energies) < 150:
            valid = False
            validation += "energy is to low for the 1200 l/mm grating\n"
    elif grating == "250":
        if max(energies) > 1300:
            valid = False
            validation += "energy is too high for 250 l/mm grating\n"
    elif grating == "rsoxs":
        if max(energies) > 1300:
            valid = False
            validation += "energy is too high for 250 l/mm grating\n"
    else:
        valid = False
        validation += "invalid grating was chosen"
    if max(times) > 10:
        valid = False
        validation += "exposure times greater than 10 seconds are not valid\n"
    if min(polarizations) < -1 or max(polarizations) > 180:
        valid = False
        validation += f"a provided polarization is not valid\n"
    if min(temperatures,default=35) < 20 or max(temperatures,default=35) > 300:
        valid = False
        validation += f"temperature out of range\n"
    if not isinstance(energy, Device):
        valid = False
        validation += f"energy object {energy} is not a valid ophyd device\n"
    motor_positions=[]
    if len(locations) > 0:
        motor_positions = [{d['motor']: d['position'] for d in location} for location in locations]
        angles = {d.get('angle', None) for d in motor_positions}
        angles.discard(None)
        xs = {d.get('x', None) for d in motor_positions}
        xs.discard(None)
        if min(xs,default=0) < -13 or max(xs,default=0) > 13:
            valid = False
            validation += f"X motor is out of vaild range\n"
        ys = {d.get('y', None) for d in motor_positions}
        ys.discard(None)
        if min(ys,default=0) < -190 or max(ys,default=0) > 355:
            valid = False
            validation += f"Y motor is out of vaild range\n"
        zs = {d.get('z', None) for d in motor_positions}
        zs.discard(None)
        if min(zs,default=0) < -13 or max(zs,default=0) > 13:
            valid = False
            validation += f"Z motor is out of vaild range\n"
        # temxs = {d.get('temx', None) for d in motor_positions}
        # temxs.discard(None)
        # if min(xs) < -13 or max(xs) > 13:
        #     valid = False
        #     validation += f"X motor is out of vaild range\n"
        # temys = {d.get('temy', None) for d in motor_positions}
        # temys.discard(None)
        # if min(xs) < -13 or max(xs) > 13:
        #     valid = False
        #     validation += f"X motor is out of vaild range\n"
        temzs = {d.get('temz', None) for d in motor_positions}
        temzs.discard(None)
        if min(temzs,default=0) < 0 or max(temzsdefault=0) > 150:
            valid = False
            validation += f"TEMz motor is out of vaild range\n"
        if max(temzs,0) > 100 and min(ys,default=50) < 20:
            valid = False
            validation += f"potential clash between TEY and sample bar\n"
    if(temps_with_locations):
        if len(temperatures)!= len(locations):
            valid = False
            validation += f"temperatures and locations are different lengths, cannot be simultaneously changed\n"
    if sim_mode:
        if valid:
            retstr = f"scanning {detnames} from {min(energies)} eV to {max(energies)} eV on the {grating} l/mm grating\n"
            retstr += f"    in {len(times)} steps with exposure times from {min(times)} to {max(times)} seconds\n"
            return retstr
        else:
            return validation

    if not valid:
        raise ValueError(validation)
    for det in newdets:
        det.cam.acquire_time.kind = "hinted"
    # set the grating
    if 'hopg_loc' in md.keys():
        print('hopg location found')
        hopgx = md['hopg_loc']['x']
        hopgy = md['hopg_loc']['y']
        hopgth = md['hopg_loc']['th']
    else:
        print('no hopg location found')
        hopgx = None
        hopgy = None
        hopgth = None
    print(f'checking grating is {grating}')
    if grating == "1200":
        yield from grating_to_1200(hopgx=hopgx,hopgy=hopgy,hopgtheta=hopgth)
    elif grating == "250":
        yield from grating_to_250(hopgx=hopgx,hopgy=hopgy,hopgtheta=hopgth)
    elif grating == "rsoxs":
        yield from grating_to_rsoxs(hopgx=hopgx,hopgy=hopgy,hopgtheta=hopgth)
    # set up the scan cycler
    sigcycler = cycler(energy, energies)
    shutter_times = [i * 1000 for i in times]
    yield from bps.mv(energy.scanlock, 0)
    yield from bps.sleep(0.5)
    yield from bps.mv(energy, energies[0])  # move to the initial energy (unlocked)

    if lockscan:
        yield from bps.mv(energy.scanlock, 1)  # lock the harmonic, grating, m3_pitch everything based on the first energy

    for det in newdets:
        sigcycler += cycler(det.cam.acquire_time, times.copy()) # cycler for changing each detector exposure time
    sigcycler += cycler(Shutter_open_time, shutter_times) # cycler for changing the shutter opening time

    if len(polarizations):
        sigcycler *= cycler(energy.polarization, polarizations) # cycler for polarization changes (multiplied means we do everything above for each polarization)


    if(temps_with_locations):
        angles = [d.get('th', None) for d in motor_positions]
        xs = [d.get('x', None) for d in motor_positions]
        ys = [d.get('y', None) for d in motor_positions]
        zs = [d.get('z', None) for d in motor_positions]
        loc_temp_cycler = cycler(sam_X,xs)
        loc_temp_cycler += cycler(sam_Y,ys) # adding means we run the cyclers simultaenously, 
        loc_temp_cycler += cycler(sam_Z,zs)
        loc_temp_cycler += cycler(sam_Th,angles)
        loc_temp_cycler += cycler(tem_tempstage,temperatures)
        sigcycler *= loc_temp_cycler # add cyclers for temperature and location changes (if they are linked) one of everything above (energies, polarizations) for each temp/location
    else:
        angles = [d.get('th', None) for d in motor_positions]
        xs = [d.get('x', None) for d in motor_positions]
        ys = [d.get('y', None) for d in motor_positions]
        zs = [d.get('z', None) for d in motor_positions]
        loc_cycler = cycler(sam_X,xs)
        loc_cycler += cycler(sam_Y,ys)
        loc_cycler += cycler(sam_Z,zs)
        loc_cycler += cycler(sam_Th,angles)
        sigcycler *= loc_cycler # run every energy for every polarization and every polarization for every location
        sigcycler *= cycler(tem_tempstage,temperatures) # run every location for each temperature step



    yield from finalize_wrapper(bp.scan_nd(newdets + signals, sigcycler, md=md),cleanup())




def NEXAFS_scan_core(
    signals,
    dets,
    energy,
    energies,
    enscan_type=None,
    master_plan=None,
    openshutter=False,
    open_each_step=False,
    lockscan=True,
    pol=0,
    exp_time=1,
    grating="no change",
    motorname="None",
    offset=0,
    sim_mode=False,
    **kwargs #extraneous settings from higher level plans are ignored
):
    if sim_mode:
        return f"NEXAFS scan from {min(energies)} eV to {max(energies)} eV"
    set_exposure(exp_time)
    # set grating
    if 'hopg_loc' in md.keys():
        hopgx = md['hopg_loc']['x']
        hopgy = md['hopg_loc']['y']
        hopgth = md['hopg_loc']['th']
    if grating == "1200":
        yield from grating_to_1200(hopgx=hopgx,hopgy=hopgy,hopgtheta=hopgth)
    elif grating == "250":
        yield from grating_to_250(hopgx=hopgx,hopgy=hopgy,hopgtheta=hopgth)
    elif grating == "rsoxs":
        yield from grating_to_rsoxs(hopgx=hopgx,hopgy=hopgy,hopgtheta=hopgth)
    # set motor offset if it's set
    if motorname != "None":
        yield from bps.rel_set(globals()[motorname], offset, wait=True)
    # set polarization
    yield from set_polarization(pol)
    # make sure the energy is completely read, so we know where we are
    en.read()

    sigcycler = cycler(energy, energies)
    yield from bps.mv(en.scanlock, 0)
    yield from bps.mv(en, energies[0])  # move to the initial energy
    if lockscan:
        yield from bps.mv(en.scanlock, 1) # lock the harmonic, grating, m3_pitch everything based on the first energy
    for signal in signals:
        signal.kind = "normal"
    if openshutter and not open_each_step:
        yield from bps.mv(Shutter_enable, 0)
        yield from bps.mv(Shutter_control, 1)
        yield from bp.scan_nd(
            dets + signals + [en.energy],
            sigcycler,
            md={"plan_name": enscan_type, "master_plan": master_plan},
        )
        yield from bps.mv(Shutter_control, 0)
    elif open_each_step:
        yield from bps.mv(Shutter_enable, 1)
        yield from finalize_wrapper(bp.scan_nd(
            dets + signals + [en.energy],
            sigcycler,
            md={"plan_name": enscan_type, "master_plan": master_plan},
            per_step=one_shuttered_step,
        ),cleanup())
    else:
        yield from bp.scan_nd(
            dets + signals + [en.energy],
            sigcycler,
            md={"plan_name": enscan_type, "master_plan": master_plan},
        )


def NEXAFS_fly_scan_core(
    scan_params,
    openshutter=False,
    pol=0,
    grating="best",
    enscan_type=None,
    master_plan=None,
    angle=None,
    cycles=0,
    locked = True,
    md=None,
    sim_mode=False,
    **kwargs #extraneous settings from higher level plans are ignored
):
    # grab locals
    if md is None:
        md = {}
    arguments = dict(locals())
    del arguments["md"]  # no recursion here!
    if md is None:
        md = {}
    md.setdefault("plan_history", [])
    md["plan_history"].append(
        {"plan_name": "NEXAFS_fly_scan_core", "arguments": arguments}
    )
    md.update({"plan_name": enscan_type, "master_plan": master_plan})
    # validate inputs
    valid = True
    validation = ""
    energies = np.empty(0)
    speeds = []
    for scanparam in scan_params:
        (sten, enden, speed) = scanparam
        energies = np.append(energies, np.linspace(sten, enden, 10))
        speeds.append(speed)
    if len(energies) < 10:
        valid = False
        validation += f"scan parameters {scan_params} could not be parsed\n"
    if min(energies) < 70 or max(energies) > 2200:
        valid = False
        validation += "energy input is out of range for SST 1\n"
    if grating == "1200":
        if min(energies) < 150:
            valid = False
            validation += "energy is to low for the 1200 l/mm grating\n"
    elif grating == "250":
        if max(energies) > 1000:
            valid = False
            validation += "energy is too high for 250 l/mm grating\n"
    elif grating == "rsoxs":
        if max(energies) > 1000:
            valid = False
            validation += "energy is too high for 250 l/mm grating\n"
    else:
        valid = False
        validation += "invalid grating was chosen"
    if pol < -1 or pol > 180:
        valid = False
        validation += f"polarization of {pol} is not valid\n"
    if angle is not None:
        if -155 > angle or angle > 195:
            valid = False
            validation += f"angle of {angle} is out of range\n"
    if sim_mode:
        if valid:
            retstr = f"fly scanning from {min(energies)} eV to {max(energies)} eV on the {grating} l/mm grating\n"
            retstr += f"    at speeds from {max(speeds)} to {max(speeds)} ev/second\n"
            return retstr
        else:
            return validation
    if not valid:
        raise ValueError(validation)
    if angle is not None:
        print(f'moving angle to {angle}')
        yield from rotate_now(angle)
    if 'hopg_loc' in md.keys():
        hopgx = md['hopg_loc']['x']
        hopgy = md['hopg_loc']['y']
        hopgth = md['hopg_loc']['th']
    else:
        hopgx = None
        hopgy = None
        hopgth = None
    if grating == "1200":
        yield from grating_to_1200(hopgx=hopgx,hopgy=hopgy,hopgtheta=hopgth)
    elif grating == "250":
        yield from grating_to_250(hopgx=hopgx,hopgy=hopgy,hopgtheta=hopgth)
    elif grating == "rsoxs":
        yield from grating_to_rsoxs(hopgx=hopgx,hopgy=hopgy,hopgtheta=hopgth)
    signals = [Beamstop_WAXS, Beamstop_SAXS, Izero_Mesh, Sample_TEY]
    if np.isnan(pol):
        pol = en.polarization.setpoint.get()
    (en_start, en_stop, en_speed) = scan_params[0]
    yield from bps.mv(en.scanlock, 0) # unlock parameters
    print("Moving to initial position before scan start")
    yield from bps.mv(en.energy, en_start+10, en.polarization, pol )  # move to the initial energy
    samplepol = en.sample_polarization.setpoint.get()
    if locked:
        yield from bps.mv(en.scanlock, 1) # lock parameters for scan, if requested
    yield from bps.mv(en.energy, en_start-0.10 )  # move to the initial energy
    print(f"Effective sample polarization is {samplepol}")
    if len(kwargs)>0:
        print(f'{kwargs} were entered as options, but are being ignored')
    if cycles>0:
        rev_scan_params = []
        for (start, stop, speed) in scan_params:
            rev_scan_params = [(stop, start, speed)]+rev_scan_params
        scan_params += rev_scan_params
        scan_params *= int(cycles)

    uid = ""
    if openshutter:
        yield from bps.mv(Shutter_enable, 0)
        yield from bps.mv(Shutter_control, 1)
    uid = yield from finalize_wrapper(fly_scan_eliot(scan_params,sigs=signals, md=md, locked=locked, polarization=pol),cleanup())

    return uid


def rd(obj, *, default_value=0):
    """Reads a single-value non-triggered object
    This is a helper plan to get the scalar value out of a Device
    (such as an EpicsMotor or a single EpicsSignal).
    For devices that have more than one read key the following rules are used:
    - if exactly 1 field is hinted that value is used
    - if no fields are hinted and there is exactly 1 value in the
      reading that value is used
    - if more than one field is hinted an Exception is raised
    - if no fields are hinted and there is more than one key in the reading an
      Exception is raised
    The devices is not triggered and this plan does not create any Events
    Parameters
    ----------
    obj : Device
        The device to be read
    default_value : Any
        The value to return when not running in a "live" RunEngine.
        This come ups when ::
           ret = yield Msg('read', obj)
           assert ret is None
        the plan is passed to `list` or some other iterator that
        repeatedly sends `None` into the plan to advance the
        generator.
    Returns
    -------
    val : Any or None
        The "single" value of the device
    """
    hints = getattr(obj, "hints", {}).get("fields", [])
    if len(hints) > 1:
        msg = (
            f"Your object {obj} ({obj.name}.{getattr(obj, 'dotted_name', '')}) "
            f"has {len(hints)} items hinted ({hints}).  We do not know how to "
            "pick out a single value.  Please adjust the hinting by setting the "
            "kind of the components of this device or by rd ing one of it's components"
        )
        raise ValueError(msg)
    elif len(hints) == 0:
        hint = None
        if hasattr(obj, "read_attrs"):
            if len(obj.read_attrs) != 1:
                msg = (
                    f"Your object {obj} ({obj.name}.{getattr(obj, 'dotted_name', '')}) "
                    f"and has {len(obj.read_attrs)} read attrs.  We do not know how to "
                    "pick out a single value.  Please adjust the hinting/read_attrs by "
                    "setting the kind of the components of this device or by rd ing one "
                    "of its components"
                )

                raise ValueError(msg)
    # len(hints) == 1
    else:
        (hint,) = hints

    ret = yield from read(obj)

    # list-ify mode
    if ret is None:
        return default_value

    if hint is not None:
        return ret[hint]["value"]

    # handle the no hint 1 field case
    try:
        (data,) = ret.values()
    except ValueError as er:
        msg = (
            f"Your object {obj} ({obj.name}.{getattr(obj, 'dotted_name', '')}) "
            f"and has {len(ret)} read values.  We do not know how to pick out a "
            "single value.  Please adjust the hinting/read_attrs by setting the "
            "kind of the components of this device or by rd ing one of its components"
        )

        raise ValueError(msg) from er
    else:
        return data["value"]


# monkey batch bluesky.plans_stubs to fix bug.
bps.rd = rd


def one_shuttered_step(detectors, step, pos_cache):
    """
    Inner loop of an N-dimensional step scan

    This is the default function for ``per_step`` param`` in ND plans.

    Parameters
    ----------
    detectors : iterable
        devices to read
    step : dict
        mapping motors to positions in this step
    pos_cache : dict
        mapping motors to their last-set positions
    """

    yield Msg("checkpoint")
    grp = _short_uid("set")  # stolen from move per_step to break out the wait
    for motor, pos in step.items():
        if pos == pos_cache[motor]:
            # This step does not move this motor.
            continue
        yield Msg("set", motor, pos, group=grp)
        pos_cache[motor] = pos

    motors = step.keys()  # start the acquisition now
    yield from bps.mv(Shutter_trigger, 1)
    yield from trigger_and_read(list(detectors) + list(motors))
    t = yield from bps.rd(Shutter_open_time)
    yield from bps.sleep((t / 1000) + 0.5)
    yield Msg(
        "wait", None, group=grp
    )  # now wait for motors, before moving on to next step



def fly_scan_eliot(scan_params, sigs=[], polarization=0, locked = 1, *, md={}):
    """
    Specific scan for SST-1 monochromator fly scan, while catching up with the undulator

    scan proceeds as:
    1.) set up the flying parameters in the monochromator
    2.) move to the starting position in both undulator and monochromator
    3.) begin the scan (take baseline, begin monitors)
    4.) read the current mono readback
    5.) set the undulator to move to the corresponding position
    6.) if the mono is still running (not at end position), return to step 4
    7.) if the mono is done, load the next parameters and start at step 1
    8.) if no more parameters, end the scan

    Parameters
    ----------
    scan_params : a list of tuples consisting of:
        (start_en : eV to begin the scan,
        stop_en : eV to stop the scan,
        speed_en : eV / second to move the monochromator)
        the stop energy of each tuple should match the start of the next to make a continuous scan
            although this is not strictly enforced to allow for flexibility
    pol : polarization to run the scan
    grating : grating to run the scan
    md : dict, optional
        metadata

    """
    _md = {
        "detectors": [mono_en.name],
        "motors": [mono_en.name],
        "plan_name": "fly_scan_eliot",
        "hints": {},
    }
    _md.update(md or {})
    devices = [mono_en]+sigs

    @bpp.monitor_during_decorator([mono_en])
    @bpp.stage_decorator(list(devices))
    @bpp.run_decorator(md=_md)
    def inner_scan_eliot():
        # start the scan parameters to the monoscan PVs
        yield Msg("checkpoint")
        if np.isnan(polarization):
            pol = en.polarization.setpoint.get()
        else:
            yield from set_polarization(polarization)
            pol = polarization

        for (start_en, end_en, speed_en) in scan_params:
            step = 0
            print(f"starting fly from {start_en} to {end_en} at {speed_en} eV/second")
            yield Msg("checkpoint")
            print("Preparing mono for fly")
            yield from bps.mv(
                Mono_Scan_Start_ev, start_en,
                Mono_Scan_Stop_ev,end_en,
                Mono_Scan_Speed_ev,speed_en,
            )
            # move to the initial position
            #if step > 0:
            #    yield from wait(group="EPU")
            yield from bps.abs_set(mono_en, start_en, group="mono")
            print("moving to starting position")
            yield from wait(group="mono")
            print("Mono in start position")
            yield from bps.mv(epu_gap, en.gap(start_en, pol, locked))
            yield from bps.abs_set(epu_gap, en.gap(start_en, pol, locked), group="EPU")
            yield from wait(group="EPU")
            print("EPU in start position")
            if step == 0:
                monopos = mono_en.readback.get()
                yield from bps.abs_set(
                    epu_gap,
                    en.gap(monopos, pol, locked),
                    wait=False,
                    group="EPU",
                )
                yield from wait(group="EPU")
            # start the mono scan
            print("starting the fly")
            yield from bps.sleep(.5)
            yield from bps.mv(Mono_Scan_Start, 1)
            monopos = mono_en.readback.get()
            while np.abs(monopos - end_en) > 0.1:
                monopos = mono_en.readback.get()
                yield from bps.abs_set(
                    epu_gap,
                    en.gap(monopos, pol, locked),
                    wait=False,
                    group="EPU",
                )
                yield from create("primary")
                for obj in devices:
                    yield from read(obj)
                yield from save()
                yield from wait(group="EPU")
            print(f"Mono reached {monopos} which appears to be near {end_en}")
            step += 1

    return (yield from inner_scan_eliot())




def fly_scan_dets(scan_params,dets, polarization=0, locked = 1, *, md={}):
    """
    Specific scan for SST-1 monochromator fly scan, while catching up with the undulator
    this specific plan in in progress and is not operational yet

    scan proceeds as:
    1.) set up the flying parameters in the monochromator
    2.) move to the starting position in both undulator and monochromator
    3.) begin the scan (take baseline, begin monitors)
    4.) read the current mono readback
    5.) set the undulator to move to the corresponding position
    6.) if the mono is still running (not at end position), return to step 4
    7.) if the mono is done, load the next parameters and start at step 1
    8.) if no more parameters, end the scan

    Parameters
    ----------
    scan_params : a list of tuples consisting of:
        (start_en : eV to begin the scan,
        stop_en : eV to stop the scan,
        speed_en : eV / second to move the monochromator)
        the stop energy of each tuple should match the start of the next to make a continuous scan
            although this is not strictly enforced to allow for flexibility
    pol : polarization to run the scan
    grating : grating to run the scan
    md : dict, optional
        metadata

    """
    _md = {
        "detectors": [mono_en.name,Shutter_control.name],
        "motors": [mono_en.name,Shutter_control.name],
        "plan_name": "fly_scan_RSoXS",
        "hints": {},
    }
    _md.update(md or {})

    devices = [mono_en]
    @bpp.monitor_during_decorator([mono_en]) # add shutter
    #@bpp.stage_decorator(list(devices)) # staging the detector # do explicitely
    @bpp.run_decorator(md=_md)
    def inner_scan_eliot():
        # start the scan parameters to the monoscan PVs
        for det in dets:
            yield from bps.stage(det)
            yield from abs_set(det.cam.image_mode, 2) # set continuous mode
        yield Msg("checkpoint")
        if np.isnan(polarization):
            pol = en.polarization.setpoint.get()
        else:
            yield from set_polarization(polarization)
            pol = polarization
        step = 0
        for (start_en, end_en, speed_en) in scan_params:
            print(f"starting fly from {start_en} to {end_en} at {speed_en} eV/second")
            yield Msg("checkpoint")
            print("Preparing mono for fly")
            yield from bps.mv(
                Mono_Scan_Start_ev,
                start_en,
                Mono_Scan_Stop_ev,
                end_en,
                Mono_Scan_Speed_ev,
                speed_en,
            )
            # move to the initial position
            if step > 0:
                yield from wait(group="EPU")
            yield from bps.abs_set(mono_en, start_en, group="EPU")
            print("moving to starting position")
            yield from wait(group="EPU")
            print("Mono in start position")
            yield from bps.mv(epu_gap, en.gap(start_en, pol, locked))
            print("EPU in start position")
            if step == 0:
                monopos = mono_en.readback.get()
                yield from bps.abs_set(
                    epu_gap,
                    en.gap(monopos, pol, locked),
                    wait=False,
                    group="EPU",
                )
                yield from wait(group="EPU")
            print("Starting detector stream")
            # start the detectors collecting in continuous mode
            for det in dets:
                yield from trigger(det, group="det_trigger")
            # start the mono scan
            print("starting the fly")
            yield from bps.mv(Mono_Scan_Start, 1)
            monopos = mono_en.readback.get()
            while np.abs(monopos - end_en) > 0.1:
                yield from wait(group="EPU")
                monopos = mono_en.readback.get()
                yield from bps.abs_set(
                    epu_gap,
                    en.gap(monopos, pol, locked),
                    wait=False,
                    group="EPU",
                )
                yield from create("primary")
                for obj in devices:
                    yield from read(obj)
                yield from save()
            print(f"Mono reached {monopos} which appears to be near {end_en}")
            print("Stopping Detector stream")
            for det in dets:
                yield from abs_set(det.cam.acquire, 0)
            for det in dets:
                yield from read(det)
                yield from save(det)

            step += 1
        for det in dets:
            yield from unstage(det)
            yield from abs_set(det.cam.image_mode, 1)

    return (yield from inner_scan_eliot())

