from django.db import models
from django.utils import timezone


class LeadMonitorStatus(models.TextChoices):
    NEW = "new", "Новая"
    ACTIVE = "active", "Активна"
    SUCCESS = "success", "Успешно завершена"
    STOPPED = "stopped", "Остановлена"
    SKIPPED = "skipped", "Исключена"
    ERROR = "error", "Ошибка"


class LeadMonitor(models.Model):
    bitrix_deal_id = models.BigIntegerField(
        unique=True,
        verbose_name="ID сделки в Bitrix24"
    )

    # Первая кастомная задача, которую ставим сразу в хендлере
    initial_bitrix_task_id = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name="ID первой задачи в Bitrix24"
    )

    # Текущая актуальная задача по сделке
    bitrix_task_id = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name="ID текущей задачи в Bitrix24"
    )

    moderator_bitrix_user_id = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name="ID модератора в Bitrix24"
    )
    responsible_bitrix_user_id = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name="ID ответственного за сделку"
    )

    task_description = models.TextField(
        blank=True,
        default="",
        verbose_name="Описание первой задачи"
    )

    initial_task_created = models.BooleanField(
        default=False,
        verbose_name="Первая задача уже создана"
    )

    attempts_total = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Всего создано задач"
    )
    attempts_today = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Задач создано сегодня"
    )
    attempts_last_reset_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Дата последнего сброса attempts_today"
    )

    entered_logic_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Когда сделка зарегистрирована в логике"
    )

    current_stage_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Последняя известная стадия сделки"
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Активна в мониторинге"
    )
    status = models.CharField(
        max_length=20,
        choices=LeadMonitorStatus.choices,
        default=LeadMonitorStatus.NEW,
        verbose_name="Статус"
    )
    status_comment = models.TextField(
        blank=True,
        default="",
        verbose_name="Комментарий статуса"
    )

    last_task_closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Когда в последний раз закрыли задачу"
    )
    last_checked_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Когда в последний раз проверяли"
    )

    raw_deal_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Последние сырые данные сделки"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Мониторинг лида из модерации"
        verbose_name_plural = "Мониторинг лидов из модерации"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "status"]),
            models.Index(fields=["responsible_bitrix_user_id"]),
            models.Index(fields=["current_stage_id"]),
        ]

    def __str__(self):
        return f"LeadMonitor(deal={self.bitrix_deal_id}, status={self.status})"

    def reset_daily_attempts_if_needed(self):
        today = timezone.localdate()
        if self.attempts_last_reset_date != today:
            self.attempts_today = 0
            self.attempts_last_reset_date = today