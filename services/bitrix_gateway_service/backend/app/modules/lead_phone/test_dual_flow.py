from .processor import Options, process_converted_lead, process_lead


def test_lead_phone_flow_is_independent_from_contact_flow():
    calls = []

    def call(method, params):
        calls.append(method)
        if method == "crm.item.get":
            return {"item": {"fm": {"7": {"typeId": "PHONE", "valueType": "OTHER", "value": "+79990000000"}}}}
        return True

    assert process_lead(call, "10", Options(dry_run=False)) == ("done", 1)
    assert calls == ["crm.item.get", "crm.item.update"]
