import bluesky.plan_stubs as bps
from nbs_bl.printing import run_report
from nbs_bl.hw import (
    mir1,
    en,
    mir3,
    psh10,
    slitsc,
    slits1,
    shutter_y,
    izero_y,
    slits2,
    slits3,
    Det_W,
    #Det_S,
    BeamStopS,
    BeamStopW,
    sam_Th,
    sam_Z,
    sam_Y,
    sam_X,
    TEMZ,
    mir4OLD,
    #dm7
)
from ..HW.energy import mono_en, grating_to_1200
from ..startup import RE

run_report(__file__)

waxs_in_pos = 2
waxs_out_pos = -94
bs_waxs_in_pos = 69.6



## TODO: Maybe make a larger dictionary or toml file with all of the configurations so that way I can automatically generate a list of these configurations that I can feed into the allowed configurations in rsoxs_scans
## TODO: Ideally I would like to have these hard-coded into rsoxs_scans and import them here, but I have not figured that out yet

## Save mirror alignment here, TODO: need to update positions
## TODO: have it print positions?  Could be a separate function and then cna just call it here
def viewMirrorConfiguration():
    print(mir1.x.read())
    print(mir1.y.read())
    print(mir1.z.read())
    print(mir1.pitch.read())
    print(mir1.roll.read())
    print(mir1.yaw.read())

    print(mir3.x.read())
    print(mir3.y.read())
    print(mir3.z.read())
    print(mir3.pitch.read())
    print(mir3.roll.read())
    print(mir3.yaw.read())

def mirrorConfiguration_RSoXS():
    yield from bps.mv(mir1.x, -0.55)
    yield from bps.mv(mir1.y, -18)
    yield from bps.mv(mir1.z, 0)
    yield from bps.mv(mir1.pitch, 0.45)
    yield from bps.mv(mir1.roll, 0)
    yield from bps.mv(mir1.yaw, 0)

    yield from bps.mv(mir3.x, 22.1)
    yield from bps.mv(mir3.y, 18)
    yield from bps.mv(mir3.z, 0)
    yield from bps.mv(mir3.pitch, 7.93)
    yield from bps.mv(mir3.roll, 0)
    yield from bps.mv(mir3.yaw, 0)



## Intended to allow me to run test scans when I don't have beam.  Does not move any hardware that could interfere with others' experiments.
## TODO: Need to deal with RSoXS_Main_DET md.  
def noBeam():
    return [
        [
            {"motor": slits1.vsize, "position": 10, "order": 0},
            {"motor": slits1.hsize, "position": 10, "order": 0},
            {"motor": slits2.vsize, "position":  10, "order": 0},
            {"motor": slits2.hsize, "position": 10, "order": 0},
            {"motor": slits3.vsize, "position": 10, "order": 0},
            {"motor": slits3.hsize, "position": 10, "order": 0},
        ],
        {
            "RSoXS_Config": "noBeam",
            "RSoXS_Main_DET": "WAXS",
            "RSoXS_WAXS_SDD": 39.19,
            "RSoXS_WAXS_BCX": 467.5,
            "RSoXS_WAXS_BCY": 513.4,
            "WAXS_Mask": [(367, 545), (406, 578), (880, 0), (810, 0)],
            "RSoXS_SAXS_SDD": None,
            "RSoXS_SAXS_BCX": None,
            "RSoXS_SAXS_BCY": None,
        },
    ]


## 20250131 - sets exit slit to narrow aperture so don't accidentally forget
## Also moves I0 out of the way so that scattering from the mesh is not seen
def WAXS_OpenBeamImages():
    return [
        [
            {"motor": TEMZ, "position": 1, "order": 0},
            {"motor": slits1.vsize, "position": 0.02, "order": 0},
            {"motor": slits1.vcenter, "position": -0.55, "order": 0},
            {"motor": slits1.hsize, "position": 0.04, "order": 0},
            {"motor": slits1.hcenter, "position": -0.18, "order": 0},
            {"motor": slits2.vsize, "position":  0.21, "order": 0},
            {"motor": slits2.vcenter, "position": -0.873, "order": 0},
            {"motor": slits2.hsize, "position": 0.4, "order": 0},
            {"motor": slits2.hcenter, "position": -0.1, "order": 0},
            {"motor": slits3.vsize, "position": 1, "order": 0},
            {"motor": slits3.vcenter, "position": -0.45, "order": 0},
            {"motor": slits3.hsize, "position": 1, "order": 0},
            {"motor": slits3.hcenter, "position": 0.15, "order": 0},
            {"motor": shutter_y, "position": 2.2, "order": 0},
            {"motor": izero_y, "position": 145, "order": 0},
            {"motor": Det_W, "position": waxs_in_pos, "order": 1},
            {"motor": BeamStopW, "position": bs_waxs_in_pos, "order": 1},
            {"motor": slitsc, "position": -0.01, "order": 2},
        ],
        {
            "RSoXS_Config": "WAXS_OpenBeamImages",
            "RSoXS_Main_DET": "WAXS",
            "RSoXS_WAXS_SDD": 39.19,
            "RSoXS_WAXS_BCX": 467.5,
            "RSoXS_WAXS_BCY": 513.4,
            "WAXS_Mask": [(367, 545), (406, 578), (880, 0), (810, 0)],
            "RSoXS_SAXS_SDD": None,
            "RSoXS_SAXS_BCX": None,
            "RSoXS_SAXS_BCY": None,
        },
    ]


def WAXSNEXAFS():
    return [
        [
            {"motor": TEMZ, "position": 1, "order": 0},
            {"motor": slits1.vsize, "position": 0.02, "order": 0},
            {"motor": slits1.vcenter, "position": -0.55, "order": 0},
            {"motor": slits1.hsize, "position": 0.04, "order": 0},
            {"motor": slits1.hcenter, "position": -0.18, "order": 0},
            {"motor": slits2.vsize, "position":  0.21, "order": 0},
            {"motor": slits2.vcenter, "position": -0.873, "order": 0},
            {"motor": slits2.hsize, "position": 0.4, "order": 0},
            {"motor": slits2.hcenter, "position": -0.1, "order": 0},
            {"motor": slits3.vsize, "position": 1, "order": 0},
            {"motor": slits3.vcenter, "position": -0.45, "order": 0},
            {"motor": slits3.hsize, "position": 1, "order": 0},
            {"motor": slits3.hcenter, "position": 0.15, "order": 0},
            {"motor": shutter_y, "position": 2.2, "order": 0},
            {"motor": izero_y, "position": -31, "order": 0},
            {"motor": Det_W, "position": waxs_out_pos, "order": 1},
            # {"motor": Det_S, "position": -100, "order": 1},
            {"motor": BeamStopW, "position": bs_waxs_in_pos, "order": 1},
            {"motor": slitsc, "position": -3.05, "order": 2},
        ],
        {
            "RSoXS_Config": "WAXSNEXAFS",
            "RSoXS_Main_DET": "beamstop_waxs",
            "RSoXS_WAXS_SDD": None,
            "RSoXS_WAXS_BCX": None,
            "RSoXS_WAXS_BCY": None,
            "RSoXS_SAXS_SDD": None,
            "RSoXS_SAXS_BCX": None,
            "RSoXS_SAXS_BCY": None,
        },
    ]


def WAXS():
    return [
        [
            {"motor": TEMZ, "position": 1, "order": 0},
            {"motor": slits1.vsize, "position": 0.02, "order": 0},
            {"motor": slits1.vcenter, "position": -0.55, "order": 0},
            {"motor": slits1.hsize, "position": 0.04, "order": 0},
            {"motor": slits1.hcenter, "position": -0.18, "order": 0},
            {"motor": slits2.vsize, "position":  0.21, "order": 0},
            {"motor": slits2.vcenter, "position": -0.873, "order": 0},
            {"motor": slits2.hsize, "position": 0.4, "order": 0},
            {"motor": slits2.hcenter, "position": -0.1, "order": 0},
            {"motor": slits3.vsize, "position": 1, "order": 0},
            {"motor": slits3.vcenter, "position": -0.45, "order": 0},
            {"motor": slits3.hsize, "position": 1, "order": 0},
            {"motor": slits3.hcenter, "position": 0.15, "order": 0},
            {"motor": shutter_y, "position": 2.2, "order": 0},
            {"motor": izero_y, "position": -31, "order": 0},
            {"motor": Det_W, "position": waxs_in_pos, "order": 1},
            {"motor": BeamStopW, "position": bs_waxs_in_pos, "order": 1},
            {"motor": slitsc, "position": -3.05, "order": 2},
        ],
        {
            "RSoXS_Config": "WAXS",
            "RSoXS_Main_DET": "WAXS",
            "RSoXS_WAXS_SDD": 39.19,
            "RSoXS_WAXS_BCX": 467.5,
            "RSoXS_WAXS_BCY": 513.4,
            "WAXS_Mask": [(367, 545), (406, 578), (880, 0), (810, 0)],
            "RSoXS_SAXS_SDD": None,
            "RSoXS_SAXS_BCX": None,
            "RSoXS_SAXS_BCY": None,
        },
    ]


## Added 20241204 to reduce flux using slit C
def WAXS_LowFlux():
    return [
        [
            {"motor": TEMZ, "position": 1, "order": 0},
            {"motor": slits1.vsize, "position": 0.02, "order": 0},
            {"motor": slits1.vcenter, "position": -0.55, "order": 0},
            {"motor": slits1.hsize, "position": 0.04, "order": 0},
            {"motor": slits1.hcenter, "position": -0.18, "order": 0},
            {"motor": slits2.vsize, "position":  0.21, "order": 0},
            {"motor": slits2.vcenter, "position": -0.873, "order": 0},
            {"motor": slits2.hsize, "position": 0.4, "order": 0},
            {"motor": slits2.hcenter, "position": -0.1, "order": 0},
            {"motor": slits3.vsize, "position": 1, "order": 0},
            {"motor": slits3.vcenter, "position": -0.45, "order": 0},
            {"motor": slits3.hsize, "position": 1, "order": 0},
            {"motor": slits3.hcenter, "position": 0.15, "order": 0},
            {"motor": shutter_y, "position": 2.2, "order": 0},
            {"motor": izero_y, "position": -31, "order": 0},
            {"motor": Det_W, "position": waxs_in_pos, "order": 1},
            {"motor": BeamStopW, "position": bs_waxs_in_pos, "order": 1},
            {"motor": slitsc, "position": -0.05, "order": 2},
        ],
        {
            "RSoXS_Config": "WAXS_LowFlux",
            "RSoXS_Main_DET": "WAXS",
            "RSoXS_WAXS_SDD": 39.19,
            "RSoXS_WAXS_BCX": 467.5,
            "RSoXS_WAXS_BCY": 513.4,
            "WAXS_Mask": [(367, 545), (406, 578), (880, 0), (810, 0)],
            "RSoXS_SAXS_SDD": None,
            "RSoXS_SAXS_BCX": None,
            "RSoXS_SAXS_BCY": None,
        },
    ]


def WAXSNEXAFS_liquid():
    return [
        [
            {"motor": slits1.vsize, "position": 0.02, "order": 0},
            {"motor": slits1.vcenter, "position": -0.55, "order": 0},
            {"motor": slits1.hsize, "position": 0.04, "order": 0},
            {"motor": slits1.hcenter, "position": -0.18, "order": 0},
            {"motor": slits2.vsize, "position":  0.21, "order": 0},
            {"motor": slits2.vcenter, "position": -0.873, "order": 0},
            {"motor": slits2.hsize, "position": 0.4, "order": 0},
            {"motor": slits2.hcenter, "position": -0.1, "order": 0},
            {"motor": slits3.vsize, "position": 1, "order": 0},
            {"motor": slits3.vcenter, "position": -0.45, "order": 0},
            {"motor": slits3.hsize, "position": 1, "order": 0},
            {"motor": slits3.hcenter, "position": 0.15, "order": 0},
            {"motor": shutter_y, "position": 2.2, "order": 0},
            {"motor": izero_y, "position": -31, "order": 1},
            {"motor": BeamStopW, "position": bs_waxs_in_pos, "order": 1},
            {"motor": Det_W, "position": waxs_out_pos, "order": 1},
            {"motor": slitsc, "position": -3.05, "order": 2}
        ],
        {
            "RSoXS_Config": "WAXS",
            "RSoXS_Main_DET": "WAXS",
            "RSoXS_WAXS_SDD": 39.19,
            "RSoXS_WAXS_BCX": 396.341,
            "RSoXS_WAXS_BCY": 549.99,
            "WAXS_Mask": [(367, 545), (406, 578), (880, 0), (810, 0)],
            "RSoXS_SAXS_SDD": None,
            "RSoXS_SAXS_BCX": None,
            "RSoXS_SAXS_BCY": None,
        },
    ]


def WAXS_liquid():
    return [
        [
            {"motor": slits1.vsize, "position": 0.02, "order": 0},
            {"motor": slits1.vcenter, "position": -0.55, "order": 0},
            {"motor": slits1.hsize, "position": 0.04, "order": 0},
            {"motor": slits1.hcenter, "position": -0.18, "order": 0},
            {"motor": slits2.vsize, "position":  0.21, "order": 0},
            {"motor": slits2.vcenter, "position": -0.873, "order": 0},
            {"motor": slits2.hsize, "position": 0.4, "order": 0},
            {"motor": slits2.hcenter, "position": -0.1, "order": 0},
            {"motor": slits3.vsize, "position": 1, "order": 0},
            {"motor": slits3.vcenter, "position": -0.45, "order": 0},
            {"motor": slits3.hsize, "position": 1, "order": 0},
            {"motor": slits3.hcenter, "position": 0.15, "order": 0},
            {"motor": shutter_y, "position": 2.2, "order": 0},
            {"motor": izero_y, "position": -31, "order": 1},
            {"motor": Det_W, "position": waxs_in_pos, "order": 1},
            {"motor": BeamStopW, "position": bs_waxs_in_pos, "order": 1},
            {"motor": slitsc, "position": -3.05, "order": 2},
        ],
        {
            "RSoXS_Config": "WAXS",
            "RSoXS_Main_DET": "WAXS",
            "RSoXS_WAXS_SDD": 39.19,
            "RSoXS_WAXS_BCX": 467.5,
            "RSoXS_WAXS_BCY": 513.4,
            "WAXS_Mask": [(367, 545), (406, 578), (880, 0), (810, 0)],
            "RSoXS_SAXS_SDD": None,
            "RSoXS_SAXS_BCX": None,
            "RSoXS_SAXS_BCY": None,
        },
    ]

def all_out():
    yield from psh10.close()
    print("Retracting Slits to 1 cm gap")
    yield from slits_out()
    print("Moving the rest of RSoXS components")
    yield from bps.mv(
        shutter_y,
        44,
        izero_y,
        144,
        Det_W,
        waxs_out_pos,
        # Det_S,
        # -100,
        BeamStopW,
        3,
        BeamStopS,
        3,
        sam_Y,
        345,
        sam_X,
        0,
        sam_Z,
        0,
        sam_Th,
        0,
        en.polarization, #TODO - remove this to another step with try except for PV access error
        0,
        slitsc,
        -0.05,
        TEMZ,
        1
        #dm7, ## PK 20240625 - commenting out because it throws an error while running nmode #TODO - check with cherno about moving mirror 4 back as well
        #80 ## PK 20240528: Changed from -80 to 80 because while running nmode, I got LimitError.  I think the negative sign is a typo and DM7 is supposed to move up to get out of the way.
    )
    print("moving back to 1200 l/mm grating")
    yield from grating_to_1200()
    print("resetting cff to 2.0")
    yield from bps.mv(mono_en.cff, 2)
    print("moving to 270 eV")
    yield from bps.mv(en, 270)
    RE.md.update(
        {
            "RSoXS_Config": "inactive",
            "RSoXS_Main_DET": None,
            "RSoXS_WAXS_SDD": None,
            "RSoXS_WAXS_BCX": None,
            "RSoXS_WAXS_BCY": None,
            "RSoXS_SAXS_SDD": None,
            "RSoXS_SAXS_BCX": None,
            "RSoXS_SAXS_BCY": None,
        }
    )
    print("All done - Happy NEXAFSing")













## Eliot's configurations that I don't use

def Shutter_in():
    yield from bps.mv(shutter_y, 2.2)


def Shutter_out():
    yield from bps.mv(shutter_y, 44)


def Izero_screen():
    yield from bps.mv(izero_y, 2)


def Izero_mesh():
    yield from bps.mv(izero_y, -29)


def Izero_diode():
    yield from bps.mv(izero_y, 35)


def Izero_out():
    yield from bps.mv(izero_y, 145)


# def DetS_in():
#     yield from bps.mv(Det_S, -15)


# def DetS_edge():
#     yield from bps.mv(Det_S, -50)


# def DetS_out():
#     yield from bps.mv(Det_S, -100)


def DetW_edge():
   yield from bps.mv(Det_W, -50)


def DetW_in():
   yield from bps.mv(Det_W, waxs_in_pos)


def DetW_out():
   yield from bps.mv(Det_W, waxs_out_pos)


def BSw_in():
    yield from bps.mv(BeamStopW, bs_waxs_in_pos)


def BSw_out():
    yield from bps.mv(BeamStopW, 3)


def BSs_in():
    yield from bps.mv(BeamStopS, 67)


def BSs_out():
    yield from bps.mv(BeamStopS, 3)


#def Detectors_out():
#    yield from bps.mv(Det_S, -94, Det_W, -100)


#def Detectors_edge():
#    yield from bps.mv(Det_S, -50, Det_W, -50)


def BS_out():
    yield from bps.mv(BeamStopW, 3, BeamStopS, 3)


def slits_in_SAXS():
    yield from bps.mv(
        slits1.vsize,
        0.025,
        slits1.vcenter,
        -0.55,
        slits1.hsize,
        0.153,
        slits1.hcenter,
        0.7,
        slits2.vsize,
        0.4,
        slits2.vcenter,
        -0.9,
        slits2.hsize,
        0.5,
        slits2.hcenter,
        0.7,
        slits3.vsize,
        1,
        slits3.vcenter,
        -0.5,
        slits3.hsize,
        1,
        slits3.hcenter,
        0.9,
    )


def slits_out():
    yield from bps.mv(
        slits1.vsize,
        10,
        slits1.hsize,
        10,
        slits2.vsize,
        10,
        slits2.hsize,
        10,
        slits3.vsize,
        10,
        slits3.hsize,
        10,
    )


def slits_in_WAXS():
    yield from bps.mv(
        slits1.vsize,
        0.05,
        slits1.vcenter,
        -0.55,
        slits1.hsize,
        0.3,
        slits1.hcenter,
        0.55,
        slits2.vsize,
        0.45,
        slits2.vcenter,
        -1.05,
        slits2.hsize,
        0.5,
        slits2.hcenter,
        0.45,
        slits3.vsize,
        1.1,
        slits3.vcenter,
        -0.625,
        slits3.hsize,
        1.2,
        slits3.hcenter,
        0.55,
    )

#TODO do we want these functions anymore?




def mirror_pos_NEXAFS():# TODO positions names are all lowercase now
    yield from bps.mv(mir1.Pitch, 0.66)
    yield from bps.mv(mir1.X, 0)
    yield from bps.mv(mir1.Y, -18)
    yield from bps.mv(mir1.Z, 0)
    yield from bps.mv(mir1.Roll, 3)
    yield from bps.mv(mir1.Yaw, 0)


## TODO: make a wh() function for mirror positions in sst_base, similar to the wh() function for slits
def mirror_pos_rsoxs():# TODO positions names are all lowercase now
    yield from bps.mv(
        mir3.Pitch,
        7.92,
        mir3.X,
        26.5,
        mir3.Y,
        18,
        mir3.Z,
        0,
        mir3.Roll,
        0,
        mir3.Yaw,
        1,
        mir1.Pitch,
        0.7,
        mir1.X,
        0,
        mir1.Y,
        -18,
        mir1.Z,
        0,
        mir1.Roll,
        0,
        mir1.Yaw,
        0,
    )


def mirror1_NEXAFSpos():
    yield from bps.mv(
        mir3.pitch,
        7.94,
        mir3.x,
        26.5,
        mir3.y,
        18,
        mir3.z,
        0,
        mir3.roll,
        0,
        mir3.yaw,
        1,
        mir1.pitch,
        0.68,
        mir1.x,
        0,
        mir1.y,
        -18,
        mir1.z,
        0,
        mir1.roll,
        0,
        mir1.yaw,
        0,
    )






def SAXSNEXAFS():
    return [
        [
            {"motor": TEMZ, "position": 1, "order": 0},
           {"motor": slits1.vsize, "position": 0.02, "order": 0},
            {"motor": slits1.vcenter, "position": -0.55, "order": 0},
            {"motor": slits1.hsize, "position": 0.04, "order": 0},
            {"motor": slits1.hcenter, "position": -0.18, "order": 0},
            {"motor": slits2.vsize, "position":  0.21, "order": 0},
            {"motor": slits2.vcenter, "position": -0.873, "order": 0},
            {"motor": slits2.hsize, "position": 0.4, "order": 0},
            {"motor": slits2.hcenter, "position": -0.1, "order": 0},
            {"motor": slits3.vsize, "position": 1, "order": 0},
            {"motor": slits3.vcenter, "position": -0.45, "order": 0},
            {"motor": slits3.hsize, "position": 1, "order": 0},
            {"motor": slits3.hcenter, "position": 0.15, "order": 0},
            {"motor": shutter_y, "position": 2.2, "order": 0},
            {"motor": izero_y, "position": -31, "order": 0},
            {"motor": Det_W, "position": waxs_out_pos, "order": 0},
            # {"motor": Det_S, "position": -100, "order": 0},
            {"motor": BeamStopS, "position": 68, "order": 0},
            {"motor": BeamStopW, "position": 3, "order": 1},
            {"motor": slitsc, "position": -3.05, "order": 2},
        ],
        {
            "RSoXS_Config": "SAXSNEXAFS",
            "RSoXS_Main_DET": "Beamstop_SAXS",
            "RSoXS_WAXS_SDD": None,
            "RSoXS_WAXS_BCX": None,
            "RSoXS_WAXS_BCY": None,
            "RSoXS_SAXS_SDD": None,
            "RSoXS_SAXS_BCX": None,
            "RSoXS_SAXS_BCY": None,
        },
    ]





def DM7NEXAFS():
    return [
        [
            {"motor": TEMZ, "position": 1, "order": 0},
            {"motor": slits1.vsize, "position": 0.02, "order": 0},
            {"motor": slits1.vcenter, "position": -0.55, "order": 0},
            {"motor": slits1.hsize, "position": 0.04, "order": 0},
            {"motor": slits1.hcenter, "position": -0.18, "order": 0},
            {"motor": slits2.vsize, "position":  0.21, "order": 0},
            {"motor": slits2.vcenter, "position": -0.873, "order": 0},
            {"motor": slits2.hsize, "position": 0.4, "order": 0},
            {"motor": slits2.hcenter, "position": -0.1, "order": 0},
            {"motor": slits3.vsize, "position": 1, "order": 0},
            {"motor": slits3.vcenter, "position": -0.45, "order": 0},
            {"motor": slits3.hsize, "position": 1, "order": 0},
            {"motor": slits3.hcenter, "position": 0.15, "order": 0},
            {"motor": shutter_y, "position": 2.2, "order": 0},
            {"motor": izero_y, "position": -31, "order": 0},
            {"motor": Det_W, "position": waxs_out_pos, "order": 1},
            # {"motor": Det_S, "position": -100, "order": 1},
            {"motor": BeamStopW, "position": 3, "order": 1},
            {"motor": BeamStopS, "position": 3, "order": 1},
            {"motor": slitsc, "position": -3.05, "order": 2},
            #{"motor": mir4OLD.x, "position": 0, "order": 1},
            {"motor": mir4OLD.y, "position": -10, "order": 1},
            {"motor": dm7, "position": -15, "order": 1},
        ],
        {
            "RSoXS_Config": "DM7NEXAFS",
            "RSoXS_Main_DET": "DownstreamLargeDiode_int",
            "RSoXS_WAXS_SDD": None,
            "RSoXS_WAXS_BCX": None,
            "RSoXS_WAXS_BCY": None,
            "RSoXS_SAXS_SDD": None,
            "RSoXS_SAXS_BCX": None,
            "RSoXS_SAXS_BCY": None,
        },
    ]








def SAXS_liquid():
    return [
        [
            {"motor": sam_Y, "position": 350, "order": 0},
            {"motor": slits1.vsize, "position": 0.02, "order": 0},
            {"motor": slits1.vcenter, "position": -0.55, "order": 0},
            {"motor": slits1.hsize, "position": 0.04, "order": 0},
            {"motor": slits1.hcenter, "position": -0.18, "order": 0},
            {"motor": slits2.vsize, "position":  0.21, "order": 0},
            {"motor": slits2.vcenter, "position": -0.873, "order": 0},
            {"motor": slits2.hsize, "position": 0.4, "order": 0},
            {"motor": slits2.hcenter, "position": -0.1, "order": 0},
            {"motor": slits3.vsize, "position": 1, "order": 0},
            {"motor": slits3.vcenter, "position": -0.45, "order": 0},
            {"motor": slits3.hsize, "position": 1, "order": 0},
            {"motor": slits3.hcenter, "position": 0.15, "order": 0},
            {"motor": shutter_y, "position": 2.2, "order": 0},
            {"motor": izero_y, "position": -29, "order": 0},
            {"motor": Det_W, "position": waxs_out_pos, "order": 0},
            # {"motor": Det_S, "position": -15, "order": 0},
            {"motor": BeamStopS, "position": 68, "order": 0},
            {"motor": BeamStopW, "position": 3, "order": 1},
            {"motor": slitsc, "position": -3.05, "order": 2},
        ],
        {
            "RSoXS_Config": "SAXS",
            "RSoXS_Main_DET": "SAXS",
            "SAXS_Mask": [(473, 472), (510, 471), (515, 1024), (476, 1024)],
            "RSoXS_WAXS_SDD": None,
            "RSoXS_WAXS_BCX": None,
            "RSoXS_WAXS_BCY": None,
            "RSoXS_SAXS_SDD": 516,
            "RSoXS_SAXS_BCX": 493.4,
            "RSoXS_SAXS_BCY": 514.4,
        },
    ]

def SAXSNEXAFS_liquid():
    return [
        [
            {"motor": sam_Y, "position": 350, "order": 0},
            {"motor": slits1.vsize, "position": 0.02, "order": 0},
            {"motor": slits1.vcenter, "position": -0.55, "order": 0},
            {"motor": slits1.hsize, "position": 0.04, "order": 0},
            {"motor": slits1.hcenter, "position": -0.18, "order": 0},
            {"motor": slits2.vsize, "position":  0.21, "order": 0},
            {"motor": slits2.vcenter, "position": -0.873, "order": 0},
            {"motor": slits2.hsize, "position": 0.4, "order": 0},
            {"motor": slits2.hcenter, "position": -0.1, "order": 0},
            {"motor": slits3.vsize, "position": 1, "order": 0},
            {"motor": slits3.vcenter, "position": -0.45, "order": 0},
            {"motor": slits3.hsize, "position": 1, "order": 0},
            {"motor": slits3.hcenter, "position": 0.15, "order": 0},
            {"motor": shutter_y, "position": 2.2, "order": 0},
            {"motor": izero_y, "position": -29, "order": 0},
            {"motor": Det_W, "position": waxs_out_pos, "order": 0},
            # {"motor": Det_S, "position": -100, "order": 0},
            {"motor": BeamStopS, "position": 68, "order": 0},
            {"motor": BeamStopW, "position": 3, "order": 1},
            {"motor": slitsc, "position": -3.05, "order": 2},
        ],
        {
            "RSoXS_Config": "SAXS",
            "RSoXS_Main_DET": "SAXS",
            "SAXS_Mask": [(473, 472), (510, 471), (515, 1024), (476, 1024)],
            "RSoXS_WAXS_SDD": None,
            "RSoXS_WAXS_BCX": None,
            "RSoXS_WAXS_BCY": None,
            "RSoXS_SAXS_SDD": 516,
            "RSoXS_SAXS_BCX": 493.4,
            "RSoXS_SAXS_BCY": 514.4,
        },
    ]

