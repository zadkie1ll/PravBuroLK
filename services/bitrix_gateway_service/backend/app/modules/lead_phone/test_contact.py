from .processor import process_contact


def test_new_contact_copies_first_phone_to_report_field():
    calls = []

    def call(method, params):
        calls.append((method, params))
        if method == "crm.contact.get":
            return {"ID": "42", "PHONE": [{"VALUE": "+79990000000", "VALUE_TYPE": "WORK"}]}
        return True

    status, changed = process_contact(call, "42", "UF_CRM_68931B5269702", False)
    assert (status, changed) == ("done", 1)
    assert calls[-1] == ("crm.contact.update", {"id": 42, "fields": {"UF_CRM_68931B5269702": "+79990000000"}})
