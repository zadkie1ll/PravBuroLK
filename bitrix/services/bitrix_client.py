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
        """
        field_name: "UF_CRM_1745886887592"
        Возвращает LIST: [{ID, VALUE, SORT, DEF}, ...]
        """
        items = self.call(
            "crm.deal.userfield.list",
            {"filter": {"FIELD_NAME": field_name}}
        )

        if not items:
            raise RuntimeError(f"Userfield not found: {field_name}")

        uf = items[0]
        enums = uf.get("LIST", []) or []
        return enums