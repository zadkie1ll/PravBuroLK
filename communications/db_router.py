from django.conf import settings


class CommunicationsRouter:
    """
    Разводим модельный слой по БД:
    - CallWebhookEvent / CallProcessingLog -> logs DB
    - ProcessedCallArchive -> archive DB
    """

    route_app_labels = {"communications"}
    logs_models = {"callwebhookevent", "callprocessinglog"}
    archive_models = {"processedcallarchive"}

    def _enabled(self) -> bool:
        return bool(getattr(settings, "COMMUNICATIONS_SPLIT_DATABASES", False))

    def _logs_alias(self) -> str:
        return str(getattr(settings, "COMMUNICATIONS_LOGS_DB_ALIAS", "logs"))

    def _archive_alias(self) -> str:
        return str(getattr(settings, "COMMUNICATIONS_ARCHIVE_DB_ALIAS", "archive"))

    def _model_name(self, model) -> str:
        return str(getattr(model._meta, "model_name", "")).lower()

    def db_for_read(self, model, **hints):
        if not self._enabled():
            return None
        model_name = self._model_name(model)
        if model_name in self.archive_models:
            return self._archive_alias()
        if model_name in self.logs_models:
            return self._logs_alias()
        return None

    def db_for_write(self, model, **hints):
        if not self._enabled():
            return None
        model_name = self._model_name(model)
        if model_name in self.archive_models:
            return self._archive_alias()
        if model_name in self.logs_models:
            return self._logs_alias()
        return None

    def allow_relation(self, obj1, obj2, **hints):
        if obj1._meta.app_label in self.route_app_labels and obj2._meta.app_label in self.route_app_labels:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label != "communications":
            return None
        if not self._enabled():
            return None

        normalized_model_name = str(model_name or "").lower()

        if normalized_model_name == "processedcallarchive":
            return db == self._archive_alias()

        if normalized_model_name in {"callwebhookevent", "callprocessinglog"}:
            return db == self._logs_alias()

        return None
