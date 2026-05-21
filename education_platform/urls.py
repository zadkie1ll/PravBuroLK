from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.education_login_redirect, name="education_login"),
    path("dashboard/", views.education_dashboard_redirect, name="education_dashboard"),
    path("course/<int:course_id>/", views.education_course_redirect, name="education_course"),
    path("auth/", views.auth_page, name="education_auth"),
    path("hr/", views.hr_content_dashboard, name="education_hr_dashboard"),
    path("hr/trainees/", views.hr_trainee_dashboard, name="education_hr_trainees"),
    path("hr/trainees/new/", views.hr_trainee_create, name="education_hr_trainee_create"),
    path("hr/trainees/<int:profile_id>/", views.hr_trainee_detail, name="education_hr_trainee_detail"),
    path("hr/course/new/", views.hr_course_create, name="education_hr_course_create"),
    path("hr/course/<int:course_id>/edit/", views.hr_course_edit, name="education_hr_course_edit"),
    path("hr/module/new/", views.hr_module_create, name="education_hr_module_create"),
    path("hr/module/<int:module_id>/edit/", views.hr_module_edit, name="education_hr_module_edit"),
    path("hr/module/<int:module_id>/material/new/", views.hr_material_create, name="education_hr_material_create"),
    path("hr/material/<int:material_id>/edit/", views.hr_material_edit, name="education_hr_material_edit"),
    path("hr/material/<int:material_id>/delete/", views.hr_material_delete, name="education_hr_material_delete"),
    path("hr/module/<int:module_id>/test/", views.hr_test_edit, name="education_hr_test_edit"),
    path("hr/test/<int:test_id>/question/new/", views.hr_question_create, name="education_hr_question_create"),
    path("hr/question/<int:question_id>/edit/", views.hr_question_edit, name="education_hr_question_edit"),
    path("hr/question/<int:question_id>/delete/", views.hr_question_delete, name="education_hr_question_delete"),
    path("hr/question/<int:question_id>/option/new/", views.hr_option_create, name="education_hr_option_create"),
    path("hr/option/<int:option_id>/edit/", views.hr_option_edit, name="education_hr_option_edit"),
    path("hr/option/<int:option_id>/delete/", views.hr_option_delete, name="education_hr_option_delete"),
]

api_urlpatterns = [
    path("auth/", views.auth_api_login, name="education_auth_api"),
    path("auth/me/", views.auth_api_me, name="education_auth_me_api"),
    path("reg/", views.auth_api_register, name="education_register_api"),
    path("courses/", views.get_courses, name="education_get_courses"),
    path("modules/", views.get_modules, name="education_get_modules"),
    path("tests/", views.get_test, name="education_get_test"),
    path("tests/submit/", views.submit_test, name="education_submit_test"),
    path("progress/", views.update_module_progress, name="education_update_module_progress"),
    path("modules/<int:module_id>/video/", views.module_video_file, name="education_module_video"),
    path("materials/<int:material_id>/file/", views.module_material_file, name="education_material_file"),
]
