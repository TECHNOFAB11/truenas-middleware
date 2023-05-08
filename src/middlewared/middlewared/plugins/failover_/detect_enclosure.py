import subprocess
import re

from pyudev import Context

from middlewared.service import Service
from middlewared.utils.functools import cache
from .ha_hardware import HA_HARDWARE

import libsgio

ENCLOSURES_DIR = '/sys/class/enclosure/'


class EnclosureDetectionService(Service):

    class Config:
        namespace = 'failover.enclosure'
        private = True

    @cache
    def detect(self):
        HARDWARE = NODE = 'MANUAL'
        if self.middleware.call_sync('system.dmidecode_info')['system-product-name'] == 'BHYVE':
            # bhyve host configures a scsi_generic device that when sent an inquiry will
            # respond with a string that we use to determine the position of the node
            ctx = Context()
            for i in ctx.list_devices(subsystem='scsi_generic'):
                if (model := i.attributes.get('device/model')) is not None:
                    model = model.decode().strip() if isinstance(model, bytes) else model.strip()
                    if model == 'TrueNAS_A':
                        NODE = 'A'
                        HARDWARE = 'BHYVE'
                        break
                    elif model == 'TrueNAS_B':
                        NODE = 'B'
                        HARDWARE = 'BHYVE'
                        break

            return HARDWARE, NODE

        for enc in self.middleware.call_sync("enclosure.list_ses_enclosures"):
            try:
                ed = libsgio.EnclosureDevice(enc).get_element_descriptor()
            except OSError:
                self.logger.warning("Error querying Element Descriptor page %r: %s", enc, ed)
                continue

            if ed:
                info = ed

                if re.search(HA_HARDWARE.ZSERIES_ENCLOSURE.value, info):
                    # Z-series Hardware (Echostream)
                    HARDWARE = 'ECHOSTREAM'
                    reg = re.search(HA_HARDWARE.ZSERIES_NODE.value, info)
                    NODE = reg.group(1)
                    if NODE:
                        break
                elif re.search(HA_HARDWARE.XSERIES_ENCLOSURE.value, info):
                    # X-series Hardware (PUMA)
                    HARDWARE = 'PUMA'

                    sas_addr = ''
                    with open(f'{ENCLOSURES_DIR}{enc.split("/")[-1]}/device/sas_address') as f:
                        # We need to get the SAS address of the SAS expander first
                        sas_addr = f.read().strip()

                    # We then cast the SES address (deduced from SES VPD pages)
                    # to an integer and subtract 1. Then cast it back to hexadecimal.
                    # We then compare if the SAS expander's SAS address
                    # is in the SAS expanders SES address
                    if (reg := re.search(HA_HARDWARE.XSERIES_NODEA.value, info)) is not None:
                        ses_addr = hex(int(reg.group(1), 16) - 1)
                        if ses_addr == sas_addr:
                            NODE = 'A'
                            break

                    if (reg := re.search(HA_HARDWARE.XSERIES_NODEB.value, info)) is not None:
                        ses_addr = hex(int(reg.group(1), 16) - 1)
                        if ses_addr == sas_addr:
                            NODE = 'B'
                            break
                elif (reg := re.search(HA_HARDWARE.MSERIES_ENCLOSURE.value, info)) is not None:
                    # M-series hardware (Echowarp)
                    HARDWARE = 'ECHOWARP'
                    if reg.group(2) == 'p':
                        NODE = 'A'
                        break
                    elif reg.group(2) == 's':
                        NODE = 'B'
                        break

        return HARDWARE, NODE
