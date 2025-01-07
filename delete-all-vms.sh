#!/bin/bash

# List all VMs and iterate over them
for vm in $(sudo virsh list --all --name); do
    echo "Processing VM: $vm"

    # Attempt to shut down the VM gracefully
    echo "Shutting down VM: $vm"
    sudo virsh shutdown "$vm"
    sleep 5  # Wait for a few seconds to allow graceful shutdown
    # Retrieve and delete associated disk files
    echo "Retrieving disk paths for VM: $vm"
    disk_paths=$(sudo virsh domblklist "$vm" --details | awk '/disk/{print $4}')
    for disk in $disk_paths; do
        if [ -n "$disk" ] && [ -f "$disk" ]; then
            echo "Deleting disk: $disk"
            sudo rm -f "$disk"
        else
            echo "Disk not found or invalid: $disk"
        fi
    done
    # Forcefully destroy the VM if it's still running
    if [ "$(sudo virsh domstate "$vm")" == "running" ]; then
        echo "Forcing shutdown of VM: $vm"
        sudo virsh destroy "$vm"
    fi

    # Remove NVRAM configuration if it exists
    nvram_path=$(sudo virsh dumpxml "$vm" | grep -oP '(?<=<nvram>).*?(?=</nvram>)')
    if [ -n "$nvram_path" ]; then
        echo "Removing NVRAM file: $nvram_path"
        sudo rm -f "$nvram_path"
    fi

    # Undefine the VM to remove its configuration
    echo "Undefining VM: $vm"
    sudo virsh undefine "$vm" --nvram

    echo "Completed processing VM: $vm"
done

echo "All specified VMs and their associated disks have been processed."
