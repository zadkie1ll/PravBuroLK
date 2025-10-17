from django.contrib.auth.models import User
from django.db import models
import uuid
from django.utils.text import slugify
from django.db.models import Q
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType



class Employee(models.Model):
    bitrix_id = models.CharField(max_length=255, unique=True) 
    name = models.CharField(max_length=255)                     
    referral_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_ref_link(self, request=None):
        from django.urls import reverse
        path = reverse("referral_landing", args=[str(self.referral_code)])
        return request.build_absolute_uri(path) if request else path


class StageTemplate(models.Model):
    name = models.CharField(max_length=100, unique=True)
    order = models.PositiveIntegerField(default=0)
    slug = models.SlugField(max_length=100, unique=True, blank=True, null=True)
    description = models.TextField(blank=True, null=True)  # описание стадии
    youtube_url = models.URLField(blank=True, null=True, help_text="Ссылка на видео YouTube")  # 👈 новое поле

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
    
    old_id = models.PositiveIntegerField(
    null=True,
    blank=True,
    unique=True,
    db_index=True,
    help_text="ID клиента в старой системе"
    )
    #Старый айди для миграции
    
    # --- Метки показа попапа ---
    need_stage_popup = models.BooleanField(
        default=False,
        help_text="Нужно ли показать попап при входе"
    )
    stage_popup_shown = models.BooleanField(
        default=False,
        help_text="Попап показан и закрыт пользователем"
    )
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['bitrix_id'],
                condition=~Q(bitrix_id=None),
                name='unique_bitrix_id_not_null'
            )
        ]
    
    def set_stage(self, new_stage: "StageTemplate"):
        """
        Перевод клиента на новую стадию
        и сброс меток попапа.
        """
        self.stage = new_stage
        self.need_stage_popup = True
        self.stage_popup_shown = False
        self.save(update_fields=['stage', 'need_stage_popup', 'stage_popup_shown'])
    
    def __str__(self):
        return f"{self.surname} {self.name} {self.middlename or ''}".strip()

    def current_stage(self):
        return self.stage

    def next_stage(self):
        if self.stage:
            return self.stage.get_next()
        return StageTemplate.objects.order_by('order').first()

    def get_ref_link(self, request=None):
        from django.urls import reverse
        path = reverse("referral_landing", args=[str(self.referral_code)])
        return request.build_absolute_uri(path) if request else path
    

class ReferralClick(models.Model):
    owner_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    owner_object_id = models.PositiveIntegerField(null=True, blank=True)
    owner = GenericForeignKey("owner_content_type", "owner_object_id")

    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("owner_content_type", "owner_object_id", "ip_address")   


class DashboardVisit(models.Model):
    owner_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    owner_object_id = models.PositiveIntegerField(null=True, blank=True)
    owner = GenericForeignKey("owner_content_type", "owner_object_id")

    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    visits = models.JSONField(default=list)  

    class Meta:
        unique_together = ("owner_content_type", "owner_object_id", "ip_address")
        ordering = ["-id"]

    def add_visit(self):
        self.visits.append(timezone.now().isoformat())
        self.save()

    @property
    def visits_count(self):
        return len(self.visits)

    def __str__(self):
        return f"{self.owner} - {self.ip_address} ({len(self.visits)} visits)"


class Application(models.Model):
    client = models.ForeignKey("Client", on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    referral_owner_content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    referral_owner_object_id = models.PositiveIntegerField(null=True, blank=True)
    referral_owner = GenericForeignKey("referral_owner_content_type", "referral_owner_object_id")

    def __str__(self):
        return f"Заявка {self.name} ({self.phone})"