#!/bin/bash

# color codes
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
RED='\033[1;31m'
CYAN='\033[1;36m'
RESET='\033[0m'

# Update
echo -e "${CYAN}Updating system and installing dependencies...${RESET}"
sudo apt update && sudo apt upgrade -y
sudo apt install -y git wget qemu-system libvirt-clients libvirt-daemon-system virt-manager python3-pip
pip install fastapi pydantic requests uvicorn httpx --break-system-packages

# clone repo
echo -e "${CYAN}Cloning the pi-server repository...${RESET}"
git clone https://github.com/Cherry-Corporation/pi-server.git
cd pi-server


current_user=$(whoami)
home_dir=$(eval echo ~$current_user)

sudo touch "$home_dir/pi-server/node_log.log"

sudo chown pi:pi "$home_dir/pi-server/node_log.log"
sudo chmod 664 "$home_dir/pi-server/node_log.log"

mkdir -p "$home_dir/pi-server/disks"
mkdir -p "$home_dir/pi-server/vms"

sudo chmod a+x "$home_dir"

sudo chown -R pi:pi "$home_dir/pi-server"
sudo chmod -R 755 "$home_dir/pi-server"

sudo chown libvirt-qemu:libvirt-qemu "$home_dir/pi-server/"



echo -e "${YELLOW}Undefining the default virtual network...${RESET}"
sudo virsh net-destroy default
sudo virsh net-undefine default

# networking
echo -e "${YELLOW}Defining a new NAT-based network using nat-network.xml...${RESET}"
sudo virsh net-define nat-network.xml
sudo virsh net-autostart nat-network
sudo virsh net-start nat-network

echo -e "${GREEN}Network setup complete.${RESET}"


setup_master() {
  echo -e "${CYAN}Setting up Master service...${RESET}"

  # Setup the master service
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

  # Print the current master URL for clients to connect
  IP_ADDRESS=$(hostname -I | awk '{print $1}')
  echo -e "${CYAN}Master is running on: http://$IP_ADDRESS:8000${RESET}"

  sleep 1
  sudo systemctl status master.service
}

# setup slave service
setup_slave() {
  echo -e "${CYAN}Setting up Slave service...${RESET}"

  read -p "Enter the MASTER_URL of the master machine (e.g. http://<master-ip>:8000/register): " MASTER_URL
  echo -e "${CYAN}Master URL set to: $MASTER_URL${RESET}"

  echo -e "${CYAN}Updating MASTER_URL in slave.py...${RESET}"
  sudo sed -i "s|MASTER_URL = .*|MASTER_URL = \"$MASTER_URL\"|" /home/pi/pi-server/slave.py
  echo -e "${GREEN}MASTER_URL in slave.py updated successfully.${RESET}"

  # Setup the slave service
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
