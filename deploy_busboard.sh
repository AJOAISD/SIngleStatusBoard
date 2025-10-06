#!/bin/bash
set -euo pipefail

# ---------- CONFIG - EDIT THESE ----------
REPO_URL="https://github.com/AJOAITC/SIngleStatusBoard.git"   # <-- set your GitHub repo
PROJECT_DIR="/opt/busboard"                                 # <-- where to install
SERVICE_NAME="busboard"                                     # systemd & socket name
USER="www-data"                                             # service user (nginx user)
SERVER_NAME="your.domain.or.ip"                             # <-- set your domain or server IP
BRANCH="main"                                               # branch to pull
# -----------------------------------------

echo "=== Deploying ${SERVICE_NAME} from ${REPO_URL} to ${PROJECT_DIR} ==="

# Install system packages (include build tools and image libs required by Pillow)
sudo apt update
sudo apt install -y \
  python3 python3-venv python3-pip python3-dev build-essential \
  nginx git pkg-config \
  libjpeg-dev zlib1g-dev libfreetype6-dev liblcms2-dev libopenjp2-7-dev libtiff5-dev

# Clone or update repo
if [ ! -d "$PROJECT_DIR" ]; then
  sudo mkdir -p "$PROJECT_DIR"
  sudo chown "$(whoami)":"$(whoami)" "$PROJECT_DIR"
  git clone --branch "$BRANCH" "$REPO_URL" "$PROJECT_DIR"
else
  cd "$PROJECT_DIR"
  git fetch origin "$BRANCH"
  git reset --hard "origin/$BRANCH"
fi

cd "$PROJECT_DIR"

# Ensure files are owned by deployer for venv install, then we'll assign to service user
sudo chown -R "$(whoami)":"$(whoami)" "$PROJECT_DIR"

# Create virtualenv and install requirements
python3 -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate

if [ -f "requirements.txt" ]; then
  pip install --upgrade pip
  pip install -r requirements.txt
else
  pip install --upgrade pip
  pip install flask gunicorn
fi
deactivate

# Ensure service user owns project so Gunicorn (run as $USER) can access socket and static files
sudo chown -R "$USER":"$USER" "$PROJECT_DIR"

# ----------- systemd service ------------
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

sudo bash -c "cat > ${SERVICE_FILE}" <<EOF
[Unit]
Description=${SERVICE_NAME} Flask app (Gunicorn)
After=network.target

[Service]
User=${USER}
Group=${USER}
WorkingDirectory=${PROJECT_DIR}
Environment="PATH=${PROJECT_DIR}/venv/bin"
ExecStart=${PROJECT_DIR}/venv/bin/gunicorn --workers 3 --bind unix:${PROJECT_DIR}/${SERVICE_NAME}.sock app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

# ----------- NGINX config ------------
NGINX_SITE="/etc/nginx/sites-available/${SERVICE_NAME}"

sudo bash -c "cat > ${NGINX_SITE}" <<EOF
server {
    listen 80;
    server_name ${SERVER_NAME};

    # Proxy pass to Gunicorn socket
    location / {
        include proxy_params;
        proxy_pass http://unix:${PROJECT_DIR}/${SERVICE_NAME}.sock;
    }

    # Serve static files directly (optional)
    location /static/ {
        alias ${PROJECT_DIR}/static/;
        expires 1d;
        add_header Cache-Control "public";
    }

    # Optional: basic health endpoint handling
    location /health {
        return 200 'OK';
        add_header Content-Type text/plain;
    }
}
EOF

sudo ln -sf "${NGINX_SITE}" /etc/nginx/sites-enabled/${SERVICE_NAME}
sudo nginx -t
sudo systemctl reload nginx

# Open firewall for HTTP (if ufw is present)
if command -v ufw >/dev/null 2>&1; then
  sudo ufw allow 'Nginx Full' || true
fi

echo "=== Deployment complete ==="
echo "Service: sudo systemctl status ${SERVICE_NAME}"
echo "NGINX site: ${SERVER_NAME}"
echo "Socket: ${PROJECT_DIR}/${SERVICE_NAME}.sock"
echo ""
echo "If you have a domain, get HTTPS cert with:"
echo "  sudo apt install certbot python3-certbot-nginx"
echo "  sudo certbot --nginx -d ${SERVER_NAME}"
