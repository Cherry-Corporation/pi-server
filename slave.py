import os
import shutil
import subprocess
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import time
from typing import List, Optional
import logging
import socket


log_file_path = "/home/pi/pi-server/node_log.log"


logger = logging.getLogger("NodeLogger")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(log_file_path)
file_handler.setLevel(logging.INFO)


console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Constants
DISK_FOLDER = "/home/pi/pi-server/disks"
VM_DISKS_FOLDER = "/home/pi/pi-server/vms"
MASTER_URL = "http://pi1.local:8000/register"
OS_IMAGES = {
    "alpine": "alpine.qcow2",
    "ubuntu": "ubuntu.qcow2",
    "debian": "debian.qcow2",
}

# Start FastAPI stuff
app = FastAPI()

class VMRequest(BaseModel):
    name: str
    memory: int
    vcpus: int
    disk_size: int
    os: str
    port_forwards: Optional[List[int]] = None

class PortForwardRequest(BaseModel):
    vm_name: str
    host_port: int
    target_port: int

class VMNameRequest(BaseModel):
    vm_name: str



def get_system_resources():
    """Retrieve system resources."""
    try:
        total_memory = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") // (1024 ** 2)
        free_memory = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_AVPHYS_PAGES") // (1024 ** 2)
        cpu_count = os.cpu_count()
        return {"total_memory": total_memory, "free_memory": free_memory, "cpu_count": cpu_count}
    except Exception as e:
        logger.error(f"Error fetching system resources: {e}")
        raise

def vm_exists(name: str) -> bool:
    """Check if a VM with the given name exists."""
    try:
        result = subprocess.run(
            ["sudo", "virsh", "list", "--all"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            return any(name in line.split() for line in result.stdout.splitlines())
        return False
    except subprocess.SubprocessError as e:
        logger.error(f"Error checking VM existence: {e}")
        return False

def get_vm_ip(vm_name: str) -> Optional[str]:
    """Retrieve the IP address of a running VM using ARP."""
    try:
        result = subprocess.run(
            ["sudo", "virsh", "domiflist", vm_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            logger.error(f"Error getting VM details: {result.stderr.strip()}")
            return None

        mac_address = None
        for line in result.stdout.splitlines():
            columns = line.split()
            if len(columns) >= 5 and columns[0] != "Interface":
                mac_address = columns[4]  # The MAC address is in the flippin 5th column!!!!!
                break

        if not mac_address:
            logger.error(f"Failed to retrieve MAC address for VM: {vm_name}")
            return None

        logger.info(f"MAC address for VM '{vm_name}' is {mac_address}")

        # thanks god i found this!!!!!!!
        result = subprocess.run(
            ["sudo", "arp", "-n"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            logger.error(f"Error fetching ARP table: {result.stderr.strip()}")
            return None

        #get my ippppppppp
        for line in result.stdout.splitlines():
            columns = line.split()
            if len(columns) >= 3 and mac_address.lower() == columns[2].lower():
                logger.info(f"IP address for VM '{vm_name}' is {columns[0]}")
                return columns[0]  # IP address should be in the first column i think maybe

        logger.error(f"Failed to find IP address for MAC: {mac_address}")
        return None
    except Exception as e:
        logger.error(f"Exception while retrieving VM IP by ARP: {e}")
        return None


def setup_port_forwarding(vm_ip: str, ports: List[int]) -> None:
    """Set up port forwarding from host to VM."""
    for port in ports:
        try:
            subprocess.run(
                [
                    "sudo", "iptables", "-t", "nat", "-A", "PREROUTING",
                    "-p", "tcp", "--dport", str(port),
                    "-j", "DNAT", f"--to-destination", f"{vm_ip}:{port}"
                ],
                check=True
            )
            subprocess.run(
                [
                    "sudo", "iptables", "-A", "FORWARD",
                    "-d", vm_ip, "-p", "tcp", "--dport", str(port),
                    "-j", "ACCEPT"
                ],
                check=True
            )
            logger.info(f"Port forwarding set for port {port} -> {vm_ip}:{port}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to set up port forwarding for port {port}: {e}")

@app.on_event("startup")
async def register_node():
    """Register this node with the master server on app startup."""
    try:
        resources = get_system_resources()
        local_ip = socket.gethostbyname(socket.gethostname())
        node_info = {
            "node_name": os.uname().nodename,
            "cpu_count": resources["cpu_count"],
            "total_memory": resources["total_memory"],
            "free_memory": resources["free_memory"],
            "node_url": f"http://{local_ip}:8008"
        }

        response = requests.post(MASTER_URL, json=node_info)
        if response.status_code == 200:
            logger.info("Node registered successfully with the master server.")
        else:
            logger.error(f"Failed to register node: {response.text}")
    except Exception as e:
        logger.error(f"Error during node registration: {e}")

@app.get("/status")
async def status():
    """Provide status of this slave node."""
    try:
        resources = get_system_resources()
        return {"status": "active", "resources": resources}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching status: {e}")

@app.post("/create_vm")
async def create_vm(vm_request: VMRequest):
    """Endpoint to create a new virtual machine."""
    try:
        # Log the VM creation request for debuggingggggg
        logger.info(f"Received request to create VM: {vm_request.name} with OS: {vm_request.os}, Memory: {vm_request.memory}MB, VCPUs: {vm_request.vcpus}, Disk size: {vm_request.disk_size}GB")

        os_name = vm_request.os.lower()
        if os_name not in OS_IMAGES:
            raise HTTPException(status_code=400, detail=f"Unsupported OS: {os_name}")
        
        # Check if VM already exists so you don't mess up stuff
        if vm_exists(vm_request.name):
            raise HTTPException(status_code=400, detail=f"VM '{vm_request.name}' already exists.")
        
        logger.info(f"VM '{vm_request.name}' does not exist. Proceeding with creation.")

        # Prepare disk paths
        prebuilt_disk_path = os.path.join(DISK_FOLDER, OS_IMAGES[os_name])
        vm_folder = os.path.join(VM_DISKS_FOLDER, vm_request.name)
        target_disk_path = os.path.join(vm_folder, OS_IMAGES[os_name])

        logger.info(f"Creating folder for VM disk at: {vm_folder}")
        os.makedirs(vm_folder, exist_ok=True)

        # Log  log log
        logger.info(f"Copying disk image from {prebuilt_disk_path} to {target_disk_path}")
        shutil.copy(prebuilt_disk_path, target_disk_path)
        logger.info(f"Disk image copied successfully to {target_disk_path}")

        # command to create vm(took ages to get why this was not working turns out i needed to add a super simple boot flag wich disabled secure boot)!!!!!!!!
        command = [
            "sudo", "virt-install",
            "--name", vm_request.name,
            "--memory", str(vm_request.memory),
            "--vcpus", str(vm_request.vcpus),
            "--disk", f"path={target_disk_path},size={vm_request.disk_size}",
            "--os-variant", "generic",
            "--network", "network=nat-network",
            "--graphics", "none",
            "--console", "pty,target_type=serial",
            "--boot", "firmware=efi,firmware.feature0.enabled=no,firmware.feature0.name=secure-boot",
            "--import",
            "--noautoconsole"
        ]
        logger.info(f"Running command to create VM: {' '.join(command)}")
        subprocess.run(command, check=True)

        logger.info(f"VM '{vm_request.name}' created successfully.")
        
        # Could be done better but i do not hav the time
        logger.info(f"Waiting for VM '{vm_request.name}' to initialize...")
        time.sleep(60)

        # get my ip again
        vm_ip = get_vm_ip(vm_request.name)
        if not vm_ip:
            raise HTTPException(status_code=500, detail="Failed to retrieve VM IP address.")
        
        logger.info(f"VM '{vm_request.name}' IP address: {vm_ip}")
        
        if vm_request.port_forwards:
            logger.info(f"Setting up port forwarding for VM '{vm_request.name}' with ports: {vm_request.port_forwards}")
            setup_port_forwarding(vm_ip, vm_request.port_forwards)
        
        return {
            "message": f"VM '{vm_request.name}' created successfully.",
            "ip_address": vm_ip,
            "port_forwards": vm_request.port_forwards or []
        }
    
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during VM creation: {e.stderr.strip()}")
        raise HTTPException(status_code=500, detail=f"Error during VM creation: {e.stderr.strip()}")
    
    except Exception as e:
        logger.error(f"Unexpected error during VM creation: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


@app.post("/shutdown_vm")
async def shutdown_vm(request: VMNameRequest):
    """Shut down an existing virtual machine."""
    vm_name = request.vm_name
    try:
        if not vm_exists(vm_name):
            raise HTTPException(status_code=404, detail=f"VM '{vm_name}' not found.")
        
        subprocess.run(["sudo", "virsh", "shutdown", vm_name], check=True, stderr=subprocess.PIPE, text=True)
        return {"message": f"VM '{vm_name}' is shutting down."}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error shutting down VM: {e.stderr}")

@app.post("/start_vm")
async def start_vm(request: VMNameRequest):
    """Start an existing virtual machine."""
    vm_name = request.vm_name
    try:
        if not vm_exists(vm_name):
            raise HTTPException(status_code=404, detail=f"VM '{vm_name}' not found.")
        
        subprocess.run(["sudo", "virsh", "start", vm_name], check=True, stderr=subprocess.PIPE, text=True)
        return {"message": f"VM '{vm_name}' is starting."}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error starting VM: {e.stderr}")

@app.post("/port_forward")
async def port_forward(port_request: PortForwardRequest):
    """
    Set up port forwarding for a specific VM.
    """
    try:
        if not vm_exists(port_request.vm_name):
            raise HTTPException(status_code=404, detail=f"VM {port_request.vm_name} not found.")

        vm_ip = get_vm_ip(port_request.vm_name)
        if not vm_ip:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve IP address for VM {port_request.vm_name}.")
        try:
            setup_port_forwarding(vm_ip, [port_request.host_port, port_request.target_port])

            logger.info(
                f"Port forwarding set up: Host port {port_request.host_port} -> VM {port_request.vm_name} port {port_request.target_port}"
            )
        except Exception as e:
            logger.error(f"Failed to set up port forwarding: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to set up port forwarding: {e}")

        return {
            "message": f"Port forwarding set up: Host port {port_request.host_port} -> VM {port_request.vm_name} port {port_request.target_port}",
            "vm_name": port_request.vm_name,
            "host_port": port_request.host_port,
            "target_port": port_request.target_port,
            "vm_ip": vm_ip
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

@app.get("/vms")
async def get_vms():
    """Get a list of all virtual machines."""
    try:
        # listttt
        result = subprocess.run(
            ["sudo", "virsh", "list", "--all"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail="Failed to fetch VM list.")
        
        vms = []
        for line in result.stdout.splitlines():
            columns = line.split()
            if columns and len(columns) > 1:
                vms.append(columns[1])
                
        return {"vms": vms}
    except subprocess.SubprocessError as e:
        logger.error(f"Error fetching VM list: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching VM list: {e}")
