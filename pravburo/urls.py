"""
URL configuration for pravburo project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from clients.views import client_dashboard, redirect_handler, referral_page
from clients.views import CustomLoginView, TestCreateClientView, stage_detail
from django.contrib.auth.views import LogoutView
from payments.views import client_admin_view, recalculate_installment, update_custom_payments, client_search_view, BitrixWebhookCreateClientView, admin_dashboard
from bitrix.views import referral_landing, referral_submit, application_success


urlpatterns = [
    path('admin/', admin.site.urls),
    path("ref/<uuid:referral_code>/", referral_landing, name="referral_landing"),
    path('ref/success/', application_success, name='application_success'),
    path("referral", referral_page, name="referral_page"),
    path("bitrix/webhook/create-client/", BitrixWebhookCreateClientView.as_view(), name="bitrix_create_client"),
    path("ref/submit/", referral_submit, name="referral_submit"),
    path('dashboard/', client_dashboard, name='client_dashboard'),
    path('', redirect_handler, name='index'),
    path('stages/<slug:slug>/', stage_detail, name='stage_detail'),
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path("test-create-client/", TestCreateClientView.as_view(), name="test-create-client"),
    path('admin-panel/', admin_dashboard, name='admin_dashboard'),
    path('client_admin/<int:client_id>/', client_admin_view, name='client_admin_view'),
    path('client_search/', client_search_view, name='client_search'),
    path('client_admin/<int:client_id>/recalculate/', recalculate_installment, name='recalculate_installment'),
    path('client/<int:client_id>/update_custom_payments/', update_custom_payments, name='update_custom_payments'),
]
