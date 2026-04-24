# Jetson Orin Nano — Setup Guide

SSH access, remote desktop, and project deployment.

---

## 1. First boot — find the Jetson's IP

Connect the Jetson to the same network as your PC (Ethernet recommended for stability).

### Option A — From the Jetson directly (if you have a screen + keyboard)
```bash
ip a | grep "inet " | grep -v 127
# Look for something like: inet 192.168.1.42/24
hostname -I   # quicker
```

### Option B — From your router
Open your router admin page (usually `192.168.1.1` or `192.168.0.1`) → connected devices → look for `nvidia` or `tegra` or `ubuntu`.

### Option C — mDNS hostname (no screen needed)
Jetson broadcasts `ubuntu.local` by default. From your Windows PC:
```cmd
ping ubuntu.local
```
If it resolves, use `ubuntu.local` as the hostname everywhere below instead of the IP.

### Option D — Network scan (if nothing else works)
```cmd
# Windows — install nmap first (winget install nmap)
nmap -sn 192.168.1.0/24
# Look for "NVIDIA" in the MAC vendor column
```

---

## 2. Enable SSH on the Jetson

SSH is enabled by default on Jetson JetPack Ubuntu. To verify (on the Jetson):
```bash
sudo systemctl status ssh
# Should show: active (running)

# If not running:
sudo systemctl enable ssh --now
```

Allow SSH through the firewall if needed:
```bash
sudo ufw allow ssh
```

---

## 3. Connect via SSH from Windows

Windows 10/11 has OpenSSH built in — no PuTTY needed.

```cmd
ssh <jetson-username>@<jetson-ip>
# Example:
ssh nvidia@192.168.1.42
# or using mDNS:
ssh nvidia@ubuntu.local
```

Default Jetson credentials (set during JetPack first boot — use what you chose).

### Useful SSH flags
```cmd
# Keep connection alive (prevents timeout)
ssh -o ServerAliveInterval=60 nvidia@192.168.1.42

# Port forwarding — access Flask API on your PC browser
ssh -L 5000:localhost:5000 nvidia@192.168.1.42
# Then open http://localhost:5000 on your PC
```

### Optional — passwordless SSH (recommended)
```cmd
# On your Windows PC (PowerShell)
ssh-keygen -t ed25519 -C "jetson"
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh nvidia@192.168.1.42 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

---

## 4. Remote Desktop — NoMachine (recommended)

NoMachine is the best option for Jetson — fast, ARM64 native, free, and handles the GPU display properly. NVIDIA uses it in their official Jetson documentation.

### On the Jetson (via SSH)
```bash
# Download the ARM64 .deb (check https://www.nomachine.com/download for latest version)
wget https://download.nomachine.com/download/8.14/Arm/nomachine_8.14.1_1_arm64.deb

# Install
sudo dpkg -i nomachine_8.14.1_1_arm64.deb

# NoMachine starts automatically as a service — verify:
sudo systemctl status nxserver
```

### On your Windows PC
Download and install the NoMachine client from [nomachine.com/download](https://www.nomachine.com/download) (choose Windows).

### Connect
1. Open NoMachine on your PC
2. Click **Add** → Protocol: **NX** → Host: `192.168.1.42` (or `ubuntu.local`) → Port: `4000`
3. Enter your Jetson username/password
4. You get a full desktop of the Jetson on your PC

### Fix black screen (common on headless Jetson)
If the Jetson has no monitor plugged in, the desktop may not initialize. Add a virtual display:
```bash
sudo apt install xserver-xorg-video-dummy

# Create /etc/X11/xorg.conf.d/10-dummy.conf
sudo tee /etc/X11/xorg.conf.d/10-dummy.conf << 'EOF'
Section "Device"
  Identifier "DummyDevice"
  Driver "dummy"
  VideoRam 256000
EndSection

Section "Screen"
  Identifier "DummyScreen"
  Device "DummyDevice"
  Monitor "DummyMonitor"
  DefaultDepth 24
  SubSection "Display"
    Depth 24
    Modes "1920x1080"
  EndSubSection
EndSection

Section "Monitor"
  Identifier "DummyMonitor"
  HorizSync 28.0-80.0
  VertRefresh 48.0-75.0
EndSection
EOF

sudo reboot
```

---

## 5. Remote Desktop — VNC (alternative)

Lighter than NoMachine but can lag at high resolution. Use if NoMachine doesn't work.

### On the Jetson
```bash
sudo apt install tigervnc-standalone-server -y

# Set VNC password
vncpasswd

# Start VNC server on display :1 (1920x1080)
vncserver :1 -geometry 1920x1080 -depth 24

# Auto-start on boot
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/vncserver.service << 'EOF'
[Unit]
Description=TigerVNC Server

[Service]
ExecStartPre=/bin/sh -c '/usr/bin/vncserver -kill :1 > /dev/null 2>&1; true'
ExecStart=/usr/bin/vncserver :1 -geometry 1920x1080 -depth 24
ExecStop=/usr/bin/vncserver -kill :1

[Install]
WantedBy=default.target
EOF

systemctl --user enable vncserver --now
```

### On your Windows PC
Install [TigerVNC Viewer](https://tigervnc.org/) or [RealVNC Viewer](https://www.realvnc.com/en/connect/download/viewer/).

Connect to: `192.168.1.42:5901` (port 5900 + display number 1).

> **Tip:** Tunnel VNC over SSH for security:
> ```cmd
> ssh -L 5901:localhost:5901 nvidia@192.168.1.42
> ```
> Then connect VNC to `localhost:5901`.

---

## 6. Deploy the project

Once connected via SSH:

```bash
# Clone the repo
git clone https://github.com/Paug09/IA04_Jetson.git
cd IA04_Jetson

# Install Ollama + pull model (~2.2GB download)
bash scripts/setup_ollama.sh

# Install PyTorch for JetPack 6.x (MUST come before pip install)
pip install --extra-index-url \
  https://developer.download.nvidia.com/compute/redist/jp/v61 torch

# Install project dependencies
pip install -r requirements.txt

# Download embedding model cache (~120MB, happens on first import)
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"

# Run the full pipeline
bash scripts/run_pipeline.sh
```

Flask will be available at `http://<jetson-ip>:5000`.

From your PC, access it directly (same network) or via SSH port forward:
```cmd
ssh -L 5000:localhost:5000 nvidia@192.168.1.42
# Then: http://localhost:5000/health
```

---

## 7. Quick reference

| Task | Command |
|------|---------|
| Find Jetson IP | `hostname -I` on Jetson, or `ping ubuntu.local` from PC |
| SSH in | `ssh nvidia@<ip>` |
| SSH with port forward | `ssh -L 5000:localhost:5000 nvidia@<ip>` |
| Check Ollama | `ollama list` |
| Restart Flask | `python src/app.py` |
| Rebuild RAG index | `python src/build_index.py` |
| Full pipeline | `bash scripts/run_pipeline.sh --skip-collect` |
| Check GPU usage | `tegrastats` |
| Check RAM | `free -h` |
