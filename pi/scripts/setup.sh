#!/bin/bash
# Pillar Controller — Pi setup script
# Run once on a fresh Raspberry Pi OS Lite install.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PI_DIR="${REPO_DIR}/pi"

echo "=== Pillar Controller Setup ==="
echo "Repo: ${REPO_DIR}"

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
  avahi-daemon

# Create directory structure
sudo mkdir -p /opt/pillar/{config,media,cache,logs}
sudo chown -R pillar:pillar /opt/pillar

# Create venv and install from pyproject.toml
sudo -u pillar python3 -m venv /opt/pillar/venv
sudo -u pillar /opt/pillar/venv/bin/pip install --upgrade pip
sudo -u pillar /opt/pillar/venv/bin/pip install -e "${PI_DIR}[audio]"

# Copy config if not present (never overwrite existing)
if [ ! -f /opt/pillar/config/system.yaml ]; then
  sudo -u pillar cp "${PI_DIR}/config/system.yaml.example" /opt/pillar/config/system.yaml
  echo ""
  echo "*** IMPORTANT: Edit /opt/pillar/config/system.yaml ***"
  echo "*** Set auth.token and network.password before starting ***"
  echo ""
fi
for cfg in hardware.yaml effects.yaml; do
  if [ ! -f "/opt/pillar/config/${cfg}" ]; then
    sudo -u pillar cp "${PI_DIR}/config/${cfg}" "/opt/pillar/config/${cfg}"
  fi
done

# Install systemd service
sudo cp "${PI_DIR}/systemd/pillar.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pillar

# Set hostname
sudo hostnamectl set-hostname pillar

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit /opt/pillar/config/system.yaml (set auth.token and network.password)"
echo "  2. Set up Wi-Fi hotspot:"
echo "     sudo nmcli dev wifi hotspot ifname wlan0 ssid Pillar-Control password YOUR_PASSWORD"
echo "     sudo nmcli connection modify Hotspot autoconnect yes"
echo "     sudo nmcli connection modify Hotspot ipv4.addresses 192.168.4.1/24"
echo "  3. Start: sudo systemctl start pillar"
echo "  4. Logs:  sudo journalctl -u pillar -f"
echo "  5. UI:    http://192.168.4.1"
