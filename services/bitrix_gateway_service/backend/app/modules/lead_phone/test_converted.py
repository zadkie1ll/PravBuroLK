from .processor import process_converted_lead


def test_converted_lead_updates_contact_only():
    calls = []

    def call(method, params):
        calls.append((method, params))
        if method == "crm.lead.get":
            return {"ID": "100", "STATUS_ID": "CONVERTED", "CONTACT_ID": "42"}
        if method == "crm.contact.get":
            return {"ID": "42", "PHONE": [{"VALUE": "+79990000000", "VALUE_TYPE": "WORK"}]}
        return True

    status, changed = process_converted_lead(call, "100", "CONVERTED", "UF_CRM_68931B5269702", False)
    assert (status, changed) == ("done", 1)
    assert [method for method, _ in calls] == ["crm.lead.get", "crm.contact.get", "crm.contact.update"]
    assert calls[-1][1] == {"id": 42, "fields": {"UF_CRM_68931B5269702": "+79990000000"}}
