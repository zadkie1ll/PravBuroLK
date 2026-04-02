from django.urls import path
from django.views.generic import RedirectView

from . import views


app_name = "call_queue"

urlpatterns = [
    path("", views.production_handler, name="production_handler"),
    path("", views.production_handler, name="dashboard"),
    path("handler/", RedirectView.as_view(pattern_name="call_queue:production_handler", permanent=False), name="production_handler_legacy"),
    path("session/<int:session_id>/", views.call_session_detail, name="session_detail"),
    path("handler/status/", views.production_handler_status, name="production_handler_status"),
    path("handler/resolve/", views.production_handler_resolve, name="production_handler_resolve"),
    path("handler/auto-next/", views.production_handler_auto_next, name="production_handler_auto_next"),
    path("megafon/test-call/", views.megafon_test_call, name="megafon_test_call"),
    path("megafon/call-status/", views.megafon_call_status, name="megafon_call_status"),
    path("megafon/resolve-call/", views.megafon_resolve_call, name="megafon_resolve_call"),
    path("megafon/auto-next/", views.megafon_auto_next_call, name="megafon_auto_next_call"),
    path("megafon/webhook/", views.megafon_webhook, name="megafon_webhook"),
]
