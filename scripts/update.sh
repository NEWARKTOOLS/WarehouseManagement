#!/bin/bash
# WMS Auto-Update Script
# This script pulls latest changes and restarts the container

set -e

# Navigate to project directory
cd "$(dirname "$0")/.."

echo "=== WMS Update Script ==="
echo "$(date)"
echo ""

# Pull latest changes
echo "Pulling latest changes from GitHub..."
git fetch origin
git pull origin main

# Check if docker-compose.yml or Dockerfile changed
if git diff --name-only HEAD@{1} HEAD | grep -qE '(Dockerfile|docker-compose\.yml|requirements\.txt)'; then
    echo "Build files changed - rebuilding container..."
    docker-compose down
    docker-compose up -d --build
else
    echo "Only code changes - restarting container..."
    docker-compose restart wms
fi

echo ""
echo "Update complete!"
echo "==========================="
