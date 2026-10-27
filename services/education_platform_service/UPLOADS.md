# Загрузка большого видео с компьютера

Без нового контейнера: браузер отправляет multipart через admin_panel в education backend.
Starlette складывает большой UploadFile во временный файл; save_upload копирует его
блоками по 1 МиБ в .part и переименовывает только полностью записанный файл.
Это потоковая запись, а не возобновляемая/порционная загрузка HTTP: при обрыве передачи
браузеру потребуется отправить файл заново.

После записи исходника и commit модуля video_worker берёт queued-задание, запускает
ffmpeg, проверяет выходной MP4 и только затем публикует его. Старое готовое видео
не заменяется до успешной обработки. При ошибке старое видео и новый исходник сохраняются.
После успеха удаляется только исходник успешно обработанного задания.
Перезапуск воркера повторяет незавершённую конвертацию с сохранённого исходника.
Повторная загрузка файла или смена ссылки не позволяет старому заданию подменить новый результат.

## Развёртывание

Сначала проверить свободный диск (`df -h`): потребуется место для временного файла,
исходника и результата, а не только размер конечного MP4. Исходники неуспешных или
заменённых заданий могут остаться на диске; удалять их можно только после проверки.

После push/pull пересобрать:

```bash
cd ~/projects/PravBuroLK
docker compose -f services/education_platform_service/docker-compose.prod.yml up -d --build backend
docker compose -f services/education_platform_service/docker-compose.prod.yml up -d --build video_worker
docker compose -f services/admin_panel_service/docker-compose.prod.yml up -d --build backend frontend
```

Миграция `20261027_upload_source` добавляет только video_import_source в modules;
существующие видео и статусы сохраняются. Compose запускает alembic upgrade head.
В production нужен ровно один video_worker (очередь обрабатывается последовательно).
Для миграции лучше пересоздать backend сначала, затем воркер, без параллельного старта Alembic.

В существующем **HTTPS** server{} домена panel.prav-buro.ru найти
`location /education-management/` и добавить/обновить только эти директивы:

```nginx
client_max_body_size 3G;
client_body_timeout 300s;
proxy_http_version 1.1;
proxy_request_buffering off;
proxy_send_timeout 3600s;
proxy_read_timeout 3600s;
```

Оставить proxy_pass и заголовки как есть. Не заменять весь production nginx конфигурацией
из репозитория: там шаблон без всех ваших HTTPS/прочих location-блоков.
Лимит 3G относится ко всему multipart-запросу вместе со служебными полями.

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Внешний reverse proxy/CDN при наличии тоже должен разрешать такой размер/длительность.
Без изменения реального nginx запрос по-прежнему будет отклоняться до приложения.

## Проверка

1. Сначала загрузить небольшое тестовое видео. После передачи модуль сохраняется;
   в админке видно «Видео в очереди»/«Подготовка видео»/«Видео готово».
2. Проверить воспроизведение результата, затем повторить с файлом 1–2 ГБ.
3. 100% в браузере означает окончание передачи, **не окончание конвертации**.
4. Наблюдать конвертацию: `docker compose -f services/education_platform_service/docker-compose.prod.yml logs -f --tail 50 video_worker`.

Тесты (без production и реального ffmpeg):

```bash
cd services/education_platform_service/backend
PYTHONPATH=. python3 -m pytest -q tests/test_video_upload.py
```
