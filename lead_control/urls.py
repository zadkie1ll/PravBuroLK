from django.urls import path
from .views import deal_webhook_handler

urlpatterns = [
    path('webhook/deal/', deal_webhook_handler, name='lead_control_deal_webhook'),
]