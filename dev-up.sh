#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

docker compose -f docker-compose.yml up -d --build
docker compose -f services/call_queue_service/docker-compose.yml up -d --build
docker compose -f services/bitrix_gateway_service/docker-compose.yml up -d --build
docker compose -f services/education_platform_service/docker-compose.yml up -d --build
docker compose -f services/communications_service/docker-compose.yml up -d --build
