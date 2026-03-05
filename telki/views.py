from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, render

from .models import March8Greeting
from .services import (
    build_astrology_image_bytes,
    get_numerology_number,
    get_zodiac_sign,
    persist_generated_assets,
)


def greeting_card_view(request, token):
    greeting = get_object_or_404(March8Greeting, token=token, is_active=True)
    zodiac = get_zodiac_sign(greeting.birth_date)
    number = get_numerology_number(greeting.birth_date)
    return render(
        request,
        "telki/card.html",
        {
            "greeting": greeting,
            "zodiac_sign": zodiac,
            "numerology_number": number,
        },
    )


def greeting_certificate_pdf_view(request, token):
    greeting = get_object_or_404(March8Greeting, token=token, is_active=True)
    if not greeting.certificate_pdf:
        persist_generated_assets(greeting, regenerate=False)
        greeting.refresh_from_db(fields=["certificate_pdf"])

    if greeting.certificate_pdf:
        return FileResponse(
            greeting.certificate_pdf.open("rb"),
            as_attachment=True,
            filename=f"8marta-{greeting.recipient_name}.pdf",
            content_type="application/pdf",
        )
    return HttpResponse("PDF не удалось создать", status=500)


def greeting_astrology_image_view(request, token):
    greeting = get_object_or_404(March8Greeting, token=token, is_active=True)
    if greeting.astrology_image:
        return FileResponse(greeting.astrology_image.open("rb"), content_type="image/png")

    img_bytes = build_astrology_image_bytes(greeting)
    return HttpResponse(img_bytes, content_type="image/png")
