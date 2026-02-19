#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/zadkiel/projects/PravBuroLK"
VENV="$APP_DIR/venv"
PY="$VENV/bin/python"
FRONT_DIR="$APP_DIR/lms-front"
FRONT_STATIC_DIR="$APP_DIR/static/lms-front"
DEPLOY_FRONTEND="${DEPLOY_FRONTEND:-1}"

cd "$APP_DIR"

echo "[1/9] Sync repo to origin/main (clean local changes)"
git fetch origin main
git reset --hard origin/main
git clean -fd

echo "[2/9] Activate venv"
source "$VENV/bin/activate"

echo "[3/9] Install deps"
pip install -r requirements.txt

if [[ "$DEPLOY_FRONTEND" == "1" ]]; then
  echo "[4/9] Build frontend (Vite)"
  sudo apt install nodejs npm

  cd "$FRONT_DIR"
  VITE_BASE_PATH="${VITE_BASE_PATH:-/static/lms-front/}"
  VITE_APP_BASENAME="${VITE_APP_BASENAME:-/static/lms-front}"
  if [[ -f package-lock.json ]]; then
    npm ci
  else
    npm install
  fi
  VITE_BACKEND_URL="${VITE_BACKEND_URL:-}" \
  VITE_BASE_PATH="$VITE_BASE_PATH" \
  VITE_APP_BASENAME="$VITE_APP_BASENAME" \
  npm run build

  echo "[5/9] Copy frontend dist to Django static"
  rm -rf "$FRONT_STATIC_DIR"
  mkdir -p "$FRONT_STATIC_DIR"
  cp -R dist/. "$FRONT_STATIC_DIR/"
  cd "$APP_DIR"
else
  echo "[4/9] Skip frontend (DEPLOY_FRONTEND=$DEPLOY_FRONTEND)"
fi

echo "[6/9] Migrate"
$PY manage.py migrate --noinput

echo "[7/9] Collectstatic"
$PY manage.py collectstatic --noinput

echo "[8/9] Restart service"
sudo -n /usr/bin/systemctl restart pravburo.service

echo "[9/9] Status"
/usr/bin/systemctl --no-pager --full status pravburo.service | head -n 50

echo "DONE"
