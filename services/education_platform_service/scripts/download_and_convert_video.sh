#!/usr/bin/env bash

set -Eeuo pipefail

if [[ $# -lt 1 || $# -gt 3 ]]; then
  echo "Использование:"
  echo "  $0 <URL> [имя-файла.mp4] [каталог]"
  echo
  echo "Пример:"
  echo "  $0 'https://example.com/lesson_01.mp4'"
  exit 2
fi

URL="$1"
URL_PATH="${URL%%\?*}"
OUTPUT_NAME="${2:-${URL_PATH##*/}}"
TARGET_DIR="${3:-$PWD}"

if [[ -z "$OUTPUT_NAME" || "$OUTPUT_NAME" == "/" ]]; then
  OUTPUT_NAME="video.mp4"
fi

if [[ "$OUTPUT_NAME" == */* || "$OUTPUT_NAME" == "." || "$OUTPUT_NAME" == ".." ]]; then
  echo "Ошибка: имя файла должно быть простым именем без каталогов: $OUTPUT_NAME" >&2
  exit 2
fi

command -v curl >/dev/null || { echo "Не найден curl" >&2; exit 1; }
command -v ffmpeg >/dev/null || { echo "Не найден ffmpeg" >&2; exit 1; }
command -v ffprobe >/dev/null || { echo "Не найден ffprobe" >&2; exit 1; }

mkdir -p "$TARGET_DIR"
SOURCE="$TARGET_DIR/$OUTPUT_NAME"
CONVERTED="${SOURCE%.*}.h264.mp4"

if [[ -e "$SOURCE" || -e "$CONVERTED" ]]; then
  echo "Ошибка: файл уже существует:" >&2
  [[ -e "$SOURCE" ]] && echo "  $SOURCE" >&2
  [[ -e "$CONVERTED" ]] && echo "  $CONVERTED" >&2
  exit 1
fi

cleanup_on_error() {
  rm -f -- "$CONVERTED"
  echo "Конвертация не завершена. Исходный файл сохранён: $SOURCE" >&2
}
trap cleanup_on_error ERR

echo "Скачивание: $OUTPUT_NAME"
DOWNLOAD_URL="$URL"
if [[ "$URL" == *"disk.yandex.ru/d/"* ]]; then
  API_URL="$(python3 - "$URL" <<'PY'
import sys
from urllib.parse import quote, unquote, urlsplit, urlencode

url = sys.argv[1]
parts = [part for part in urlsplit(url).path.split('/') if part]
try:
    index = parts.index('d')
    public_id = parts[index + 1]
except (ValueError, IndexError):
    raise SystemExit('Не удалось определить публичный ключ Яндекс.Диска')

public_key = f'https://disk.yandex.ru/d/{public_id}'
file_path = '/' + '/'.join(unquote(part) for part in parts[index + 2:])
print('https://cloud-api.yandex.net/v1/disk/public/resources/download?' + urlencode({
    'public_key': public_key,
    'path': file_path,
}))
PY
)"
  DOWNLOAD_URL="$(curl --fail --location --retry 3 "$API_URL" | python3 -c 'import json, sys; print(json.load(sys.stdin)["href"])')"
fi

curl --fail --location --retry 3 --continue-at - --output "$SOURCE" "$DOWNLOAD_URL"

echo "Конвертация в H.264/AAC: $SOURCE"
ffmpeg -hide_banner -y -i "$SOURCE" \
  -map 0:v:0 -map 0:a? \
  -c:v libx264 -preset medium -crf 23 \
  -c:a aac -b:a 128k \
  -movflags +faststart \
  "$CONVERTED"

VIDEO_CODEC="$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$CONVERTED")"
AUDIO_CODEC="$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$CONVERTED" || true)"

if [[ "$VIDEO_CODEC" != "h264" || ( -n "$AUDIO_CODEC" && "$AUDIO_CODEC" != "aac" ) ]]; then
  echo "Ошибка проверки результата: video=$VIDEO_CODEC audio=${AUDIO_CODEC:-none}" >&2
  exit 1
fi

mv -- "$CONVERTED" "$SOURCE"
trap - ERR

echo "Готово: $SOURCE"
echo "Проверено: video=$VIDEO_CODEC audio=${AUDIO_CODEC:-none}"
echo "Исходный HEVC-файл удалён после успешной проверки."
