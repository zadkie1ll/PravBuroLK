from communications.models import CallProcessingLog, CallWebhookEvent, ProcessedCallArchive


class CommunicationsRouter:
    """
    Разводим модельный слой по БД:
    - CallWebhookEvent / CallProcessingLog -> logs DB
    - ProcessedCallArchive -> archive DB
    """

    route_app_labels = {"communications"}
    logs_models = {CallWebhookEvent, CallProcessingLog}
    archive_models = {ProcessedCallArchive}

    def db_for_read(self, model, **hints):
        if model in self.archive_models:
            return "archive"
        if model in self.logs_models:
            return "logs"
        return None

    def db_for_write(self, model, **hints):
        if model in self.archive_models:
            return "archive"
        if model in self.logs_models:
            return "logs"
        return None

    def allow_relation(self, obj1, obj2, **hints):
        if obj1._meta.app_label in self.route_app_labels and obj2._meta.app_label in self.route_app_labels:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label != "communications":
            return None

        if model_name == "processedcallarchive":
            return db == "archive"

        if model_name in {"callwebhookevent", "callprocessinglog"}:
            return db == "logs"

        return None
