# pi-server
remotely managable from you terminal with vm-manager.py
# a pretty cool api based vm manager for rpi 5 

built for my own use prob with some major adjustments would work in production.


# Quick Install

`bash -c "$(wget -qO- https://raw.githubusercontent.com/Cherry-Corporation/pi-server/refs/heads/main/install.sh)"`

![{8350C7A8-54ED-4999-B377-DE13128ED7E3}](https://github.com/user-attachments/assets/6e1cc639-562f-47d5-bf88-a8cdcdeb668a)

# setup 
- clone the repo
- install python and python3-pip
- do pip install fastapi
- then sudo apt install qemu-system libvirt-clients libvirt-daemon-system virt-manager
- then run the slave or the master depending on what machine it is
- or even better create a systemctl service on boot like i did

# Notes
cat /etc/systemd/system/master.service
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

cat /etc/systemd/system/slave.service
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

then reload with: 
sudo systemctl daemon-reload
sudo systemctl enable master.service
sudo systemctl enable slave.service
sudo systemctl start master.service
sleep 1
sudo systemctl start slave.service
systemctl status master.service
systemctl status slave.service
