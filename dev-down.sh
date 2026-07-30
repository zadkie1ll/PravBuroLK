#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

docker compose -f services/urlshorter_service/docker-compose.yml down
docker compose -f services/lead_control_service/docker-compose.yml down
docker compose -f services/admin_panel_service/docker-compose.yml down
docker compose -f services/referral_stats_service/docker-compose.yml down
docker compose -f services/client_search_service/docker-compose.yml down
docker compose -f services/leadreport_service/docker-compose.yml down
docker compose -f services/documents_service/docker-compose.yml down
docker compose -f services/communications_service/docker-compose.yml down
docker compose -f services/education_platform_service/docker-compose.yml down
docker compose -f services/bitrix_gateway_service/docker-compose.yml down
docker compose -f services/call_queue_service/docker-compose.yml down
docker compose -f docker-compose.yml down
docker compose -f services/shared_postgres/docker-compose.yml down
