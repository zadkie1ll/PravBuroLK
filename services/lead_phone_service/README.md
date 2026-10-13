# Типы телефонов новых лидов

Небольшой Node.js 22 сервис без npm-зависимостей. Только `ONCRMLEADADD`:
читает лид через `crm.item.get` (`entityTypeId: 1`) и меняет `PHONE/OTHER`
на `WORK` через `crm.item.update`. В `fields` отправляется только `fm`,
по существующим ID, с исходными значениями. Почта, другие телефоны и поля не отправляются.

## Локально

```bash
cd services/lead_phone_service
cp .env.example .env
openssl rand -hex 32
```

В `.env` задать `ENDPOINT_SECRET`, `BITRIX_GATEWAY_TOKEN` (тот же, что
`INTERNAL_TOKEN` у gateway), `BITRIX_GATEWAY_PROFILE=consultation` и
`QUEUE_FILE=./data/jobs.json`. Сервис действительно меняет телефоны.

```bash
npm test
npm start
```

Тесты используют только заглушки REST, к Битрикс24 не обращаются.

## Сервер

```bash
cd ~/projects/PravBuroLK
git pull --ff-only
cd services/lead_phone_service
cp .env.example .env
openssl rand -hex 32
nano .env
sudo ss -tlnp 'sport = :8013'
docker compose -f docker-compose.prod.yml config --quiet
docker compose -f docker-compose.prod.yml up -d --build
curl --fail http://127.0.0.1:8013/health
docker logs lead_phone_backend --tail 50
```

Не перезаписывать существующий `.env`: `cp` нужен только при первом запуске.
Если 8013 занят, выбрать свободный порт и изменить PORT и nginx snippet вместе.
Production: `HOST=127.0.0.1`, `QUEUE_FILE=/data/jobs.json`.
Лимиты контейнера: 128 МБ, 0.5 CPU; один процесс, одна последовательная очередь.

Добавить `deploy/nginx.snippet.conf` внутрь существующего HTTPS `server {}`
выбранного домена. Не заменять целиком конфигурацию других сервисов.

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Только после успешного тестирования создать исходящий вебхук в Битрикс24:
событие **создание лида / ONCRMLEADADD**, адрес обработчика:
`https://ВАШ-ДОМЕН/webhooks/bitrix24/ENDPOINT_SECRET`.
Не подписывать на изменение лидов. REST-вебхук с правами CRM хранится только
в конфигурации gateway. `ENDPOINT_SECRET` — секрет URL события, а
`BITRIX_GATEWAY_TOKEN` — внутренний токен между сервисами. Не публиковать их.
Access/error log для endpoint отключены, чтобы секрет в URL не попадал в nginx-логи;
также исключить его из логирования внешнего proxy/CDN/APM, если они есть.

## Надёжность и ограничения

- HTTP 202 возвращается после сохранения задания на диске, обработка асинхронная.
  Повторное событие того же ID не добавляет новое задание.
- Очередь хранит только ID, статус и счётчик, без телефонов/токенов.
  Том `queue_data` сохранять: `docker compose down -v` удалит очередь и историю.
  Запускать только одну реплику: файл не рассчитан на несколько процессов.
- Отсутствующий телефон проверяется до 8 раз (около 4 минут без учёта REST).
  После появления хотя бы одного телефона обработка завершается; добавленные позднее
  телефоны не отслеживаются, поскольку события изменения намеренно не обрабатываются.
- REST: таймаут 15 секунд, backoff для сети, HTTP 429/5xx и лимитов Bitrix.
  Неоднозначный ответ обновления повторяется через новую загрузку лида, а не
  повторную отправку старого payload. Идемпотентность также обеспечивается фильтром OTHER.
- `lead_failed` требует внимания администратора: исправить причину, затем после остановки
  сервиса удалить только соответствующую запись из jobs.json и повторить событие.
  Не переводить реальные сделки/лиды между стадиями ради проверки.
- Bitrix REST не предоставляет здесь compare-and-swap для `fm`: между чтением и записью
  другой пользователь может изменить номер. Сервис сохраняет прочитанный номер, но
  не гарантирует отсутствие гонки с одновременным ручным редактированием или удалением.
  Обрабатывать сразу после создания и проверять на отдельном тестовом лиде.
- История ID растёт; файл требуется резервировать и контролировать его размер.
- `/health` проверяет процесс, но не права/доступность Bitrix. Смотреть `lead_processed`,
  `lead_retry`, `lead_failed` в логах. Тексты ошибок REST, URL и payload не логируются.

## Официальная документация

- [ONCRMLEADADD](https://apidocs.bitrix24.ru/api-reference/crm/leads/events/on-crm-lead-add.html)
- [crm.item.get и массив fm](https://apidocs.bitrix24.ru/api-reference/crm/universal/crm-item-get.html)
- [crm.item.update: существующие ID в fm](https://apidocs.bitrix24.ru/api-reference/crm/universal/crm-item-update.html)
- [Изменение телефонов по ID мультиполя](https://apidocs.bitrix24.ru/tutorials/crm/how-to-edit-crm-objects/how-to-change-email-or-phone.html)
