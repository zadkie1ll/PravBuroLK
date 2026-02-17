# bitrix/services/bitrix_client.py
class BitrixClient:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url.rstrip("/")

    def call(self, method: str, params: dict | None = None) -> dict:
        import requests
        url = f"{self.webhook_url}/{method}.json"
        r = requests.post(url, json=params or {}, timeout=60)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(f"Bitrix error: {data['error']} - {data.get('error_description')}")
        return data["result"]

    def get_deal_userfield_enums(self, field_name: str) -> list[dict]:
        items = self.call("crm.deal.userfield.list", {"filter": {"FIELD_NAME": field_name}})
        if not items:
            raise RuntimeError(f"Userfield not found: {field_name}")
        uf = items[0]
        return uf.get("LIST", []) or []

    def get_status_list(self, entity_id: str) -> list[dict]:
        """
        Для системных справочников CRM.
        Примеры entity_id:
          - "SOURCE" (источники лидов)
          - "STATUS" (статусы лидов)
          - "DEAL_STAGE" / "DEAL_STAGE_XXX" (стадии сделок)
        Возвращает список словарей со стандартными ключами вроде:
          { "ID": "...", "NAME": "...", "SORT": 10, "STATUS_ID": "...", ... }
        """
        # crm.status.list поддерживает фильтр по ENTITY_ID
        return self.call("crm.status.list", {"filter": {"ENTITY_ID": entity_id}})
    def get_users(self, filter_params: dict | None = None, select: list[str] | None = None) -> list[dict]:
        """
        Обёртка над user.get.
        Bitrix может возвращать постранично — сразу учитываем это.
        """
        filter_params = filter_params or {}
        select = select or [
            "ID",
            "NAME",
            "LAST_NAME",
            "EMAIL",
            "PERSONAL_PHONE",
            "WORK_PHONE",
            "ACTIVE",
            "UF_DEPARTMENT",
        ]

        all_items = []
        start = 0

        while True:
            result = self.call(
                "user.get",
                {
                    "filter": filter_params,
                    "select": select,
                    "start": start,
                },
            )

            if not result:
                break

            all_items.extend(result)

            # Если Bitrix вернул меньше 50 — страниц больше нет
            if len(result) < 50:
                break

            start += 50

        return all_items