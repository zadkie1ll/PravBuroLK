# Мониторинг контейнеров ЛК

Uptime Kuma запускается на сервере ЛК отдельным Compose-проектом.
Docker Socket Proxy предоставляет Kuma доступ на чтение к API контейнеров
во внутренней сети. Настройки, мониторы и история хранятся в томе `kuma_data`.

На сервере из корня репозитория:

```bash
cd services/uptime_kuma_service
docker compose -f docker-compose.prod.yml config -q
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
```

На Mac откройте SSH-туннель и оставьте терминал открытым:

```bash
ssh -N -o ExitOnForwardFailure=yes -L 3001:127.0.0.1:3001 zadkiel@217.149.31.38
```

1. Откройте [Kuma](http://localhost:3001) и создайте администратора.
2. Добавьте монитор **Docker Container**. В настройках Docker Host выберите
   **TCP**, укажите `http://docker-proxy:2375` и нажмите **Test**.
3. Для первой проверки укажите контейнер `postgres_db` и интервал 60 секунд.
4. Добавьте нужные контейнеры по именам из `docker ps`. При настройке
   Telegram нажмите **Test** в настройках уведомления и привяжите его к мониторам.

Если Kuma уже запущена из `~/monitoring/uptime-kuma`, перед запуском этого
проекта проверьте, есть ли в прежнем томе нужные настройки. Оба проекта
используют порт 3001 и по умолчанию имеют разные тома.
