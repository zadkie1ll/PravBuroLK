from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import March8Greeting
from .services import get_numerology_number, get_zodiac_sign, persist_generated_assets


@admin.register(March8Greeting)
class March8GreetingAdmin(admin.ModelAdmin):
    list_display = (
        "recipient_name",
        "birth_date",
        "zodiac_display",
        "numerology_display",
        "has_astrology_image",
        "has_certificate_url",
        "is_active",
    )
    list_filter = ("is_active", "birth_date")
    search_fields = ("recipient_name", "client__name", "client__surname", "client__middlename")
    readonly_fields = (
        "token",
        "created_at",
        "updated_at",
        "zodiac_display",
        "numerology_display",
        "preview_card_link",
        "preview_certificate_link",
    )
    actions = ("generate_selected_assets", "regenerate_selected_assets")
    autocomplete_fields = ("client",)

    fieldsets = (
        (
            "Основное",
            {
                "fields": (
                    "client",
                    "recipient_name",
                    "birth_date",
                    "personal_text",
                    "is_active",
                )
            },
        ),
        (
            "Материалы",
            {
                "fields": (
                    "custom_background",
                    "astrology_image",
                    "certificate_url",
                )
            },
        ),
        (
            "Авторасчет",
            {
                "fields": (
                    "zodiac_display",
                    "numerology_display",
                    "preview_card_link",
                    "preview_certificate_link",
                )
            },
        ),
        ("Служебное", {"fields": ("token", "created_at", "updated_at")}),
    )

    @admin.display(description="Знак зодиака")
    def zodiac_display(self, obj):
        return get_zodiac_sign(obj.birth_date)

    @admin.display(description="Нумерология")
    def numerology_display(self, obj):
        return get_numerology_number(obj.birth_date)

    @admin.display(description="Астрокартинка")
    def has_astrology_image(self, obj):
        return bool(obj.astrology_image)

    @admin.display(description="Сертификат")
    def has_certificate_url(self, obj):
        return bool(obj.certificate_url)

    @admin.display(description="Открыть карточку")
    def preview_card_link(self, obj):
        if not obj.pk:
            return "Сохраните объект"
        url = reverse("telki:card", args=[obj.token])
        return format_html('<a href="{}" target="_blank">Открыть</a>', url)

    @admin.display(description="Открыть сертификат")
    def preview_certificate_link(self, obj):
        if not obj.pk:
            return "Сохраните объект"
        url = reverse("telki:certificate-link", args=[obj.token])
        return format_html('<a href="{}" target="_blank">Открыть</a>', url)

    @admin.action(description="Сгенерировать картинку")
    def generate_selected_assets(self, request, queryset):
        count = 0
        for obj in queryset:
            persist_generated_assets(obj, regenerate=False)
            count += 1
        self.message_user(request, f"Готово: обработано {count} записей.")

    @admin.action(description="Перегенерировать картинку")
    def regenerate_selected_assets(self, request, queryset):
        count = 0
        for obj in queryset:
            persist_generated_assets(obj, regenerate=True)
            count += 1
        self.message_user(request, f"Готово: перегенерировано {count} записей.")
