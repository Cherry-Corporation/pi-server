#!/bin/bash

# Update and install dependencies
echo "Updating system and installing dependencies..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y git wget qemu-system libvirt-clients libvirt-daemon-system virt-manager python3-pip
pip install fastapi pydantic requests uvicorn httpx  --break-system-packages

# Clone repository and navigate to it
echo "Cloning the pi-server repository..."
git clone https://github.com/Cherry-Corporation/pi-server.git
cd pi-server

mkdir disks
mkdir vms
mkdir isos


echo "Undefining the default virtual network..."
sudo virsh net-destroy default
sudo virsh net-undefine default

# Define the new NAT-based network using existing nat-network.xml
echo "Defining a new NAT-based network using nat-network.xml..."
sudo virsh net-define nat-network.xml
sudo virsh net-autostart nat-network
sudo virsh net-start nat-network

echo "Network setup complete."

# Function to setup master service
setup_master() {
  echo "Setting up Master service..."
  sudo tee /etc/systemd/system/master.service > /dev/null <<EOF
[Unit]
Description=Master FastAPI Server
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/pi-server
ExecStart=/usr/bin/python3 -m uvicorn master:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF
  sudo systemctl daemon-reload
  sudo systemctl enable master.service
  sudo systemctl start master.service
  echo "Master service setup complete."
}

# Function to setup slave service
setup_slave() {
  echo "Setting up Slave service..."
  sudo tee /etc/systemd/system/slave.service > /dev/null <<EOF
[Unit]
Description=Slave FastAPI Server
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/pi-server
ExecStart=/usr/bin/python3 -m uvicorn slave:app --host 0.0.0.0 --port 8008
Restart=always

[Install]
WantedBy=multi-user.target
EOF
  sudo systemctl daemon-reload
  sudo systemctl enable slave.service
  sudo systemctl start slave.service
  echo "Slave service setup complete."
}

# Ask user
read -p "Will this machine be a Master or Slave? (master/slave): " ROLE
ROLE=${ROLE,,} # lowercase

if [[ "$ROLE" == "master" ]]; then
  setup_master
elif [[ "$ROLE" == "slave" ]]; then
  setup_slave
else
  echo "Invalid option. Please enter 'master' or 'slave'."
  exit 1
fi


sleep 1
sudo systemctl status "${ROLE}.service"
cd isos
wget https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/aarch64/alpine-virt-3.21.0-aarch64.iso
sudo virt-install   --name alpine_vm_template   --memory 1024   --vcpus 2   --disk size=10   --os-variant generic   --cdrom alpine-virt-3.21.0-aarch64.iso   --network network=nat-network   --graphics none   --console pty,target_type=serial --boot firmware=efi,firmware.feature0.enabled=no,firmware.feature0.name=secure-boot

echo "Setup complete."
