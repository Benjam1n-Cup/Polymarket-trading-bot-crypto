#!/bin/bash
# rarb deployment script for fresh Ubuntu VPS
# Usage: ssh root@NEW_IP 'bash -s' < deploy.sh

set -e

echo "=== rarb Deployment Script ==="

# Install dependencies
apt update && apt install -y python3.11 python3.11-venv python3-pip git

# Clone repo
cd /opt
if [ -d "rarb" ]; then
    cd rarb && git pull origin master
else
    git clone https://github.com/kmizzi/rarb.git
    cd rarb
fi

# Create venv and install
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .

# Create .env template
if [ ! -f .env ]; then
    cat > .env << 'EOF'
# === REQUIRED: Fill these in ===

# Polymarket wallet
PRIVATE_KEY=0x_YOUR_WALLET_PRIVATE_KEY
WALLET_ADDRESS=0x_YOUR_WALLET_ADDRESS

# Dashboard credentials
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=CHANGE_THIS_PASSWORD
DASHBOARD_PORT=8080

# Kalshi API (optional - for cross-platform)
KALSHI_API_KEY=your_kalshi_api_key
KALSHI_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
...your key...
-----END RSA PRIVATE KEY-----"

# === Usually don't need to change below ===

# Network
POLYGON_RPC_URL=https://polygon-rpc.com
CHAIN_ID=137

# Trading
DRY_RUN=false
MIN_PROFIT_THRESHOLD=0.005
MAX_POSITION_SIZE=1000
POLL_INTERVAL_SECONDS=2
MIN_LIQUIDITY_USD=5000

# API Endpoints
CLOB_BASE_URL=https://clob.polymarket.com
GAMMA_BASE_URL=https://gamma-api.polymarket.com
EOF
    echo ""
    echo ">>> IMPORTANT: Edit /opt/rarb/.env with your credentials <<<"
    echo ""
fi

# Create systemd service
cat > /etc/systemd/system/rarb.service << 'EOF'
[Unit]
Description=rarb Arbitrage Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/rarb
Environment=PATH=/opt/rarb/.venv/bin
ExecStart=/opt/rarb/.venv/bin/rarb run --realtime
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/rarb-dashboard.service << 'EOF'
[Unit]
Description=rarb Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/rarb
Environment=PATH=/opt/rarb/.venv/bin
ExecStart=/opt/rarb/.venv/bin/rarb dashboard
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable rarb
systemctl enable rarb-dashboard

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit credentials: nano /opt/rarb/.env"
echo "  2. Start the bot: systemctl start rarb"
echo "  3. Start dashboard: systemctl start rarb-dashboard"
echo "  4. Check bot logs: journalctl -u rarb -f"
echo "  5. Access dashboard: http://YOUR_IP:8080"
echo ""
