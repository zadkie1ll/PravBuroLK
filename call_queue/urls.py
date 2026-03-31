from django.urls import path

from . import views


app_name = "call_queue"

urlpatterns = [
    path("", views.call_queue_dashboard, name="dashboard"),
    path("session/<int:session_id>/", views.call_session_detail, name="session_detail"),
    path("megafon/test-call/", views.megafon_test_call, name="megafon_test_call"),
    path("megafon/call-status/", views.megafon_call_status, name="megafon_call_status"),
    path("megafon/webhook/", views.megafon_webhook, name="megafon_webhook"),
]
