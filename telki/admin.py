from django.contrib import admin
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html
from django.utils.text import slugify
from io import BytesIO
import zipfile

from PIL import Image, ImageDraw, ImageFont
from reportlab.graphics.barcode import qr as reportlab_qr

from .models import March8Greeting
from .services import get_numerology_number, get_zodiac_sign, persist_generated_assets


def _load_font(size: int) -> ImageFont.ImageFont:
    font_candidates = (
        "static/fonts/SF-Pro.ttf",
        "static/fonts/tt-norms-medium.otf",
        "static/fonts/gilroy-light.otf",
    )
    for path in font_candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _build_qr_card_png(url: str, recipient_name: str) -> bytes:
    width, height = 1080, 1350
    img = Image.new("RGB", (width, height), "#eef2ff")
    draw = ImageDraw.Draw(img)

    # subtle background accents
    draw.ellipse((-240, -140, 460, 520), fill="#dbeafe")
    draw.ellipse((620, 760, 1300, 1450), fill="#bfdbfe")

    # main card container
    card_box = (90, 90, width - 90, height - 90)
    draw.rounded_rectangle(card_box, radius=48, fill="white", outline="#dbeafe", width=4)

    title_font = _load_font(56)
    subtitle_font = _load_font(32)
    name_font = _load_font(48)
    small_font = _load_font(28)

    draw.text((150, 150), "8 Марта", fill="#1d4ed8", font=title_font)
    draw.text((150, 230), "Персональная карточка", fill="#475569", font=subtitle_font)

    # QR area
    qr_outer = (150, 320, width - 150, 980)
    draw.rounded_rectangle(qr_outer, radius=34, fill="#f8fafc", outline="#cbd5e1", width=3)

    qr_widget = reportlab_qr.QrCodeWidget(url)
    qr_code = qr_widget.qr
    qr_code.make()
    modules = qr_code.getModuleCount()
    qr_size = 620
    cell = max(1, qr_size // modules)
    rendered_size = cell * modules
    offset_x = (width - rendered_size) // 2
    offset_y = 340

    draw.rectangle(
        (offset_x - 24, offset_y - 24, offset_x + rendered_size + 24, offset_y + rendered_size + 24),
        fill="white",
    )
    for y in range(modules):
        for x in range(modules):
            if qr_code.isDark(y, x):
                x1 = offset_x + x * cell
                y1 = offset_y + y * cell
                draw.rectangle((x1, y1, x1 + cell - 1, y1 + cell - 1), fill="#0f172a")

    safe_name = (recipient_name or "Без имени").strip()
    draw.text((150, 1030), safe_name, fill="#0f172a", font=name_font)
    draw.text((150, 1110), "Сканируйте QR, чтобы открыть открытку", fill="#475569", font=small_font)

    output = BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()


@admin.register(March8Greeting)
class March8GreetingAdmin(admin.ModelAdmin):
    list_display = (
        "recipient_name",
        "birth_date",
        "zodiac_display",
        "numerology_display",
        "has_astrology_image",
        "has_certificate_pdf",
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
        "preview_pdf_link",
    )
    actions = ("generate_selected_assets", "regenerate_selected_assets", "generate_qr_codes")
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
                    "certificate_pdf",
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
                    "preview_pdf_link",
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

    @admin.display(description="PDF")
    def has_certificate_pdf(self, obj):
        return bool(obj.certificate_pdf)

    @admin.display(description="Открыть карточку")
    def preview_card_link(self, obj):
        if not obj.pk:
            return "Сохраните объект"
        url = reverse("telki:card", args=[obj.token])
        return format_html('<a href="{}" target="_blank">Открыть</a>', url)

    @admin.display(description="Скачать PDF")
    def preview_pdf_link(self, obj):
        if not obj.pk:
            return "Сохраните объект"
        url = reverse("telki:certificate-pdf", args=[obj.token])
        return format_html('<a href="{}" target="_blank">Скачать</a>', url)

    @admin.action(description="Сгенерировать картинку и PDF")
    def generate_selected_assets(self, request, queryset):
        count = 0
        for obj in queryset:
            persist_generated_assets(obj, regenerate=False)
            count += 1
        self.message_user(request, f"Готово: обработано {count} записей.")

    @admin.action(description="Перегенерировать картинку и PDF")
    def regenerate_selected_assets(self, request, queryset):
        count = 0
        for obj in queryset:
            persist_generated_assets(obj, regenerate=True)
            count += 1
        self.message_user(request, f"Готово: перегенерировано {count} записей.")

    @admin.action(description="Сгенерировать QR-коды карточек (ZIP)")
    def generate_qr_codes(self, request, queryset):
        if not queryset.exists():
            self.message_user(request, "Ничего не выбрано.")
            return None

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for obj in queryset:
                card_url = request.build_absolute_uri(reverse("telki:card", args=[obj.token]))
                png_bytes = _build_qr_card_png(card_url, obj.recipient_name)
                safe_name = slugify(obj.recipient_name or "bez-imeni", allow_unicode=True) or f"greeting-{obj.pk}"
                zf.writestr(f"{safe_name}-qr.png", png_bytes)

        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = 'attachment; filename="march8-qr-cards.zip"'
        return response
