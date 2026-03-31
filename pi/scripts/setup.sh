#!/bin/bash
# Pillar Controller — Pi setup script
# Run once on a fresh Raspberry Pi OS Lite install

set -euo pipefail

echo "=== Pillar Controller Setup ==="

# Create user
if ! id -u pillar &>/dev/null; then
  sudo useradd -r -m -s /bin/bash pillar
  sudo usermod -aG dialout,audio pillar
  echo "Created pillar user"
fi

# Install system dependencies
sudo apt-get update
sudo apt-get install -y \
  python3 python3-pip python3-venv \
  ffmpeg \
  libportaudio2 portaudio19-dev \
  avahi-daemon \
  git

# Create directory structure
sudo mkdir -p /opt/pillar/{app,config,media,cache,logs}
sudo chown -R pillar:pillar /opt/pillar

# Copy application
sudo cp -r "$(dirname "$0")/../app/"* /opt/pillar/app/
sudo cp -r "$(dirname "$0")/../config/"* /opt/pillar/config/

# Create virtual environment
sudo -u pillar python3 -m venv /opt/pillar/venv
sudo -u pillar /opt/pillar/venv/bin/pip install --upgrade pip
sudo -u pillar /opt/pillar/venv/bin/pip install \
  fastapi uvicorn[standard] pyserial numpy Pillow pyyaml \
  websockets python-multipart sounddevice av

# Install systemd service
sudo cp "$(dirname "$0")/../systemd/pillar.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pillar

# Setup hotspot
echo ""
echo "=== Setting up Wi-Fi hotspot ==="
echo "Run the following to create the hotspot profile:"
echo ""
echo "  sudo nmcli dev wifi hotspot ifname wlan0 ssid Pillar-Control password pillar2026"
echo "  sudo nmcli connection modify Hotspot autoconnect yes"
echo "  sudo nmcli connection modify Hotspot ipv4.addresses 192.168.4.1/24"
echo ""

# Set hostname
sudo hostnamectl set-hostname pillar

echo ""
echo "=== Setup complete ==="
echo "Start with: sudo systemctl start pillar"
echo "View logs:  sudo journalctl -u pillar -f"
echo "Web UI:     http://192.168.4.1"
