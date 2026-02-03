#!/bin/bash
# Setup cron-based auto-update (simpler alternative to webhooks)
# Checks for updates every 5 minutes

set -e

WMS_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Setting up Cron Auto-Update ==="

# Create update script that checks for changes first
sudo tee /usr/local/bin/wms-auto-update > /dev/null << EOF
#!/bin/bash
cd ${WMS_DIR}

# Fetch latest without merging
git fetch origin main --quiet

# Check if there are new commits
LOCAL=\$(git rev-parse HEAD)
REMOTE=\$(git rev-parse origin/main)

if [ "\$LOCAL" != "\$REMOTE" ]; then
    echo "\$(date): New updates found, deploying..." >> /var/log/wms-updates.log
    ${WMS_DIR}/scripts/update.sh >> /var/log/wms-updates.log 2>&1
else
    # Uncomment below line if you want to log "no updates" messages
    # echo "\$(date): No updates" >> /var/log/wms-updates.log
    :
fi
EOF

sudo chmod +x /usr/local/bin/wms-auto-update

# Add to crontab (every 5 minutes)
(crontab -l 2>/dev/null | grep -v wms-auto-update; echo "*/5 * * * * /usr/local/bin/wms-auto-update") | crontab -

echo ""
echo "=== Cron Auto-Update Setup Complete ==="
echo ""
echo "The server will check for updates every 5 minutes."
echo "View logs: tail -f /var/log/wms-updates.log"
echo ""
echo "To change frequency, edit crontab: crontab -e"
echo "To disable: crontab -e and remove the wms-auto-update line"
