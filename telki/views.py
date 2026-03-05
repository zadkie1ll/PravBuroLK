from django.http import FileResponse, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render

from .models import March8Greeting
from .services import build_astrology_image_bytes, get_numerology_number, get_zodiac_sign


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


def greeting_certificate_link_view(request, token):
    greeting = get_object_or_404(March8Greeting, token=token, is_active=True)
    if greeting.certificate_url:
        return HttpResponseRedirect(greeting.certificate_url)
    return HttpResponse("Ссылка на сертификат не указана", status=404)


def greeting_astrology_image_view(request, token):
    greeting = get_object_or_404(March8Greeting, token=token, is_active=True)
    if greeting.astrology_image:
        return FileResponse(greeting.astrology_image.open("rb"), content_type="image/png")

    img_bytes = build_astrology_image_bytes(greeting)
    return HttpResponse(img_bytes, content_type="image/png")
