#!/bin/bash
# Deploy updated code to the Pi
# Usage: ./deploy.sh [pi-hostname-or-ip]

set -euo pipefail

PI_HOST="${1:-pillar.local}"
PI_USER="pillar"
PI_PATH="/opt/pillar"

echo "Deploying to ${PI_USER}@${PI_HOST}..."

# Sync app code
rsync -avz --delete \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  "$(dirname "$0")/../app/" \
  "${PI_USER}@${PI_HOST}:${PI_PATH}/app/"

# Sync config (don't delete — preserve local changes)
rsync -avz \
  "$(dirname "$0")/../config/" \
  "${PI_USER}@${PI_HOST}:${PI_PATH}/config/"

# Restart service
ssh "${PI_USER}@${PI_HOST}" "sudo systemctl restart pillar"

echo "Deployed and restarted."
