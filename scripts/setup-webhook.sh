#!/bin/bash
# Setup GitHub webhook listener for auto-deploy
# Uses webhook (https://github.com/adnanh/webhook)

set -e

WEBHOOK_SECRET="${1:-your-webhook-secret}"
WMS_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Setting up GitHub Webhook Listener ==="

# Install webhook if not present
if ! command -v webhook &> /dev/null; then
    echo "Installing webhook..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y webhook
    elif command -v brew &> /dev/null; then
        brew install webhook
    else
        echo "Please install webhook manually: https://github.com/adnanh/webhook"
        exit 1
    fi
fi

# Create webhook config directory
sudo mkdir -p /etc/webhook
sudo mkdir -p /var/log/webhook

# Create hooks configuration
sudo tee /etc/webhook/hooks.json > /dev/null << EOF
[
  {
    "id": "wms-deploy",
    "execute-command": "${WMS_DIR}/scripts/update.sh",
    "command-working-directory": "${WMS_DIR}",
    "pass-arguments-to-command": [],
    "trigger-rule": {
      "and": [
        {
          "match": {
            "type": "payload-hmac-sha256",
            "secret": "${WEBHOOK_SECRET}",
            "parameter": {
              "source": "header",
              "name": "X-Hub-Signature-256"
            }
          }
        },
        {
          "match": {
            "type": "value",
            "value": "refs/heads/main",
            "parameter": {
              "source": "payload",
              "name": "ref"
            }
          }
        }
      ]
    }
  }
]
EOF

# Create systemd service
sudo tee /etc/systemd/system/webhook.service > /dev/null << EOF
[Unit]
Description=GitHub Webhook Handler
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/webhook -hooks /etc/webhook/hooks.json -port 9000 -verbose
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable webhook
sudo systemctl start webhook

echo ""
echo "=== Webhook Setup Complete ==="
echo ""
echo "Webhook is now listening on port 9000"
echo ""
echo "Next steps:"
echo "1. Go to your GitHub repo → Settings → Webhooks → Add webhook"
echo "2. Payload URL: http://your-tailscale-ip:9000/hooks/wms-deploy"
echo "3. Content type: application/json"
echo "4. Secret: ${WEBHOOK_SECRET}"
echo "5. Events: Just the push event"
echo ""
echo "Test with: curl -X POST http://localhost:9000/hooks/wms-deploy"
