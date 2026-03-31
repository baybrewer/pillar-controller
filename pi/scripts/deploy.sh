#!/bin/bash
# Deploy updated code to the Pi
# Usage: ./deploy.sh [pi-hostname-or-ip]

set -euo pipefail

PI_HOST="${1:-pillar.local}"
PI_USER="pillar"
PI_PATH="/opt/pillar"
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

echo "Deploying to ${PI_USER}@${PI_HOST}..."

# Sync app code
rsync -avz --delete \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude '.venv' \
  --exclude '.pytest_cache' \
  "${REPO_DIR}/pi/app/" \
  "${PI_USER}@${PI_HOST}:${PI_PATH}/app-src/app/"

# Sync pyproject.toml for dependency updates
rsync -avz \
  "${REPO_DIR}/pi/pyproject.toml" \
  "${PI_USER}@${PI_HOST}:${PI_PATH}/app-src/"

# Reinstall package and restart
ssh "${PI_USER}@${PI_HOST}" "\
  ${PI_PATH}/venv/bin/pip install -e ${PI_PATH}/app-src && \
  sudo systemctl restart pillar"

echo "Deployed and restarted."
