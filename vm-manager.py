import click
import requests
import json

MASTER_URL = "http://pi1.local:8000"

@click.group()
def cli():
    "A CLI tool to manage VMs via the master node."
    pass

def print_success(message):
    "Print a success message in green."
    click.echo(click.style(message, fg="green"))

def print_error(message):
    "Print an error message in red."
    click.echo(click.style(message, fg="red"))

def print_info(message):
    "Print an informational message in cyan."
    click.echo(click.style(message, fg="cyan"))

@click.command()
@click.option('--name', required=True, help="Name of the VM.")
@click.option('--memory', required=True, type=int, help="Memory for the VM in MB.")
@click.option('--vcpus', required=True, type=int, help="Number of vCPUs for the VM.")
@click.option('--disk-size', required=True, type=int, help="Disk size for the VM in GB.")
@click.option('--os', required=True, type=str, help="Operating system for the VM (e.g., alpine, ubuntu, debian).")
@click.option('--ports', multiple=True, type=int, help="Host ports to forward to the VM. Multiple values are allowed.")
def create_vm(name, memory, vcpus, disk_size, os, ports):
    "Create a new virtual machine."
    payload = {
        "name": name,
        "memory": memory,
        "vcpus": vcpus,
        "disk_size": disk_size,
        "os": os,
        "port_forwards": list(ports) if ports else []
    }
    try:
        response = requests.post(f"{MASTER_URL}/create_vm", json=payload)
        response.raise_for_status()
        data = response.json()

        message = data.get("message", "VM created successfully.")
        ip_address = data.get("ip_address", "unknown")
        port_forwards = data.get("port_forwards", [])

        # Display the VM creation stuff
        print_success(message)
        print_info(f"IP Address: {ip_address}")
        if port_forwards:
            print_info("Port Forwards:")
            for forward in port_forwards:
                print_info(f"- {forward}")
        else:
            print_info("No port forwards configured.")
    except requests.RequestException as e:
        print_error(f"Error: {e}")
        if hasattr(response, 'text'):
            print_error(f"Response content: {response.text}")

@click.command()
@click.argument('vm_name')
def shutdown_vm(vm_name):
    "Shut down an existing VM."
    try:
        response = requests.post(f"{MASTER_URL}/shutdown_vm", json={"vm_name": vm_name})
        response.raise_for_status()
        print_success(f"VM '{vm_name}' shut down successfully.")
    except requests.RequestException as e:
        print_error(f"Error: {e}")

@click.command()
@click.argument('vm_name')
def start_vm(vm_name):
    "Start an existing VM."
    try:
        response = requests.post(f"{MASTER_URL}/start_vm", json={"vm_name": vm_name})
        response.raise_for_status()
        print_success(f"VM '{vm_name}' started successfully.")
    except requests.RequestException as e:
        print_error(f"Error: {e}")

@click.command()
@click.option('--vm-name', required=True, help="Name of the VM.")
@click.option('--host-port', required=True, type=int, help="Host port to forward.")
@click.option('--target-port', required=True, type=int, help="Target port on the VM.")
def port_forward(vm_name, host_port, target_port):
    "Set up port forwarding for a VM."
    payload = {
        "vm_name": vm_name,
        "host_port": host_port,
        "target_port": target_port
    }
    try:
        response = requests.post(f"{MASTER_URL}/port_forward", json=payload)
        response.raise_for_status()
        print_success(f"Port forwarding set up for VM '{vm_name}': {host_port} -> {target_port}.")
    except requests.RequestException as e:
        print_error(f"Error: {e}")


@click.command()
def cluster_status():
    "Fetch the status of the cluster."
    try:
        response = requests.get(f"{MASTER_URL}/status")
        response.raise_for_status()
        data = response.json()
        for node, status in data.get('status', {}).items():
            if "error" in status:
                print_error(f"Node {node}: {status['error']}")
            else:
                print_info(f"Node {node}: {status}")
    except requests.RequestException as e:
        print_error(f"Error: {e}")

@click.command()
def list_nodes():
    "List all registered nodes."
    try:
        response = requests.get(f"{MASTER_URL}/nodes")
        response.raise_for_status()
        nodes = response.json()
        if nodes:
            print_info("Registered nodes:")
            for node in nodes:
                click.echo(f"- {node.get('node_name', 'unknown')} ({node.get('node_url', 'unknown')})")
        else:
            print_info("No nodes are currently registered.")
    except requests.RequestException as e:
        print_error(f"Error: {e}")
@click.command()
def list_vms():
    """List all virtual machines across the cluster and the nodes they are running on."""
    try:
        response = requests.get(f"{MASTER_URL}/list_vms")
        response.raise_for_status()
        data = response.json()

        vms_on_nodes = data.get("vms_on_nodes", {})
        if not vms_on_nodes:
            print_info("No VMs found in the cluster.")
            return
        
        print_info("List of VMs across the cluster:")
        for node, vms in vms_on_nodes.items():
            click.echo(f"- {node}:")
            # workaround when i have time i need to fix
            filtered_vms = [vm for vm in vms if vm != "Name"]
            if filtered_vms:
                for vm in filtered_vms:
                    click.echo(f"  * {vm}")
            else:
                click.echo("  (No valid VMs found)")

    except requests.RequestException as e:
        print_error(f"Error: {e}")
    except Exception as e:
        print_error(f"Unexpected error: {e}")

# Add commands to my cli vm manager and hopefully it will finally work
task_list = [
    create_vm,
    shutdown_vm,
    start_vm,
    port_forward,
    cluster_status,
    list_nodes,
    list_vms
]


for task in task_list:
    cli.add_command(task)

if __name__ == "__main__":
    cli()
