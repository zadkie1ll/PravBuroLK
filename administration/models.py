from django.db import models


class Prize(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name="Название приза"
    )

    image = models.ImageField(
        upload_to="prizes/",
        verbose_name="Картинка приза"
    )

    chance = models.FloatField(
        verbose_name="Шанс выпадения",
        help_text="Относительный вес. Например: 0.1, 1, 5"
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Приз"
        verbose_name_plural = "Призы"

    def __str__(self):
        return self.name
    
    
class Ticket(models.Model):
    code = models.CharField(
        max_length=6,
        unique=True,
        verbose_name="Код билета"
    )

    is_used = models.BooleanField(
        default=False,
        verbose_name="Использован"
    )

    used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата использования"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Билет"
        verbose_name_plural = "Билеты"

    def __str__(self):
        return self.code
    
    
    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)
    
    
class SpinResult(models.Model):
    ticket = models.OneToOneField(
        Ticket,
        on_delete=models.CASCADE,
        related_name="spin_result",
        verbose_name="Билет"
    )

    prize = models.ForeignKey(
        Prize,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Приз"
    )

    is_win = models.BooleanField(
        verbose_name="Выигрыш"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Результат прокрута"
        verbose_name_plural = "Результаты прокрута"

    def __str__(self):
        return f"{self.ticket.code} — {'WIN' if self.is_win else 'LOSE'}"