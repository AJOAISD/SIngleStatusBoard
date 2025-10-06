#!/bin/bash
APP_DIR="/home/ubuntu/busboard"
DOMAIN="your_domain_or_ip"
PORT=8000

sudo apt update && sudo apt install -y python3 python3-venv python3-pip nginx git sqlite3

if [ ! -d "$APP_DIR" ]; then
  mkdir -p "$APP_DIR"
fi

cd "$APP_DIR"

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt || pip install flask gunicorn
deactivate

# Create systemd service
sudo bash -c "cat > /etc/systemd/system/busboard.service" <<EOL
[Unit]
Description=Bus Board Flask App
After=network.target

[Service]
User=ubuntu
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:$PORT app:app

[Install]
WantedBy=multi-user.target
EOL

sudo systemctl daemon-reload
sudo systemctl enable busboard
sudo systemctl start busboard

# NGINX config
sudo bash -c "cat > /etc/nginx/sites-available/busboard" <<EOL
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOL

sudo ln -sf /etc/nginx/sites-available/busboard /etc/nginx/sites-enabled/
sudo nginx -
