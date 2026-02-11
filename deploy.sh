#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/zadkiel/projects/PravBuroLK"
VENV="$APP_DIR/venv"
PY="$VENV/bin/python"

cd "$APP_DIR"

echo "[1/6] Pull latest"
git pull --ff-only

echo "[2/6] Activate venv"
source "$VENV/bin/activate"

echo "[3/6] Install deps"
pip install -r requirements.txt

echo "[4/6] Migrate"
$PY manage.py migrate --noinput

echo "[5/6] Collectstatic"
$PY manage.py collectstatic --noinput

echo "[6/6] Restart uvicorn"
# если у тебя systemd-сервис — поменяй на него
pkill -f "uvicorn pravburo.asgi:application" || true
nohup "$VENV/bin/uvicorn" pravburo.asgi:application \
  --host 127.0.0.1 --port 8000 --workers 4 --proxy-headers --log-level info \
  > "$APP_DIR/logs/uvicorn.log" 2>&1 &

echo "DONE"
