#!/usr/bin/env bash

set -Eeuo pipefail

QUEUE_FILE="${1:-video_queue.txt}"
TARGET_DIR="${2:-$PWD}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONVERTER="$SCRIPT_DIR/download_and_convert_video.sh"

if [[ ! -f "$QUEUE_FILE" ]]; then
  echo "Файл очереди не найден: $QUEUE_FILE" >&2
  echo "Создай его: по одной ссылке на видео в каждой строке." >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"
TOTAL=0
SUCCESS=0
FAILED=0

while IFS= read -r URL || [[ -n "$URL" ]]; do
  URL="$(printf '%s' "$URL" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  [[ -z "$URL" || "$URL" == \#* ]] && continue
  TOTAL=$((TOTAL + 1))

  echo
  echo "[$TOTAL] Обработка ссылки"
  if "$CONVERTER" "$URL" "" "$TARGET_DIR"; then
    SUCCESS=$((SUCCESS + 1))
  else
    FAILED=$((FAILED + 1))
    echo "Ошибка: ссылка пропущена, очередь продолжается." >&2
  fi
done < "$QUEUE_FILE"

echo
echo "Готово. Всего: $TOTAL, успешно: $SUCCESS, ошибок: $FAILED"
[[ "$FAILED" -eq 0 ]]
