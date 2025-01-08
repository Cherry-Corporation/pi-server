#!/bin/bash

# Define color codes
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
RED='\033[1;31m'
CYAN='\033[1;36m'
RESET='\033[0m'

# Update and install dependencies
echo -e "${CYAN}Updating system and installing dependencies...${RESET}"
sudo apt update && sudo apt upgrade -y
sudo apt install -y git wget qemu-system libvirt-clients libvirt-daemon-system virt-manager python3-pip
pip install fastapi pydantic requests uvicorn httpx --break-system-packages

# Clone repository and navigate to it
echo -e "${CYAN}Cloning the pi-server repository...${RESET}"
git clone https://github.com/Cherry-Corporation/pi-server.git
cd pi-server

mkdir disks
mkdir vms

echo -e "${YELLOW}Undefining the default virtual network...${RESET}"
sudo virsh net-destroy default
sudo virsh net-undefine default

# Define the new NAT-based network using existing nat-network.xml
echo -e "${YELLOW}Defining a new NAT-based network using nat-network.xml...${RESET}"
sudo virsh net-define nat-network.xml
sudo virsh net-autostart nat-network
sudo virsh net-start nat-network

echo -e "${GREEN}Network setup complete.${RESET}"

# Function to setup master service
setup_master() {
  echo -e "${CYAN}Setting up Master service...${RESET}"
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
  echo -e "${GREEN}Master service setup complete.${RESET}"
}

# Function to setup slave service
setup_slave() {
  echo -e "${CYAN}Setting up Slave service...${RESET}"
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
  echo -e "${GREEN}Slave service setup complete.${RESET}"

  # Create VM only if slave is selected
  echo -e "${YELLOW}Downloading Alpine prebuilt disk image (180Mb)...${RESET}"
  cd disks
  wget https://github.com/Cherry-Corporation/pi-server/releases/download/v1.0.0/alpine.qcow2
  cd ..
  chmod +x restart.sh && ./restart.sh
  echo -e "${GREEN}Prebuilt disk download complete.${RESET}"
}

# Ask user
read -p "Will this machine be a Master or Slave? (master/slave): " ROLE
ROLE=${ROLE,,} # lowercase

if [[ "$ROLE" == "master" ]]; then
  setup_master
elif [[ "$ROLE" == "slave" ]]; then
  setup_slave
else
  echo -e "${RED}Invalid option. Please enter 'master' or 'slave'.${RESET}"
  exit 1
fi

sleep 1
sudo systemctl status "${ROLE}.service"

echo -e "${GREEN}Setup complete.${RESET}"
