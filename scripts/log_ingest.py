"""Reparse all DiscoveryLogs.

Usage:
/opt/netbox/venv/bin/python3 /opt/netbox/netbox/manage.py shell < log_ingest.py
"""
from netdoc.models import DiscoveryLog
from netdoc.utils import log_ingest

FILTERS = ["172.25.82.50"]  # List of discoverable IP addresses
FILTERS = []

LOGS = [2, 4, 19]  # List of log IDs to be ingested
LOGS = [2296]

COMMAND = "show mac address-table"  # Command to be parsed
COMMAND = ""

STOP_ON_ERROR = True

REINGEST = False

# Don't edit below this line

logs = DiscoveryLog.objects.filter(parsed=True).order_by("order")
if FILTERS:
    logs = logs.filter(discoverable__address__in=FILTERS)
if not REINGEST:
    logs = logs.filter(ingested=False)
if LOGS:
    logs = logs.filter(id__in=LOGS)
if COMMAND:
    logs = logs.filter(command=COMMAND)

for log in logs:
    print(
        f"Ingesting log {log.id} with command {log.command} on device {log.discoverable}... ",
        end="",
    )
    try:
        log_ingest(log)
        print("done")
        log.ingested = True
        log.save()
    except Exception:
        print("failed")
        if STOP_ON_ERROR:
            raise
