from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from clients.views import client_dashboard, redirect_handler, referral_page, mark_stage_popup_shown, employee_referral_view
from clients.views import CustomLoginView, TestCreateClientView, stage_detail, dashboard_stats, confident_police, bitrix_deal_webhook, setIsBlocked
from django.contrib.auth.views import LogoutView
from payments.views import client_admin_view, create_other_payments, delete_other_payment, update_other_payments, update_contract_info, create_installment_payment, create_actual_payments, delete_installment_payment, update_installment_payments, delete_actual_payment, update_actual_payments, client_payments_page, create_other_payment, delete_actual_payment_view, save_actual_payment, create_actual_payment, create_payment, payment_callback, BitrixCreateClientFromDealView, recalculate_installment, update_custom_payments, payments_dashboard, client_search_view, BitrixWebhookCreateClientView, admin_dashboard
from bitrix.views import referral_landing, referral_submit, application_success, referral_stats, build_consultation, sync_regions_from_bitrix, calc_km_for_deal, test
from administration.views import casino_page, spin_view
from leadreport.views import get_stats
from documents.views import document_form, generate_document, dogovor, parse_legenda
from communications.views import bitrix_call_webhook, download_call_to_server, manual_analyze_last_call
from education_platform.views import (
    auth_api_login,
    auth_api_register,
    auth_page,
    get_courses,
    get_modules,
    get_test,
    hr_content_dashboard,
    hr_course_create,
    hr_course_edit,
    hr_module_create,
    hr_module_edit,
    hr_option_create,
    hr_option_delete,
    hr_option_edit,
    hr_question_create,
    hr_question_delete,
    hr_question_edit,
    hr_test_edit,
    submit_test,
    update_module_progress,
)
from urlshorter.views import generate_url, show_stats
from yclients.views import yclients_webhook
urlpatterns = [
    path('admin/', admin.site.urls),
    path("march/", include("telki.urls")),
    path("api/calc-km/", calc_km_for_deal, name="calc_km_for_deal"),
    path("api/sync-regions/", sync_regions_from_bitrix, name="sync_regions_from_bitrix"),
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
    path("api/education/reg/", auth_api_register, name="education_register_api"),
    path("api/education/get_courses", get_courses, name="education_get_courses"),
    path("api/education/get_modules", get_modules, name="education_get_modules"),
    path("api/get_test", get_test, name="education_get_test"),
    path("api/submit_test/", submit_test, name="education_submit_test"),
    path("api/update_module_progress/", update_module_progress, name="education_update_module_progress"),
    path("education/hr/", hr_content_dashboard, name="education_hr_dashboard"),
    path("education/hr/course/new/", hr_course_create, name="education_hr_course_create"),
    path("education/hr/course/<int:course_id>/edit/", hr_course_edit, name="education_hr_course_edit"),
    path("education/hr/module/new/", hr_module_create, name="education_hr_module_create"),
    path("education/hr/module/<int:module_id>/edit/", hr_module_edit, name="education_hr_module_edit"),
    path("education/hr/module/<int:module_id>/test/", hr_test_edit, name="education_hr_test_edit"),
    path("education/hr/test/<int:test_id>/question/new/", hr_question_create, name="education_hr_question_create"),
    path("education/hr/question/<int:question_id>/edit/", hr_question_edit, name="education_hr_question_edit"),
    path("education/hr/question/<int:question_id>/delete/", hr_question_delete, name="education_hr_question_delete"),
    path("education/hr/question/<int:question_id>/option/new/", hr_option_create, name="education_hr_option_create"),
    path("education/hr/option/<int:option_id>/edit/", hr_option_edit, name="education_hr_option_edit"),
    path("education/hr/option/<int:option_id>/delete/", hr_option_delete, name="education_hr_option_delete"),
    path("url/", generate_url, name="short_url"),
    path("url-stats/", show_stats, name="url-stats"),
    path("yclients-webhook/", yclients_webhook),
    path('bitrix/webhook/call-end/', bitrix_call_webhook),
    path('download_call', download_call_to_server),
    path('api/setIsBlocked/', setIsBlocked),
    path('api/testt/', test),
    path('api/getManagerCalls/', get_stats),
    path('api/manualAnalyze/', manual_analyze_last_call)
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
