import sys
from pathlib import Path

import os
import re
import nslsii
import time
import appdirs
import httpx

from bluesky.preprocessors import finalize_decorator
from bluesky.run_engine import Msg
import bluesky.plan_stubs as bps
from nbs_bl.run_engine import create_run_engine
from nbs_bl.beamline import GLOBAL_BEAMLINE as bl
from nbs_bl.printing import run_report
from nbs_bl.help import print_builtins
from nbs_bl.detectors import *
from nbs_bl.plans.scans import *
from nbs_bl.plans.xas import *
from nbs_bl.samples import *
from rsoxs.redis_config import rsoxs_config


from databroker import Broker

run_report(__file__)

try:
    from bluesky_queueserver import is_re_worker_active
except ImportError:
    # TODO: delete this when 'bluesky_queueserver' is distributed as part of collection environment
    def is_re_worker_active():
        return False


RE = create_run_engine(setup=True)

if not is_re_worker_active():
    ns = get_ipython().user_ns
else:
    ns = {}
if not is_re_worker_active():
    get_ipython().log.setLevel("ERROR")
# db = Broker.named("rsoxs")  ## This can access scan information from Tiled (?)
# db is defined manually so that configure_base
# is not called multiple times when starting up
# Bluesky on the beamline computer.
sd = bl.supplemental_data
# bec = ns["bec"]

"""redis_md_settings = bl.settings.get("redis").get("md")

mdredis = redis.Redis(
    redis_md_settings.get("host", "info.sst.nsls2.bnl.gov"),
    port=redis_md_settings.get("port", 6379),
    db=redis_md_settings.get("db", 0),
)"""
# RE.md = RedisStatusDict(mdredis, prefix=redis_md_settings.get("prefix", ""))
RE.md = bl.md
md = RE.md  ## The contents from md are added into the start document for the scan metadata in Tiled.
# GLOBAL_USER_STATUS.add_status("USER_MD", RE.md)



data_session_re = re.compile(r"^pass-(?P<proposal_number>\d+)$")


def md_validator(md):
    """Validate RE.md before a plan runs.

    This function validates only "data_session".
    """

    if "data_session" in md:
        # if there is a "data_session" key
        # its value must be validated
        data_session_value = md["data_session"]
        if not isinstance(data_session_value, str):
            raise ValueError(f"RE.md['data_session']={data_session_value}', but it must be a string")
        data_session_match = data_session_re.match(data_session_value)
        if data_session_match is None:
            raise ValueError(
                f"RE.md['data_session']='{data_session_value}' "
                f"is not matched by regular expression '{data_session_re.pattern}'"
            )
        else:
            proposal_number = data_session_match.group("proposal_number")
            nslsii_api_client = httpx.Client(
                # base_url="https://api-staging.nsls2.bnl.gov"
                base_url="https://api.nsls2.bnl.gov"
            )
            try:
                proposal_response = nslsii_api_client.get(f"/v1/proposal/{proposal_number}")
                proposal_response.raise_for_status()
                if "error_message" in proposal_response.json():
                    raise ValueError(
                        f"while verifying data_session '{data_session_value}' "
                        f"an error was returned by {proposal_response.url}: "
                        f"{proposal_response.json()}"
                    )
                else:
                    # data_session is valid!
                    pass

            except httpx.RequestError as rerr:
                # give the user a warning
                # but allow the run to start
                warnings.warn(
                    f"while verifying data_session '{data_session_value}' "
                    f"the request {rerr.request.url!r} failed with "
                    f"'{rerr}'"
                )
                return
            except httpx.HTTPStatusError as serr:
                warnings.warn(
                    f"while verifying data_session '{data_session_value}' "
                    f"the request {serr.request.url!r} failed with "
                    f"'{serr}'"
                )
                if serr.response.is_client_error:
                    # the user may be able to fix this?
                    # do not allow the run to start
                    raise serr
                elif serr.response.is_server_error:
                    # allow the run to start
                    pass
    else:
        # if there is no "data_session" key allow runs to start
        pass


# md_validator will be called before a plan runs
RE.md_validator = md_validator

# Optional: set any metadata that rarely changes.
RE.md["beamline_id"] = "SST-1 RSoXS"


# Add a callback that prints scan IDs at the start of each scan.
def print_scan_ids(name, start_doc):
    print("Transient Scan ID: {0} @ {1}".format(start_doc["scan_id"], time.strftime("%Y/%m/%d %H:%M:%S")))
    print("Persistent Unique Scan ID: '{0}'".format(start_doc["uid"]))


RE.subscribe(print_scan_ids, "start")

control_layer = os.getenv("OPHYD_CONTROL_LAYER")

print(f'You are using the "{control_layer}" control layer')

# getting rid of the warnings
import logging

logging.getLogger("caproto").setLevel("ERROR")
# bec.disable_baseline()

# from bluesky.callbacks.zmq import Publisher

# publisher = Publisher("localhost:5577")
# RE.subscribe(publisher)

logger = logging.getLogger("bluesky_darkframes")
handler = logging.StreamHandler()
handler.setLevel("DEBUG")
logger.addHandler(handler)
logger.getEffectiveLevel()
logger.setLevel("DEBUG")  # change DEBUG to INFO later on

# bec.disable_table()
# bec.disable_plots()

# Why are we doing this?
if "scan_id" in RE.md:
    RE.md["scan_id"] = int(RE.md["scan_id"])
