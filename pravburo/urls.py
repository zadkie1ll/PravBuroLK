from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from clients.views import client_dashboard, redirect_handler, referral_page, mark_stage_popup_shown, employee_referral_view
from clients.views import CustomLoginView, TestCreateClientView, stage_detail, dashboard_stats, confident_police, bitrix_deal_webhook
from django.contrib.auth.views import LogoutView
from payments.views import client_admin_view, create_other_payments, delete_other_payment, update_other_payments, update_contract_info, create_installment_payment, create_actual_payments, delete_installment_payment, update_installment_payments, delete_actual_payment, update_actual_payments, client_payments_page, create_other_payment, delete_actual_payment_view, save_actual_payment, create_actual_payment, create_payment, payment_callback, BitrixCreateClientFromDealView, recalculate_installment, update_custom_payments, payments_dashboard, client_search_view, BitrixWebhookCreateClientView, admin_dashboard
from bitrix.views import referral_landing, referral_submit, application_success, referral_stats, build_consultation
from administration.views import casino_page, spin_view
from documents.views import document_form, generate_document, dogovor, parse_legenda
from education_platform.views import auth_api_login, auth_page
from urlshorter.views import generate_url, show_stats

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/createpdf/", build_consultation, name="pdf"),
    path('ai/', parse_legenda, name='ai_engine'),
    # path('casino/', casino_page, name='casino'),
    path("spin/", spin_view, name="spin"),
    path("ref/<uuid:referral_code>/", referral_landing, name="referral_landing"),
    path('ref/success/', application_success, name='application_success'),
    path("employee/<int:employee_id>/referral/", employee_referral_view, name="employee_referral"),
    path("referral", referral_page, name="referral_page"),
    path("bitrix/webhook/create-client/", BitrixWebhookCreateClientView.as_view(), name="bitrix_create_client"),
    path("ref/submit/", referral_submit, name="referral_submit"),
    path('dashboard/', client_dashboard, name='client_dashboard'),
    path('', redirect_handler, name='index'),
    path("create-actual-payment/", create_actual_payment, name="create_actual_payment"),
    path('payment/<int:payment_id>/', create_payment, name='create_payment'),
    path("callback/", payment_callback, name="payment_callback"),
    path("installment/delete/<int:pk>/", delete_installment_payment, name="delete_installment_payment"),
    path("installment/update-all/", update_installment_payments, name="update_installment_payments"),
    path("actual/delete/<int:pk>/", delete_actual_payment, name="delete_actual_payment"),
    path("actual/update-all/", update_actual_payments, name="update_actual_payments"),
    path('dashboard/stats/', dashboard_stats, name='dashboard_stats'),
    path("mark-stage-popup-shown/", mark_stage_popup_shown, name="mark_stage_popup_shown"),
    path('dashboard/stages/<slug:slug>/', stage_detail, name='stage_detail'),
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
    path("webhook_change/", bitrix_deal_webhook, name="bitrix_deal_webhook"),
    path("bitrix/webhook/create-client-from-deal/", BitrixCreateClientFromDealView.as_view(), name="bitrix_create_client_from_deal"),
    path("payments/dashboard/", payments_dashboard, name="payments_dashboard"),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('admin-panel/referrals/', referral_stats, name='referral_stats'),
    path("test-create-client/", TestCreateClientView.as_view(), name="test-create-client"),
    path('admin-panel/', admin_dashboard, name='admin_dashboard'),
    path('policy/', confident_police, name='police'),
    path('contract/<int:contract_id>/update/', update_contract_info, name='update_contract_info'),
    path('save_actual_payment/<int:payment_id>/', save_actual_payment, name='save_actual_payment'),
    path("delete_actual_payment/<int:payment_id>/", delete_actual_payment_view, name="delete_actual_payment"),
    path('client_admin/<int:client_id>/', client_payments_page, name='client_admin_view'),
    path('client_search/', client_search_view, name='client_search'),
    path('other/create/', create_other_payments, name='create_other_payments'),
    path('other/delete/<int:payment_id>/', delete_other_payment, name='delete_other_payment'),
    path('other/update/', update_other_payments, name='update_other_payments'),
    path('create-other-payment/', create_other_payment, name='create_other_payment'),
    path('installment/create/', create_installment_payment, name='create_installment_payment'),
    path('actual/create/', create_actual_payments, name='create_actual_payment'),
    path('client_admin/<int:client_id>/recalculate/', recalculate_installment, name='recalculate_installment'),
    path('client/<int:client_id>/update_custom_payments/', update_custom_payments, name='update_custom_payments'),
    path("form/", document_form, name="document_form"),
    path("generate/", generate_document, name="generate_document"),
    path("dogovor/", dogovor, name="dogovor"),
    path("education/auth/", auth_page, name="education_auth"),
    path("api/education/auth/", auth_api_login, name="education_auth_api"),
    path("url/", generate_url, name="short_url"),
    path("url-stats/", show_stats, name="url-stats"),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )