"""Ingestor for netmiko_cisco_ios_show_inventory."""
__author__ = "Andrea Dainese"
__contact__ = "andrea@adainese.it"
__copyright__ = "Copyright 2022, Andrea Dainese"
__license__ = "GPLv3"

from netdoc.schemas import device

# See: https://github.com/netbox-community/devicetype-library
MANUFACTURER = "Cisco"
DEFAULT_MODEL = "Cisco Unknown device"


def ingest(log):
    """Processing parsed output."""
    device_o = log.discoverable.device
    part_number = DEFAULT_MODEL
    part_serial_number = None

    for item in log.parsed_output:
        # See https://github.com/networktocode/ntc-templates/tree/master/tests/cisco_ios/show_inventory # pylint: disable=line-too-long
        part_description = item.get("name")

        if "chassis" in part_description.lower():
            # Chassis model and Serial Number
            part_serial_number = item.get("sn")
            part_number = item.get("pid")
            break
    # get details from the first entry if it's not a "chassis"
    if part_number is DEFAULT_MODEL:
        item = log.parsed_output[0]
        if item.get("name") and item.get("sn") and item.get("pid"):
            part_description = item.get("name")
            part_serial_number = item.get("sn")
            part_number = item.get("pid")

    device.update(
        device_o,
        serial=part_serial_number,
        manufacturer=MANUFACTURER,
        model_keyword=part_number,
    )

    # Update the log
    log.ingested = True
    log.save()
