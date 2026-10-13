from .processor import Options, phone_changes


def test_bitrix_fm_object_uses_existing_keys_without_creating_records():
    item = {
        "fm": {
            "215": {"typeId": "PHONE", "valueType": "OTHER", "value": "+79990000000"},
            "216": {"typeId": "PHONE", "valueType": "WORK", "value": "+79991111111"},
        }
    }
    assert phone_changes(item, Options(dry_run=False)) == {
        "215": {"typeId": "PHONE", "valueType": "WORK", "value": "+79990000000"}
    }
