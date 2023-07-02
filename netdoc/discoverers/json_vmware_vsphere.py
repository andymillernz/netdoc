"""Discovery task for VMware vSphere hosts via Python pyVmomi."""
__author__ = "Andrea Dainese"
__contact__ = "andrea@adainese.it"
__copyright__ = "Copyright 2023, Andrea Dainese"
__license__ = "GPLv3"

import json
from nornir_utils.plugins.functions import print_result
from pyVmomi import vim
from pyVim.connect import SmartConnect

from netdoc.schemas import discoverable, discoverylog


def api_query(
    details,
    host=None,
    username=None,
    password=None,
    verify_cert=True,
):  # pylint: disable=unused-argument
    """Get info via Python pyVmomi."""
    data = {
        "virtual_machines": [],
    }

    # Connect to vCenter
    srv_inst = SmartConnect(
        host=host,
        user=username,
        pwd=password,
        disableSslCertValidation=not verify_cert,
    )
    content = srv_inst.RetrieveContent()
    container = content.rootFolder
    recursive = True


    hosts_data = {}
    dvswitches_data = {}

    # Get hosts
    view_type = [vim.HostSystem]  # pylint: disable=c-extension-no-member
    hosts = list(content.viewManager.CreateContainerView(
        container, view_type, recursive
    ).view)

    # Get dvSwitches
    view_type = [vim.DistributedVirtualSwitch]  # pylint: disable=c-extension-no-member
    dvswitches = list(content.viewManager.CreateContainerView(
        container, view_type, recursive
    ).view)

    for host in hosts:
        host_data = {
            "id": str(host),
            "name": host.name,
            "cluster_id": str(host.parent),
            "cluster_name": host.parent.name,
            "vendor": host.hardware.systemInfo.vendor,
            "model": host.hardware.systemInfo.model,
            "status": host.summary.overallStatus,
            "management_ip": host.summary.managementServerIp,
            "product_name": host.summary.config.product.name,
            "product_fullname": host.summary.config.product.fullName,
            "vswitches": {},
            "portgroups": {},
            "vms": {},
            "nics": {},
        }
        
        # Get physical NICs
        for nic in host.config.network.pnic:
            nic_data = {
                "id": nic.key,
                "name": nic.device,
                "mac_address": nic.mac,
            }
            # Save NIC data
            host_data["nics"][nic_data.get("id")] = nic_data

        # Get vSwitches
        for vswitch in host.config.network.vswitch:
            vswitch_data = {
                "id": vswitch.key,
                "name": vswitch.name,
                "nics": [],
                "portgroups": [],
            }
            for nic in vswitch.pnic:
                # Save associated NIC IDs
                vswitch_data["nics"].append(str(nic))
            for portgroup in vswitch.portgroup:
                # Save associated portgroup IDs
                vswitch_data["portgroups"].append(str(portgroup))
            # Save vSwitch data
            host_data["vswitches"][vswitch_data.get("id")] = vswitch_data

        # Get VMs
        for vm in host.vm:
            vm_data = {
                "id": str(vm),
                "name": vm.name,
                "status": vm.overallStatus,
                "power_state": vm.runtime.powerState,
                "nics": [],
                "guest": {
                    "type_id": vm.config.guestId,
                    "type_name": vm.config.guestFullName,
                    "hostname": vm.guest.hostName,
                    "guest_address": vm.guest.ipAddress,
                },
            }
            for hardware in vm.config.hardware.device:
                try:
                    hardware.macAddress
                except AttributeError:
                    # Not a network adapter
                    continue
                nic_data = {
                    "mac_address": str(hardware.macAddress),
                    "label": str(hardware.deviceInfo.label),
                    "connected": str(hardware.connectable.connected),
                }
                if hasattr(hardware.backing, "port"):
                    # Connected to dvSwitch
                    nic_data["switch_type"] = "dvswitch"
                    nic_data["portgroup_id"] = hardware.backing.port.portgroupKey
                    nic_data["portgroup_name"] = None
                    nic_data["port"] = hardware.backing.port.portKey
                else:
                    # Connected to vSwitch
                    nic_data["switch_type"] = "vswitch"
                    nic_data["portgroup_id"] = str(hardware.backing.network)
                    nic_data["portgroup_name"] = hardware.backing.deviceName
                    nic_data["port"] = None
                # Save interface data
                vm_data["nics"].append(nic_data)
            # Save VM data
            host_data["vms"][vm_data.get("id")] = vm_data

        # Get vSwitch portgrouops
        for portgroup in host.config.network.portgroup:
            # vSwitch portgroups
            portgroup_data = {
                "id": portgroup.key,
                "name": portgroup.spec.name,
                "vswitch_id": str(portgroup.vswitch),
                "vswitch_name": portgroup.spec.vswitchName,
                "vswitch_type": "vswitch",
                "vlan": portgroup.spec.vlanId,
            }
            # Save portgroup data
            host_data["portgroups"][portgroup_data.get("id")] = portgroup_data

        # Save host data
        hosts_data[host_data.get("id")] = host_data

    # Get dvSwitches
    for dvswitch in dvswitches:
        dvswitch_data = {
            "id": str(dvswitch),
            "name": dvswitch.name,
            "status": dvswitch.overallStatus,
            "portgroups": {},
        }
        for portgroup in dvswitch.portgroup:
            porgroup_data = {
                "id": str(portgroup),
                "name": portgroup.name,
                "vlan": None,
            }
            if hasattr(portgroup, "vlanId"):
                # Save VLAN
                portgroup_data["vlan"] = portgroup.config.defaultPortConfig.vlan.vlanId
            # Save portgroup data
            dvswitch_data["portgroups"][portgroup_data.get("id")] = portgroup_data
        # Save dvSwitch data
        dvswitches_data[dvswitch_data.get("id")] = dvswitch_data

    return {
        "hosts": hosts_data,
        "dvswitches": dvswitches_data,
    }


def discovery(nrni):
    """Discovery VMware vSphere devices."""
    host_list = []
    failed_host_list = []

    def multiple_tasks(task):
        """Define commands (in order) for the playbook."""
        supported = True
        order = 0
        template = None
        command = "pyVmomi"
        verify_cert = task.host.dict().get("data").get("verify_cert")
        details = {
            "command": command,
            "template": template if template else command,
            "order": order,
            "enable": False,
            "supported": supported,
            "verify_cert": verify_cert,
        }

        task.run(
            task=api_query,
            name=json.dumps(details),
            host=task.host.hostname,
            username=task.host.dict().get("username"),
            password=task.host.dict().get("password"),
            verify_cert=verify_cert,
        )

    # Run the playbook
    aggregated_results = nrni.run(task=multiple_tasks)

    # Print the result
    print_result(aggregated_results)

    # Save outputs and define additional commands
    for (
        key,  # pylint: disable=unused-variable
        multi_result,
    ) in aggregated_results.items():
        # MultiResult is an array of Result
        for result in multi_result:
            if result.name == "multiple_tasks":
                # Skip MultipleTask
                continue

            address = result.host.dict().get("hostname")
            discoverable_o = discoverable.get(address)
            details = json.loads(result.name)
            discoverylog.create(
                command=details.get("command"),
                discoverable_id=discoverable_o.id,
                raw_output=json.dumps(result.result),
                template=details.get("template"),
                order=details.get("order"),
                details=details,
            )

            # Tracking hosts and failed hosts
            if discoverable_o.address not in host_list:
                host_list.append(discoverable_o.address)
            if result.failed and discoverable_o.address not in failed_host_list:
                failed_host_list.append(discoverable_o.address)

    # Mark as discovered
    for address in host_list:
        if address not in failed_host_list:
            discoverable_o = discoverable.get(address, discovered=True)
            discoverable.update(discoverable_o)
