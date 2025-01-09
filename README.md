# pi-server
A remotely manageable server for Raspberry Pi 5, controlled from your terminal using `vm-manager.py`. This tool offers an efficient way to manage multiple virtual machines on Raspberry Pi devices, whether for personal projects or lightweight production deployments.

### For High-Seas Visitors!!!!!
this project was made with the help of ai(github copilot)

## Overview
`pi-server` is a lightweight API-based virtual machine manager designed specifically for Raspberry Pi devices. While it was originally created for personal use, it can be adapted for a production environment. It simplifies the management of virtual machines by providing a straightforward interface that can be accessed remotely.

## Quick Install
Get started with `pi-server` quickly by using the following command. The installation process is fully interactive:
```bash
bash -c "$(wget -qO- https://raw.githubusercontent.com/Cherry-Corporation/pi-server/refs/heads/main/install.sh)"
```

![Setup Image](https://github.com/user-attachments/assets/6e1cc639-562f-47d5-bf88-a8cdcdeb668a)

## Manual Setup
Keep in mind that i have probably missed a few steps so consider following install.sh.

If you prefer a manual setup, follow these detailed steps to get `pi-server` running:

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/Cherry-Corporation/pi-server.git
   cd pi-server
   ```
2. **Install Python and Pip:**
   Update your system and install the required packages:
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip
   ```
3. **Install FastAPI and Uvicorn:**
   Use pip to install FastAPI and Uvicorn:
   ```bash
   pip install fastapi uvicorn
   ```
4. **Install QEMU and Libvirt:**
   These packages are necessary for virtual machine management:
   ```bash
   sudo apt install qemu-system libvirt-clients libvirt-daemon-system virt-manager
   ```
5. **Run the Server:**
   Depending on the machine's role, run either the master or the slave server:
   - **Master Server:**
     ```bash
     python3 -m uvicorn master:app --host 0.0.0.0 --port 8000
     ```
   - **Slave Server:**
     ```bash
     python3 -m uvicorn slave:app --host 0.0.0.0 --port 8008
     ```
6. **Optional: Create a systemd Service:**
   For better usability, you can set up `pi-server` to start automatically on boot using systemd services.

## Setting Up Systemd Services
To ensure `pi-server` runs on boot, you can create and enable systemd services for both the master and slave servers.

### Master Service Configuration
Create a systemd service file for the master server by running:
```bash
sudo nano /etc/systemd/system/master.service
```
Add the following configuration:
```ini
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
```

### Slave Service Configuration
Similarly, create a systemd service file for the slave server:
```bash
sudo nano /etc/systemd/system/slave.service
```
Insert the following content:
```ini
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
```

### Enabling and Starting the Services
After creating the service files, reload the systemd configuration and enable the services to run on boot:
```bash
sudo systemctl daemon-reload
sudo systemctl enable master.service
sudo systemctl enable slave.service
sudo systemctl start master.service
sleep 1
sudo systemctl start slave.service
```

Verify that the services are running correctly by checking their status:
```bash
systemctl status master.service
systemctl status slave.service
```



---
Built for fun and learning! I will probably use it in my homelab tho.

