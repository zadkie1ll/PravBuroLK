from django.contrib import admin
from django.urls import path
from clients.views import client_dashboard, redirect_handler, referral_page, mark_stage_popup_shown, employee_referral_view
from clients.views import CustomLoginView, TestCreateClientView, stage_detail, dashboard_stats, confident_police
from django.contrib.auth.views import LogoutView
from payments.views import client_admin_view, create_payment, payment_callback, BitrixCreateClientFromDealView, recalculate_installment, update_custom_payments, payments_dashboard, client_search_view, BitrixWebhookCreateClientView, admin_dashboard
from bitrix.views import referral_landing, referral_submit, application_success, referral_stats


urlpatterns = [
    path('admin/', admin.site.urls),
    path("ref/<uuid:referral_code>/", referral_landing, name="referral_landing"),
    path('ref/success/', application_success, name='application_success'),
    path("employee/<int:employee_id>/referral/", employee_referral_view, name="employee_referral"),
    path("referral", referral_page, name="referral_page"),
    path("bitrix/webhook/create-client/", BitrixWebhookCreateClientView.as_view(), name="bitrix_create_client"),
    path("ref/submit/", referral_submit, name="referral_submit"),
    path('dashboard/', client_dashboard, name='client_dashboard'),
    path('', redirect_handler, name='index'),
    path('payment/<int:payment_id>/', create_payment, name='create_payment'),
    path("callback/", payment_callback, name="payment_callback"),
    path('dashboard/stats/', dashboard_stats, name='dashboard_stats'),
    path("mark-stage-popup-shown/", mark_stage_popup_shown, name="mark_stage_popup_shown"),
    path('dashboard/stages/<slug:slug>/', stage_detail, name='stage_detail'),
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    path("bitrix/webhook/create-client-from-deal/", BitrixCreateClientFromDealView.as_view(), name="bitrix_create_client_from_deal"),
    path("payments/dashboard/", payments_dashboard, name="payments_dashboard"),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('admin-panel/referrals/', referral_stats, name='referral_stats'),
    path("test-create-client/", TestCreateClientView.as_view(), name="test-create-client"),
    path('admin-panel/', admin_dashboard, name='admin_dashboard'),
    path('policy/', confident_police, name='police'),
    path('client_admin/<int:client_id>/', client_admin_view, name='client_admin_view'),
    path('client_search/', client_search_view, name='client_search'),
    path('client_admin/<int:client_id>/recalculate/', recalculate_installment, name='recalculate_installment'),
    path('client/<int:client_id>/update_custom_payments/', update_custom_payments, name='update_custom_payments'),
]
