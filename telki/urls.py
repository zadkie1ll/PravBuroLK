from django.urls import path

from .views import (
    greeting_astrology_image_view,
    greeting_card_view,
    greeting_certificate_link_view,
)

app_name = "telki"

urlpatterns = [
    path("<uuid:token>/", greeting_card_view, name="card"),
    path("<uuid:token>/certificate", greeting_certificate_link_view, name="certificate-link"),
    path("<uuid:token>/astrology.png", greeting_astrology_image_view, name="astrology-image"),
]
