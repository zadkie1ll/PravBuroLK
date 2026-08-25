from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path, re_path
from clients.views import client_dashboard, redirect_handler, referral_page, mark_stage_popup_shown, employee_referral_view
from clients.views import CustomLoginView, TestCreateClientView, stage_detail, dashboard_stats, confident_police, bitrix_deal_webhook, setIsBlocked
from django.contrib.auth.views import LogoutView
from payments.views import client_admin_view, create_other_payments, delete_other_payment, update_other_payments, update_contract_info, create_installment_payment, create_actual_payments, delete_installment_payment, update_installment_payments, delete_actual_payment, update_actual_payments, client_payments_page, create_other_payment, delete_actual_payment_view, save_actual_payment, create_actual_payment, create_payment, payment_callback, BitrixCreateClientFromDealView, recalculate_installment, update_custom_payments, payments_dashboard, client_search_view, BitrixWebhookCreateClientView, admin_dashboard
from bitrix.views import referral_landing, referral_submit, application_success, referral_stats, build_consultation, sync_regions_from_bitrix, calc_km_for_deal, test
from administration.views import casino_page, spin_view
from leadreport.views import (
    lead_admin_dashboard,
    lead_admin_manager_detail,
    lead_my_stats_page,
    internal_sales_managers_list,
    internal_sales_manager_lookup,
)
from documents.views import contract_confirmation_page, contract_document_file, contract_payment_redirect, document_form, generate_document, dogovor, dogovor_mfc, parse_legenda
from lead_control.views import deal_webhook_handler
from communications.views import bitrix_call_webhook, download_call_to_server, manual_analyze_last_call
from education_platform import urls as education_urls
from urlshorter.views import generate_url, show_stats
from yclients.views import yclients_webhook
from client_withdrawals.views import client_withdrawals_page, create_withdrawal_record, update_withdrawal_record, delete_withdrawal_record, internal_client_tail_amount
urlpatterns = [
    path('admin/', admin.site.urls),
    path("education/", include("education_platform.urls")),
    path("api/education/", include(education_urls.api_urlpatterns)),
    path("call-queue/", include("call_queue.urls")),
    path("march/", include("telki.urls")),
    path("api/calc-km/", calc_km_for_deal, name="calc_km_for_deal"),
    path("api/sync-regions/", sync_regions_from_bitrix, name="sync_regions_from_bitrix"),
    path("api/createpdf/", build_consultation, name="pdf"),
    path('ai/', parse_legenda, name='ai_engine'),
    # path('casino/', casino_page, name='casino'),
    path("spin/", spin_view, name="spin"),
    path("webhook/deal/", deal_webhook_handler, name="parsedealdataOM"),
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
    path("client-withdrawals/<int:client_id>/", client_withdrawals_page, name="client_withdrawals_page"),
    path("client-withdrawals/<int:client_id>/create/", create_withdrawal_record, name="create_withdrawal_record"),
    path("client-withdrawals/update/<int:record_id>/", update_withdrawal_record, name="update_withdrawal_record"),
    path("client-withdrawals/delete/<int:record_id>/", delete_withdrawal_record, name="delete_withdrawal_record"),
    path("api/internal/clients/<int:client_id>/tail-amount/", internal_client_tail_amount, name="internal_client_tail_amount"),
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
    path("dogovor-mfc/", dogovor_mfc, name="dogovor_mfc"),
    path("dogovor/<int:deal_id>/", contract_confirmation_page, name="contract_confirmation_page"),
    path("dogovor/<int:deal_id>/document/", contract_document_file, name="contract_document_file"),
    path("dogovor/<int:deal_id>/pay/", contract_payment_redirect, name="contract_payment_redirect"),
    path("url/", generate_url, name="short_url"),
    path("url-stats/", show_stats, name="url-stats"),
    path("yclients-webhook/", yclients_webhook),
    path('bitrix/webhook/call-end/', bitrix_call_webhook),
    path('download_call', download_call_to_server),
    re_path(r'^api/setIsBlocked/*$', setIsBlocked, name='set_is_blocked'),
    path('api/testt/', test),
    path("my/", lead_my_stats_page, name="my_stats"),
    path("leadreport/managerdashboard/", lead_admin_dashboard, name="lead_admin_dashboard"),
    path("leadreport/manager/<int:manager_id>/", lead_admin_manager_detail, name="admin_manager_detail"),
    path('api/manualAnalyze/', manual_analyze_last_call),
    path("api/internal/sales-managers/", internal_sales_managers_list, name="internal_sales_managers_list"),
    path("api/internal/sales-managers/lookup/", internal_sales_manager_lookup, name="internal_sales_manager_lookup"),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
