#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/zadkiel/projects/PravBuroLK"
VENV="$APP_DIR/venv"
PY="$VENV/bin/python"
FRONT_DIR="$APP_DIR/lms-front"
FRONT_STATIC_DIR="$APP_DIR/static/lms-front"
DEPLOY_FRONTEND="${DEPLOY_FRONTEND:-1}"
CELERY_SERVICE_NAME="${CELERY_SERVICE_NAME:-pravburo-celery.service}"
CELERY_BEAT_SERVICE_NAME="${CELERY_BEAT_SERVICE_NAME:-pravburo-celerybeat.service}"
COMMUNICATIONS_SPLIT_DATABASES="${COMMUNICATIONS_SPLIT_DATABASES:-0}"

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
    export PATH="/home/zadkiel/.nvm/versions/node/v24.14.0/bin:$PATH"
    cd "$FRONT_DIR"

    echo "=== Очистка кэша npm (убираем 'через раз') ==="
    npm cache clean --force 2>/dev/null || true

    echo "=== Установка пакетов (начало: $(date)) ==="
    rm -rf node_modules .vite  # жёсткая очистка на всякий случай

    if [[ -f package-lock.json ]]; then
        echo "→ npm ci"
        time npm ci --verbose --prefer-offline
    else
        echo "→ npm install"
        time npm install --verbose --prefer-offline
    fi

    echo "=== Сборка Vite (начало: $(date)) ==="
    VITE_BACKEND_URL="${VITE_BACKEND_URL:-}" \
    VITE_BASE_PATH="${VITE_BASE_PATH:-/static/lms-front/}" \
    VITE_APP_BASENAME="${VITE_APP_BASENAME:-/static/lms-front}" \
    time npm run build

    echo "=== Frontend готов (окончание: $(date)) ==="

    echo "[5/9] Copy frontend dist to Django static"
    rm -rf "$FRONT_STATIC_DIR"
    mkdir -p "$FRONT_STATIC_DIR"
    cp -R dist/. "$FRONT_STATIC_DIR/"
    cd "$APP_DIR"
else
    echo "[4/9] Skip frontend (DEPLOY_FRONTEND=$DEPLOY_FRONTEND)"
fi

echo "[6/9] Migrate"
$PY manage.py makemigrations
$PY manage.py makemigrations clients
$PY manage.py migrate --noinput
SPLIT_DB_AVAILABLE="$(
  $PY manage.py shell -c "from django.conf import settings; print(int({'logs','archive'}.issubset(set(settings.DATABASES.keys()))))" 2>/dev/null || echo 0
)"
if [[ "$COMMUNICATIONS_SPLIT_DATABASES" == "1" && "$SPLIT_DB_AVAILABLE" == "1" ]]; then
  $PY manage.py migrate communications --database=logs --noinput
  $PY manage.py migrate communications --database=archive --noinput
else
  echo "Skip split-db migrations (COMMUNICATIONS_SPLIT_DATABASES=$COMMUNICATIONS_SPLIT_DATABASES, SPLIT_DB_AVAILABLE=$SPLIT_DB_AVAILABLE)"
fi

echo "[7/9] Collectstatic"
$PY manage.py collectstatic --noinput

echo "[8/9] Restart service"
sudo -n /usr/bin/systemctl restart pravburo.service

echo "[9/9] Restart celery workers (if present)"
if /usr/bin/systemctl list-unit-files "$CELERY_SERVICE_NAME" --no-legend 2>/dev/null | /usr/bin/grep -q "$CELERY_SERVICE_NAME"; then
  sudo -n /usr/bin/systemctl restart "$CELERY_SERVICE_NAME"
else
  echo "Skip: $CELERY_SERVICE_NAME not found"
fi

if /usr/bin/systemctl list-unit-files "$CELERY_BEAT_SERVICE_NAME" --no-legend 2>/dev/null | /usr/bin/grep -q "$CELERY_BEAT_SERVICE_NAME"; then
  sudo -n /usr/bin/systemctl restart "$CELERY_BEAT_SERVICE_NAME"
else
  echo "Skip: $CELERY_BEAT_SERVICE_NAME not found"
fi

echo "[10/10] Status"
/usr/bin/systemctl --no-pager --full status pravburo.service | head -n 50

echo "DONE"
