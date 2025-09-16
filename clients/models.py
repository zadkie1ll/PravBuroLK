from django.contrib.auth.models import User
from django.db import models
import uuid
from django.utils.text import slugify
from django.db.models import Q



class StageTemplate(models.Model):
    name = models.CharField(max_length=100, unique=True)
    order = models.PositiveIntegerField(default=0)
    slug = models.SlugField(max_length=100, unique=True, blank=True, null=True)
    description = models.TextField(blank=True, null=True)  # описание стадии

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while StageTemplate.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_next(self):
        """Возвращает следующую стадию по order"""
        return StageTemplate.objects.filter(order__gt=self.order).order_by('order').first()


class Client(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='client')
    name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    middlename = models.CharField(max_length=100, blank=True, null=True)
    bitrix_id = models.CharField(max_length=255, null=True, blank=True)

    stage = models.ForeignKey("StageTemplate", on_delete=models.SET_NULL, null=True, blank=True)
    referral_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['bitrix_id'],
                condition=~Q(bitrix_id=None),
                name='unique_bitrix_id_not_null'
            )
        ]
    
    def __str__(self):
        return f"{self.surname} {self.name} {self.middlename or ''}".strip()

    def current_stage(self):
        return self.stage

    def next_stage(self):
        if self.stage:
            return self.stage.get_next()
        return StageTemplate.objects.order_by('order').first()

    # 👉 метод для ссылки
    def get_ref_link(self, request=None):
        from django.urls import reverse
        path = reverse("referral_landing", args=[str(self.referral_code)])
        return request.build_absolute_uri(path) if request else path
    
    
    # --- Статистика переходов по ссылке ---
class ReferralClick(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="ref_clicks")
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Переход к {self.client} с {self.ip_address}"


# --- Полноценная заявка ---
class Application(models.Model):
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # если заявка пришла по рефералу
    referral_owner = models.ForeignKey(
        Client, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="applications_from_referral"
    )

    def __str__(self):
        return f"Заявка {self.name} ({self.phone})"