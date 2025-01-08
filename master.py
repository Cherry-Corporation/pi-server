import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from threading import Lock
import httpx
from typing import List, Tuple

app = FastAPI()
lock = Lock()

# Models
class VMRequest(BaseModel):
    name: str
    memory: int
    vcpus: int
    disk_size: int
    os: str

class NodeInfo(BaseModel):
    node_name: str
    node_url: str


class PortForwardRequest(BaseModel):
    vm_name: str
    port_mappings: List[Tuple[int, int]]

class ClusterStatus(BaseModel):
    status: Dict[str, dict]

# keep track of registered slave nodes
registered_nodes: List[Dict[str, str]] = []

@app.post("/register")
async def register_node(node_info: NodeInfo):
    """Handle the registration of new nodes."""
    with lock:
        if node_info.node_url in [node['node_url'] for node in registered_nodes]:
            raise HTTPException(status_code=400, detail="Node already registered.")
        registered_nodes.append(node_info.dict())
    return {"message": f"Node {node_info.node_name} registered successfully."}

@app.get("/nodes")
async def get_registered_nodes():
    """Fetch the list of registered nodes."""
    return registered_nodes

@app.post("/create_vm")
async def create_vm(vm_request: VMRequest):
    """Distribute VM creation across the cluster."""
    if not registered_nodes:
        raise HTTPException(status_code=500, detail="No active nodes available in the cluster.")
    statuses = []
    async with httpx.AsyncClient() as client:
        for node in registered_nodes:
            try:
                response = await client.get(f"{node['node_url']}/status", timeout=5)
                if response.status_code == 200:
                    statuses.append((node['node_url'], response.json()))
            except httpx.RequestError:
                statuses.append((node['node_url'], {"error": "Node unreachable"}))
    valid_nodes = [status for status in statuses if "error" not in status[1]]

    if not valid_nodes:
        raise HTTPException(status_code=500, detail="No active nodes available with sufficient resources.")

    # Sort nodes by free memory and CPU count (descending order)
    def get_sort_key(node):
        node_data = node[1]
        resources = node_data.get("resources", {})
        free_memory = resources.get("free_memory", 0)
        cpu_count = resources.get("cpu_count", 0)
        return (free_memory, cpu_count)

    valid_nodes.sort(key=get_sort_key, reverse=True)
    best_node = valid_nodes[0][0]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{best_node}/create_vm", json=vm_request.dict(), timeout=120)
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=500, detail=f"Failed to create VM: {response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Error communicating with node {best_node}: {e}")

@app.post("/port_forward")
async def port_forward(port_request: PortForwardRequest):
    """
    Request port forwarding for a specific VM.
    """
    async with httpx.AsyncClient() as client:
        for node in registered_nodes:
            try:
                response = await client.get(f"{node['node_url']}/vms", timeout=5)
                if response.status_code == 200:
                    vms = response.json().get("vms", [])
                    if port_request.vm_name in vms:
                        forward_response = await client.post(
                            f"{node['node_url']}/port_forward",
                            json={"vm_name": port_request.vm_name, "port_mappings": port_request.port_mappings},
                            timeout=3
                        )
                        if forward_response.status_code == 200:
                            return forward_response.json()
                        else:
                            raise HTTPException(
                                status_code=500,
                                detail=f"Failed to forward port: {forward_response.text}"
                            )
            except httpx.RequestError as e:
                continue

    raise HTTPException(status_code=404, detail=f"VM {port_request.vm_name} not found in the cluster.")

@app.get("/status", response_model=ClusterStatus)
async def cluster_status():
    """Get the status of the entire cluster."""
    cluster_status = {}

    async with httpx.AsyncClient() as client:
        for node in registered_nodes:
            node_url = node['node_url']
            try:
                response = await client.get(f"{node_url}/status", timeout=5)
                if response.status_code == 200:
                    cluster_status[node_url] = response.json()
                else:
                    cluster_status[node_url] = {"error": f"Failed to fetch status: {response.text}"}
            except httpx.RequestError as e:
                cluster_status[node_url] = {"error": f"Connection failed: {str(e)}"}
            except Exception as e:
                cluster_status[node_url] = {"error": f"Unexpected error: {str(e)}"}

    return {"status": cluster_status}

class VMNameRequest(BaseModel):
    vm_name: str

@app.post("/shutdown_vm")
async def shutdown_vm(vm_request: VMNameRequest):
    """Shut down an existing virtual machine."""
    vm_name = vm_request.vm_name
    node_to_shutdown = await find_vm_node(vm_name)

    if not node_to_shutdown:
        raise HTTPException(status_code=404, detail=f"VM '{vm_name}' not found in any node.")

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{node_to_shutdown['node_url']}/shutdown_vm", json={"vm_name": vm_name})
        if response.status_code == 200:
            return {"message": f"VM '{vm_name}' is shutting down."}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to shut down VM on node: {response.text}")


@app.post("/start_vm")
async def start_vm(vm_request: VMNameRequest):
    """Start an existing virtual machine."""
    vm_name = vm_request.vm_name
    node_to_start = await find_vm_node(vm_name)

    if not node_to_start:
        raise HTTPException(status_code=404, detail=f"VM '{vm_name}' not found in any node.")

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{node_to_start['node_url']}/start_vm", json={"vm_name": vm_name})
        if response.status_code == 200:
            return {"message": f"VM '{vm_name}' is starting."}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to start VM on node: {response.text}")


async def find_vm_node(vm_name: str):
    """Find the node where the VM is located."""
    async with httpx.AsyncClient() as client:
        for node in registered_nodes:
            response = await client.get(f"{node['node_url']}/vms", timeout=5)
            if response.status_code == 200:
                vms = response.json().get("vms", [])
                if vm_name in vms:
                    return node
    return None

@app.get("/list_vms")
async def list_all_vms():
    """List all virtual machines across the cluster and their respective nodes."""
    vms_on_nodes = {}

    async with httpx.AsyncClient() as client:
        for node in registered_nodes:
            node_name = node.get("node_name", "unknown")
            node_url = node.get("node_url", "unknown")
            try:
                response = await client.get(f"{node_url}/vms", timeout=5)
                response.raise_for_status()
                vms = response.json().get("vms", [])
                vms_on_nodes[node_name] = vms
            except httpx.RequestError as e:
                vms_on_nodes[node_name] = f"Error: {str(e)}"
            except Exception as e:
                vms_on_nodes[node_name] = f"Unexpected error: {str(e)}"

    return {"vms_on_nodes": vms_on_nodes}
