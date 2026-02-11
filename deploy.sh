#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/zadkiel/projects/PravBuroLK"
VENV="$APP_DIR/venv"
PY="$VENV/bin/python"

cd "$APP_DIR"

echo "[1/6] Pull latest"
git pull --ff-only

echo "[2/6] Install deps"
source "$VENV/bin/activate"
pip install -r requirements.txt

echo "[3/6] Migrate"
$PY manage.py migrate --noinput

echo "[4/6] Collectstatic"
$PY manage.py collectstatic --noinput

echo "[5/6] Restart service"
sudo systemctl restart pravburo

echo "[6/6] Status"
sudo systemctl status pravburo --no-pager

echo "DONE ✅"