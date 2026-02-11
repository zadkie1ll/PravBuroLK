from __future__ import annotations

from django.db import models
from django.utils import timezone


class Region(models.Model):
    """
    Регион, как он задан в Bitrix (обычно ID значения списка / справочника).
    """
    bitrix_region_id = models.PositiveIntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Регион"
        verbose_name_plural = "Регионы"
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.name} (B24:{self.bitrix_region_id})"


class PmRateQuerySet(models.QuerySet):
    def active_on(self, dt):
        """
        Запись ПМ, действующая на дату dt (берём последнюю по effective_from).
        """
        if dt is None:
            dt = timezone.now()
        d = dt.date() if hasattr(dt, "date") else dt
        return self.filter(effective_from__lte=d).order_by("-effective_from")


class PmRate(models.Model):
    """
    Прожиточный минимум по региону.
    effective_from позволяет хранить историю (изменения ПМ по датам).
    """
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name="pm_rates")
    effective_from = models.DateField(help_text="С какой даты действует этот ПМ")

    pm_working = models.DecimalField(max_digits=12, decimal_places=2, help_text="ПМ для трудоспособных")
    pm_pensioner = models.DecimalField(max_digits=12, decimal_places=2, help_text="ПМ для пенсионеров")
    pm_child = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="ПМ на ребёнка (опционально, на будущее)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PmRateQuerySet.as_manager()

    class Meta:
        verbose_name = "ПМ по региону"
        verbose_name_plural = "ПМ по регионам"
        ordering = ("region__name", "-effective_from")
        constraints = [
            models.UniqueConstraint(
                fields=["region", "effective_from"],
                name="uniq_pm_rate_region_effective_from"
            )
        ]

    def __str__(self) -> str:
        return f"ПМ {self.region.name} с {self.effective_from}"

    @staticmethod
    def get_for_region_on(region_bitrix_id: int, dt=None) -> "PmRate | None":
        """
        Удобный хелпер: получить актуальный ПМ по bitrix_region_id на дату dt.
        """
        if dt is None:
            dt = timezone.now()
        d = dt.date() if hasattr(dt, "date") else dt
        return (
            PmRate.objects
            .filter(region__bitrix_region_id=region_bitrix_id, effective_from__lte=d, region__is_active=True)
            .select_related("region")
            .order_by("-effective_from")
            .first()
        )