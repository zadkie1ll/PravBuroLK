from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Course, Department, Module, TraineeProfile


class EducationAuthFlowTests(TestCase):
    def setUp(self):
        self.department, _ = Department.objects.get_or_create(code="sales", defaults={"name": "Продажи"})

    def test_login_requires_department_for_legacy_profile_without_department(self):
        User = get_user_model()
        User.objects.create_user(username="student", password="secret")

        response = self.client.post(
            reverse("education_auth_api"),
            {"username": "student", "password": "secret"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.json()["needs_department"])

    def test_login_can_attach_department_and_load_courses_from_session(self):
        User = get_user_model()
        user = User.objects.create_user(username="student", password="secret")
        TraineeProfile.objects.create(user=user)
        course = Course.objects.create(name="Онбординг", is_active=True)
        course.departments.add(self.department)
        Module.objects.create(course=course, name="Урок", is_active=True)

        login_response = self.client.post(
            reverse("education_auth_api"),
            {"username": "student", "password": "secret", "department": "sales"},
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.json()["user"]["department"], "sales")

        courses_response = self.client.get(reverse("education_get_courses"))
        self.assertEqual(courses_response.status_code, 200)
        course_names = {item["name"] for item in courses_response.json()["courses"]}
        self.assertIn("Онбординг", course_names)

    def test_user_with_multiple_departments_gets_courses_from_all_departments(self):
        marketing, _ = Department.objects.get_or_create(code="marketing", defaults={"name": "Маркетинг"})
        User = get_user_model()
        user = User.objects.create_user(username="multi", password="secret")
        profile = TraineeProfile.objects.create(user=user)
        profile.departments.set([self.department, marketing])

        sales_course = Course.objects.create(name="Продажи", is_active=True)
        sales_course.departments.add(self.department)
        Module.objects.create(course=sales_course, name="Продажный урок", is_active=True)
        marketing_course = Course.objects.create(name="Маркетинг", is_active=True)
        marketing_course.departments.add(marketing)
        Module.objects.create(course=marketing_course, name="Маркетинговый урок", is_active=True)

        self.client.force_login(user)
        response = self.client.get(reverse("education_get_courses"))

        self.assertEqual(response.status_code, 200)
        course_names = {item["name"] for item in response.json()["courses"]}
        self.assertIn("Продажи", course_names)
        self.assertIn("Маркетинг", course_names)
