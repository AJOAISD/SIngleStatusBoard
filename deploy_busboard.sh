#!/bin/bash
set -e

# CONFIG
REPO_URL="https://github.com/YOUR_USERNAME/bus-status-board.git"
PROJECT_DIR="/opt/busboard"
SERVICE_NAME="busboard"

echo "=== Installing dependencies ==="
sudo apt update
sudo apt install -y python3 python3-venv nginx git

echo "=== Cloning/updating repository ==="
if [ ! -d "$PROJECT_DIR" ]; then
  sudo git clone $REPO_URL $PROJECT_DIR
else
  cd $PROJECT_DIR
  sudo git pull
fi

cd $PROJECT_DIR
sudo python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "=== Setting up systemd service ==="
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOF
[Unit]
Description=Bus Status Board
After=network.target

[Service]
User=www-data
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/gunicorn --workers 3 --bind unix:$PROJECT_DIR/busboard.sock app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl restart ${SERVICE_NAME}

echo "=== Configuring NGINX ==="
sudo tee /etc/nginx/sites-available/${SERVICE_NAME} > /dev/null <<EOF
server {
    listen 80;
    server_name _;

    location / {
        include proxy_params;
        proxy_pass http://unix:$PROJECT_DIR/busboard.sock;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/${SERVICE_NAME} /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

echo "=== Deployment complete! ==="
echo "Visit: http://<your_server_ip>/"
