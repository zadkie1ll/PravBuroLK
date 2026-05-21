import json
import mimetypes
import re
import secrets
import string
from functools import wraps

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .forms import (
    CourseForm,
    ModuleForm,
    ModuleMaterialForm,
    ModuleTestForm,
    QuestionOptionForm,
    TestQuestionForm,
    TraineeAccountForm,
    TraineeDepartmentsForm,
)
from .models import (
    AnswerError,
    Course,
    Department,
    LearningProgress,
    Module,
    ModuleMaterial,
    ModuleTest,
    QuestionOption,
    TestAttempt,
    TestQuestion,
    TraineeProfile,
)


def auth_page(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"detail": "Use frontend app for auth"}, status=200)


def education_login_redirect(request: HttpRequest) -> HttpResponse:
    return redirect("/auth")


def education_dashboard_redirect(request: HttpRequest) -> HttpResponse:
    return redirect("/dashboard")


def education_course_redirect(request: HttpRequest, course_id: int) -> HttpResponse:
    return redirect(f"/course/{course_id}")


def _profile_department(profile: TraineeProfile) -> str:
    return next(iter(_profile_department_codes(profile)), "")


def _profile_department_codes(profile: TraineeProfile) -> list[str]:
    codes = list(profile.departments.filter(is_active=True).values_list("code", flat=True))
    legacy_code = str((profile.stats or {}).get("department", "")).strip()
    if legacy_code and legacy_code not in codes:
        codes.append(legacy_code)
    return codes


def _profile_department_payload(profile: TraineeProfile) -> list[dict]:
    departments = list(profile.departments.filter(is_active=True).values("code", "name"))
    department_codes = {department["code"] for department in departments}
    legacy_code = str((profile.stats or {}).get("department", "")).strip()
    if legacy_code and legacy_code not in department_codes:
        legacy_department = Department.objects.filter(code=legacy_code, is_active=True).first()
        if legacy_department:
            departments.append({"code": legacy_department.code, "name": legacy_department.name})
    return departments


def _ensure_profile(user, department: str | None = None) -> TraineeProfile:
    profile, _ = TraineeProfile.objects.get_or_create(user=user)
    if department:
        stats = profile.stats or {}
        stats["department"] = department
        profile.stats = stats
        profile.save(update_fields=["stats", "updated_at"])
        department_obj = Department.objects.filter(code=department, is_active=True).first()
        if department_obj:
            profile.departments.add(department_obj)
    return profile


def _serialize_user(user, profile: TraineeProfile) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "department": _profile_department(profile),
        "departments": _profile_department_payload(profile),
    }


def _user_can_access_course(user, profile: TraineeProfile, course: Course) -> bool:
    if user.is_staff:
        return True
    department_codes = _profile_department_codes(profile)
    if not department_codes:
        return False
    return course.departments.filter(code__in=department_codes, is_active=True).exists()


def _get_accessible_module_or_404(user, profile: TraineeProfile, module_id: int) -> Module:
    module = get_object_or_404(
        Module.objects.select_related("course").prefetch_related("course__departments"),
        pk=module_id,
        is_active=True,
        course__is_active=True,
    )
    if not _user_can_access_course(user, profile, module.course):
        raise Http404("Модуль не найден")
    return module


def _stream_file_range(file_field, request: HttpRequest, content_type: str, filename: str) -> HttpResponse:
    file_size = file_field.size
    range_header = request.headers.get("Range", "")
    range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)

    if not range_match:
        response = FileResponse(file_field.open("rb"), content_type=content_type)
        response["Content-Length"] = str(file_size)
        response["Accept-Ranges"] = "bytes"
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        response["Cache-Control"] = "private, no-store"
        return response

    start = int(range_match.group(1))
    end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
    end = min(end, file_size - 1)
    length = end - start + 1

    source = file_field.open("rb")
    source.seek(start)

    def iterator():
        remaining = length
        try:
            while remaining > 0:
                chunk = source.read(min(8192, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk
        finally:
            source.close()

    response = StreamingHttpResponse(iterator(), status=206, content_type=content_type)
    response["Content-Length"] = str(length)
    response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    response["Accept-Ranges"] = "bytes"
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    response["Cache-Control"] = "private, no-store"
    return response


def _generate_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _sync_legacy_department(profile: TraineeProfile) -> None:
    first_department = profile.departments.filter(is_active=True).order_by("name").first()
    stats = profile.stats or {}
    if first_department:
        stats["department"] = first_department.code
    else:
        stats.pop("department", None)
    profile.stats = stats
    profile.save(update_fields=["stats", "updated_at"])


@require_POST
@csrf_exempt
def auth_api_register(request: HttpRequest) -> JsonResponse:
    username = (request.POST.get("username") or "").strip()
    password = request.POST.get("password") or ""
    department = (request.POST.get("department") or "").strip()

    if not username or not password or not department:
        return JsonResponse({"detail": "username, password and department required"}, status=400)

    if not Department.objects.filter(code=department, is_active=True).exists():
        return JsonResponse({"detail": "Неизвестный отдел"}, status=400)

    User = get_user_model()
    if User.objects.filter(username=username).exists():
        return JsonResponse({"detail": "Пользователь уже существует"}, status=409)

    user = User.objects.create_user(username=username, password=password)
    profile = _ensure_profile(user, department=department)
    login(request, user)
    return JsonResponse({"detail": "ok", "user": _serialize_user(user, profile)}, status=201)


@require_POST
@csrf_exempt
def auth_api_login(request: HttpRequest) -> JsonResponse:
    username = (request.POST.get("username") or "").strip()
    password = request.POST.get("password") or ""
    department = (request.POST.get("department") or "").strip()

    if not username or not password:
        return JsonResponse({"detail": "username and password required"}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({"detail": "Неверный логин или пароль"}, status=401)
    if not user.is_active:
        return JsonResponse({"detail": "Пользователь деактивирован"}, status=403)

    profile = _ensure_profile(user)
    if not _profile_department_codes(profile):
        if not department:
            return JsonResponse({"detail": "Укажите отдел", "needs_department": True}, status=400)
        if not Department.objects.filter(code=department, is_active=True).exists():
            return JsonResponse({"detail": "Неизвестный отдел"}, status=400)
        profile = _ensure_profile(user, department=department)

    login(request, user)
    return JsonResponse({"detail": "ok", "user": _serialize_user(user, profile)})


@require_GET
@login_required
def auth_api_me(request: HttpRequest) -> JsonResponse:
    profile = _ensure_profile(request.user)
    return JsonResponse({"detail": "ok", "user": _serialize_user(request.user, profile)})


@require_GET
@login_required
def get_courses(request: HttpRequest) -> JsonResponse:
    profile = _ensure_profile(request.user)
    department = (request.GET.get("department") or "").strip()
    department_codes = _profile_department_codes(profile)

    if request.user.is_staff and Department.objects.filter(code=department, is_active=True).exists():
        department_codes = [department]
    if not department_codes:
        return JsonResponse({"detail": "Отдел не указан"}, status=400)

    courses_qs = (
        Course.objects.filter(is_active=True, departments__code__in=department_codes, departments__is_active=True)
        .distinct()
        .annotate(modules_count=Count("modules", filter=Q(modules__is_active=True)))
    )

    module_ids = list(
        Module.objects.filter(course__in=courses_qs, is_active=True).values_list("id", flat=True)
    )
    progress_map = {
        row["block_id"]: row["status"]
        for row in LearningProgress.objects.filter(trainee=profile, block_id__in=module_ids).values("block_id", "status")
    }

    courses = []
    for course in courses_qs:
        course_module_ids = list(course.modules.filter(is_active=True).values_list("id", flat=True))
        completed_modules = sum(
            1
            for module_id in course_module_ids
            if progress_map.get(module_id) == LearningProgress.Status.COMPLETED
        )
        courses.append(
            {
                "id": course.id,
                "name": course.name,
                "description": course.description,
                "image_url": course.image_url,
                "photo_url": course.photo_url,
                "modules_count": course.modules_count,
                "completed_modules": completed_modules,
            }
        )

    return JsonResponse({"detail": "ok", "courses": courses})


@require_GET
@login_required
def get_modules(request: HttpRequest) -> JsonResponse:
    profile = _ensure_profile(request.user)
    try:
        course_id = int(request.GET.get("course"))
    except (TypeError, ValueError):
        return JsonResponse({"detail": "Неверный course id"}, status=400)

    course = get_object_or_404(Course, pk=course_id, is_active=True)
    if not _user_can_access_course(request.user, profile, course):
        return JsonResponse({"detail": "Курс не найден"}, status=404)
    modules_qs = course.modules.filter(is_active=True).order_by("order", "id")
    progress_map = {
        row["block_id"]: row["status"]
        for row in LearningProgress.objects.filter(
            trainee=profile,
            block_id__in=list(modules_qs.values_list("id", flat=True)),
        ).values("block_id", "status")
    }

    modules = []
    for module in modules_qs:
        materials = [
            {
                "id": material.id,
                "title": material.title,
                "material_type": material.material_type,
                "url": f"/api/education/materials/{material.id}/file/",
                "order": material.order,
            }
            for material in module.materials.filter(is_active=True).order_by("order", "id")
        ]
        modules.append(
            {
                "id": module.id,
                "name": module.name,
                "description": module.description,
                "video_url": f"/api/education/modules/{module.id}/video/" if module.private_video else module.video_url,
                "video_is_private": bool(module.private_video),
                "materials": materials,
                "order": module.order,
                "status": progress_map.get(module.id, LearningProgress.Status.NOT_STARTED),
            }
        )
    return JsonResponse({"detail": "ok", "modules": modules})


def _serialize_test(test: ModuleTest) -> dict:
    questions = []
    for question in test.questions.all().order_by("order", "id"):
        options = [
            {"id": option.id, "text": option.text}
            for option in question.options.all().order_by("order", "id")
        ]
        questions.append(
            {
                "id": question.id,
                "text": question.text,
                "question_type": question.question_type,
                "options": options,
                "score": question.score,
                "order": question.order,
            }
        )
    return {
        "id": test.id,
        "name": test.name,
        "description": test.description,
        "max_score": test.max_score,
        "passing_score": test.passing_score,
        "max_attempts": test.max_attempts,
        "questions": questions,
    }


@require_GET
@login_required
def get_test(request: HttpRequest) -> JsonResponse:
    profile = _ensure_profile(request.user)
    try:
        module_id = int(request.GET.get("module"))
    except (TypeError, ValueError):
        return JsonResponse({"detail": "Неверный module id"}, status=400)

    module = _get_accessible_module_or_404(request.user, profile, module_id)
    module = Module.objects.select_related("test").prefetch_related("test__questions__options").get(pk=module.pk)
    if not hasattr(module, "test") or not module.test.is_active:
        return JsonResponse({"detail": "Тест не найден"}, status=404)

    test = module.test
    attempts_used = TestAttempt.objects.filter(trainee=profile, test_id=test.id).aggregate(
        count=Count("id", filter=Q(status__in=[TestAttempt.Status.COMPLETED, TestAttempt.Status.FAILED]))
    )["count"] or 0
    attempts_left = max(test.max_attempts - attempts_used, 0)
    payload = _serialize_test(test)
    payload["attempts_left"] = attempts_left
    return JsonResponse({"detail": "ok", "test": payload})


@require_POST
@csrf_exempt
@login_required
def update_module_progress(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Некорректный JSON"}, status=400)

    profile = _ensure_profile(request.user)
    try:
        module_id = int(payload.get("module_id"))
    except (TypeError, ValueError):
        return JsonResponse({"detail": "Неверный module_id"}, status=400)
    status = str(payload.get("status") or "").strip()
    allowed_status = {item[0] for item in LearningProgress.Status.choices}
    if status not in allowed_status:
        return JsonResponse({"detail": "Некорректный статус"}, status=400)
    module = _get_accessible_module_or_404(request.user, profile, module_id)
    if status == LearningProgress.Status.COMPLETED and hasattr(module, "test") and module.test.is_active and module.test.questions.exists():
        passed = TestAttempt.objects.filter(
            trainee=profile,
            test_id=module.test.id,
            status=TestAttempt.Status.COMPLETED,
            passed=True,
        ).exists()
        if not passed:
            return JsonResponse({"detail": "Сначала нужно пройти тест"}, status=400)

    now = timezone.now()
    progress, _ = LearningProgress.objects.get_or_create(
        trainee=profile,
        block_id=module_id,
        defaults={
            "status": status,
            "started_at": now if status in {LearningProgress.Status.IN_PROGRESS, LearningProgress.Status.COMPLETED} else None,
            "completed_at": now if status == LearningProgress.Status.COMPLETED else None,
            "last_activity_at": now,
        },
    )

    if progress.status != status:
        progress.status = status
        if status == LearningProgress.Status.IN_PROGRESS and not progress.started_at:
            progress.started_at = now
        if status == LearningProgress.Status.COMPLETED:
            progress.completed_at = now
        progress.last_activity_at = now
        progress.save(update_fields=["status", "started_at", "completed_at", "last_activity_at", "updated_at"])

    return JsonResponse({"detail": "ok", "module_id": module_id, "status": progress.status})


def _evaluate_question(question: TestQuestion, answer_payload: dict) -> tuple[bool, dict, dict]:
    options = list(question.options.all())
    correct_options = [option for option in options if option.is_correct]
    correct_ids = {option.id for option in correct_options}

    if question.question_type == TestQuestion.QuestionType.CHOICE:
        user_id = answer_payload.get("id")
        is_correct = user_id in correct_ids and len(correct_ids) == 1
        return is_correct, {"id": user_id}, {"id": next(iter(correct_ids), None)}

    if question.question_type == TestQuestion.QuestionType.MULTI_CHOICE:
        user_ids = set(answer_payload.get("ids") or [])
        is_correct = user_ids == correct_ids
        return is_correct, {"ids": sorted(user_ids)}, {"ids": sorted(correct_ids)}

    user_text = str(answer_payload.get("text") or "").strip().lower()
    expected_texts = [option.text.strip().lower() for option in correct_options if option.text.strip()]
    if expected_texts:
        is_correct = user_text in expected_texts
        return is_correct, {"text": user_text}, {"text": expected_texts}
    is_correct = bool(user_text)
    return is_correct, {"text": user_text}, {"text": "any non-empty text"}


@require_POST
@csrf_exempt
@login_required
def submit_test(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Некорректный JSON"}, status=400)

    profile = _ensure_profile(request.user)
    try:
        module_id = int(payload.get("module_id"))
    except (TypeError, ValueError):
        return JsonResponse({"detail": "Неверный module_id"}, status=400)
    answers = payload.get("answers") or {}
    _get_accessible_module_or_404(request.user, profile, module_id)
    module = get_object_or_404(
        Module.objects.select_related("test").prefetch_related(Prefetch("test__questions", queryset=TestQuestion.objects.prefetch_related("options"))),
        pk=module_id,
        is_active=True,
    )
    if not hasattr(module, "test") or not module.test.is_active:
        return JsonResponse({"detail": "Тест не найден"}, status=404)

    test = module.test
    if not test.questions.exists():
        return JsonResponse({"detail": "В тесте нет вопросов"}, status=400)
    attempts_total = TestAttempt.objects.filter(trainee=profile, test_id=test.id).count()
    if attempts_total >= test.max_attempts:
        return JsonResponse({"detail": "Попытки закончились", "attempts_left": 0, "passed": False, "score": 0}, status=400)

    score = 0.0
    dynamic_max = 0.0
    questions = list(test.questions.all().order_by("order", "id"))
    now = timezone.now()

    attempt = TestAttempt.objects.create(
        trainee=profile,
        test_id=test.id,
        status=TestAttempt.Status.IN_PROGRESS,
        attempt_number=attempts_total + 1,
        meta={"answers": answers, "module_id": module_id},
    )

    for question in questions:
        dynamic_max += question.score
        answer_payload = answers.get(str(question.id)) or answers.get(question.id) or {}
        is_correct, user_answer, correct_answer = _evaluate_question(question, answer_payload)
        if is_correct:
            score += question.score
        else:
            AnswerError.objects.create(
                attempt=attempt,
                question_id=question.id,
                answer_type=question.question_type if question.question_type in {"choice", "text"} else AnswerError.AnswerType.OTHER,
                error_type="wrong_answer",
                user_answer=user_answer,
                correct_answer=correct_answer,
            )

    max_score = test.max_score if test.max_score > 0 else dynamic_max
    passing_score = test.passing_score if test.passing_score > 0 else max_score
    passed = score >= passing_score
    attempt.status = TestAttempt.Status.COMPLETED if passed else TestAttempt.Status.FAILED
    attempt.score = score
    attempt.max_score = max_score
    attempt.passed = passed
    attempt.finished_at = now
    attempt.save(update_fields=["status", "score", "max_score", "passed", "finished_at", "updated_at"])

    if passed:
        progress, _ = LearningProgress.objects.get_or_create(trainee=profile, block_id=module_id)
        progress.status = LearningProgress.Status.COMPLETED
        if not progress.started_at:
            progress.started_at = now
        progress.completed_at = now
        progress.last_activity_at = now
        progress.save(update_fields=["status", "started_at", "completed_at", "last_activity_at", "updated_at"])

    attempts_left = max(test.max_attempts - (attempts_total + 1), 0)
    return JsonResponse({"detail": "ok", "score": score, "passed": passed, "attempts_left": attempts_left})


@require_GET
@login_required
def module_video_file(request: HttpRequest, module_id: int) -> FileResponse:
    profile = _ensure_profile(request.user)
    module = _get_accessible_module_or_404(request.user, profile, module_id)
    if not module.private_video:
        raise Http404("Видео не найдено")

    content_type = mimetypes.guess_type(module.private_video.name)[0] or "application/octet-stream"
    filename = module.private_video.name.rsplit("/", 1)[-1]
    return _stream_file_range(module.private_video, request, content_type, filename)


@require_GET
@login_required
def module_material_file(request: HttpRequest, material_id: int) -> FileResponse:
    profile = _ensure_profile(request.user)
    material = get_object_or_404(
        ModuleMaterial.objects.select_related("module", "module__course"),
        pk=material_id,
        is_active=True,
        module__is_active=True,
        module__course__is_active=True,
    )
    if not _user_can_access_course(request.user, profile, material.module.course):
        raise Http404("Материал не найден")

    content_type = mimetypes.guess_type(material.file.name)[0] or "application/pdf"
    response = FileResponse(material.file.open("rb"), content_type=content_type)
    response["Content-Disposition"] = f'inline; filename="{material.file.name.rsplit("/", 1)[-1]}"'
    response["Cache-Control"] = "private, no-store"
    return response


def staff_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            return redirect("login")
        return view_func(request, *args, **kwargs)

    return _wrapped


@staff_required
def hr_content_dashboard(request: HttpRequest) -> HttpResponse:
    courses = (
        Course.objects.prefetch_related(
            "departments",
            Prefetch(
                "modules",
                queryset=Module.objects.select_related("test").prefetch_related("materials", "test__questions"),
            ),
        )
        .order_by("id")
    )
    return render(request, "education_platform/hr_dashboard.html", {"courses": courses})


@staff_required
def hr_trainee_dashboard(request: HttpRequest) -> HttpResponse:
    profiles = (
        TraineeProfile.objects.select_related("user")
        .prefetch_related("departments")
        .annotate(
            progress_count=Count("learning_progress", distinct=True),
            completed_count=Count(
                "learning_progress",
                filter=Q(learning_progress__status=LearningProgress.Status.COMPLETED),
                distinct=True,
            ),
            attempts_count=Count("test_attempts", distinct=True),
            passed_attempts_count=Count(
                "test_attempts",
                filter=Q(test_attempts__passed=True),
                distinct=True,
            ),
        )
        .order_by("user__username")
    )
    return render(
        request,
        "education_platform/hr_trainees.html",
        {"profiles": profiles, "title": "Стажеры LMS"},
    )


@staff_required
def hr_trainee_create(request: HttpRequest) -> HttpResponse:
    generated_password = _generate_password()
    initial = {"password": generated_password, "is_active": True}
    form = TraineeAccountForm(request.POST or None, initial=initial)
    credentials = None

    if request.method == "POST" and form.is_valid():
        User = get_user_model()
        password = form.cleaned_data["password"] or _generate_password()
        user = User.objects.create_user(
            username=form.cleaned_data["username"],
            password=password,
            email=form.cleaned_data["email"],
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data["last_name"],
            is_active=form.cleaned_data["is_active"],
        )
        profile = _ensure_profile(user)
        profile.departments.set(form.cleaned_data["departments"])
        profile.is_active = form.cleaned_data["is_active"]
        profile.save(update_fields=["is_active", "updated_at"])
        _sync_legacy_department(profile)
        credentials = {"username": user.username, "password": password}
        messages.success(request, f"Аккаунт создан. Логин: {user.username} Пароль: {password}")
        form = TraineeAccountForm(initial={"password": _generate_password(), "is_active": True})

    return render(
        request,
        "education_platform/hr_trainee_create.html",
        {"form": form, "credentials": credentials, "title": "Новый стажер"},
    )


@staff_required
def hr_trainee_detail(request: HttpRequest, profile_id: int) -> HttpResponse:
    profile = get_object_or_404(
        TraineeProfile.objects.select_related("user").prefetch_related("departments"),
        pk=profile_id,
    )
    form = TraineeDepartmentsForm(
        request.POST or None,
        initial={"departments": profile.departments.all(), "is_active": profile.is_active},
    )
    if request.method == "POST" and form.is_valid():
        profile.departments.set(form.cleaned_data["departments"])
        profile.is_active = form.cleaned_data["is_active"]
        profile.user.is_active = form.cleaned_data["is_active"]
        profile.save(update_fields=["is_active", "updated_at"])
        profile.user.save(update_fields=["is_active"])
        _sync_legacy_department(profile)
        messages.success(request, "Доступы стажера обновлены.")
        return redirect("education_hr_trainee_detail", profile_id=profile.id)

    accessible_courses = (
        Course.objects.filter(is_active=True, departments__in=profile.departments.all())
        .distinct()
        .prefetch_related(Prefetch("modules", queryset=Module.objects.select_related("test").order_by("order", "id")))
        .order_by("id")
    )
    module_ids = []
    test_ids = []
    for course in accessible_courses:
        for module in course.modules.all():
            module_ids.append(module.id)
            if hasattr(module, "test"):
                test_ids.append(module.test.id)

    progress_map = {
        row.block_id: row
        for row in LearningProgress.objects.filter(trainee=profile, block_id__in=module_ids)
    }
    attempts_by_test = {}
    for attempt in TestAttempt.objects.filter(trainee=profile, test_id__in=test_ids).order_by("-created_at"):
        attempts_by_test.setdefault(attempt.test_id, []).append(attempt)

    course_rows = []
    for course in accessible_courses:
        module_rows = []
        for module in course.modules.all():
            test = getattr(module, "test", None)
            attempts = attempts_by_test.get(test.id, []) if test else []
            module_rows.append(
                {
                    "module": module,
                    "progress": progress_map.get(module.id),
                    "test": test,
                    "attempts": attempts,
                    "latest_attempt": attempts[0] if attempts else None,
                }
            )
        total = len(module_rows)
        completed = sum(
            1
            for row in module_rows
            if row["progress"] and row["progress"].status == LearningProgress.Status.COMPLETED
        )
        course_rows.append({"course": course, "modules": module_rows, "total": total, "completed": completed})

    return render(
        request,
        "education_platform/hr_trainee_detail.html",
        {
            "profile": profile,
            "form": form,
            "course_rows": course_rows,
            "title": f"Стажер: {profile.user.username}",
        },
    )


@staff_required
def hr_course_create(request: HttpRequest) -> HttpResponse:
    form = CourseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Курс создан.")
        return redirect("education_hr_dashboard")
    return render(request, "education_platform/hr_form.html", {"form": form, "title": "Новый курс"})


@staff_required
def hr_course_edit(request: HttpRequest, course_id: int) -> HttpResponse:
    course = get_object_or_404(Course, pk=course_id)
    form = CourseForm(request.POST or None, instance=course)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Курс обновлен.")
        return redirect("education_hr_dashboard")
    return render(request, "education_platform/hr_form.html", {"form": form, "title": f"Редактировать курс: {course.name}"})


@staff_required
def hr_module_create(request: HttpRequest) -> HttpResponse:
    initial = {}
    if request.GET.get("course"):
        initial["course"] = request.GET.get("course")
    form = ModuleForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        module = form.save()
        ModuleTest.objects.get_or_create(
            module=module,
            defaults={
                "name": "Проверка модуля",
                "description": "",
                "max_score": 0,
                "passing_score": 0,
                "max_attempts": 3,
                "is_active": True,
            },
        )
        messages.success(request, "Модуль создан.")
        return redirect("education_hr_dashboard")
    return render(request, "education_platform/hr_form.html", {"form": form, "title": "Новый модуль"})


@staff_required
def hr_module_edit(request: HttpRequest, module_id: int) -> HttpResponse:
    module = get_object_or_404(Module, pk=module_id)
    form = ModuleForm(request.POST or None, request.FILES or None, instance=module)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Модуль обновлен.")
        return redirect("education_hr_dashboard")
    return render(request, "education_platform/hr_form.html", {"form": form, "title": f"Редактировать модуль: {module.name}"})


@staff_required
def hr_material_create(request: HttpRequest, module_id: int) -> HttpResponse:
    module = get_object_or_404(Module, pk=module_id)
    form = ModuleMaterialForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        material = form.save(commit=False)
        material.module = module
        material.save()
        messages.success(request, "Материал добавлен.")
        return redirect("education_hr_dashboard")
    return render(request, "education_platform/hr_form.html", {"form": form, "title": f"Новый материал: {module.name}"})


@staff_required
def hr_material_edit(request: HttpRequest, material_id: int) -> HttpResponse:
    material = get_object_or_404(ModuleMaterial, pk=material_id)
    form = ModuleMaterialForm(request.POST or None, request.FILES or None, instance=material)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Материал обновлен.")
        return redirect("education_hr_dashboard")
    return render(request, "education_platform/hr_form.html", {"form": form, "title": f"Редактировать материал: {material.title}"})


@staff_required
@require_POST
def hr_material_delete(request: HttpRequest, material_id: int) -> HttpResponse:
    material = get_object_or_404(ModuleMaterial, pk=material_id)
    material.delete()
    messages.success(request, "Материал удален.")
    return redirect("education_hr_dashboard")


@staff_required
def hr_test_edit(request: HttpRequest, module_id: int) -> HttpResponse:
    module = get_object_or_404(Module, pk=module_id)
    test, _ = ModuleTest.objects.get_or_create(
        module=module,
        defaults={"name": f"Тест: {module.name}", "max_attempts": 3},
    )
    form = ModuleTestForm(request.POST or None, instance=test)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Тест обновлен.")
        return redirect("education_hr_dashboard")
    return render(
        request,
        "education_platform/hr_test_edit.html",
        {
            "form": form,
            "test": test,
            "questions": test.questions.prefetch_related("options").all(),
            "title": f"Редактировать тест: {module.name}",
        },
    )


@staff_required
def hr_question_create(request: HttpRequest, test_id: int) -> HttpResponse:
    test = get_object_or_404(ModuleTest, pk=test_id)
    form = TestQuestionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        question = form.save(commit=False)
        question.test = test
        question.save()
        messages.success(request, "Вопрос добавлен.")
        return redirect("education_hr_test_edit", module_id=test.module_id)
    return render(request, "education_platform/hr_form.html", {"form": form, "title": f"Новый вопрос для {test.name}"})


@staff_required
def hr_question_edit(request: HttpRequest, question_id: int) -> HttpResponse:
    question = get_object_or_404(TestQuestion, pk=question_id)
    form = TestQuestionForm(request.POST or None, instance=question)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Вопрос обновлен.")
        return redirect("education_hr_test_edit", module_id=question.test.module_id)
    return render(request, "education_platform/hr_form.html", {"form": form, "title": "Редактировать вопрос"})


@staff_required
@require_POST
def hr_question_delete(request: HttpRequest, question_id: int) -> HttpResponse:
    question = get_object_or_404(TestQuestion, pk=question_id)
    module_id = question.test.module_id
    question.delete()
    messages.success(request, "Вопрос удален.")
    return redirect("education_hr_test_edit", module_id=module_id)


@staff_required
def hr_option_create(request: HttpRequest, question_id: int) -> HttpResponse:
    question = get_object_or_404(TestQuestion, pk=question_id)
    form = QuestionOptionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        option = form.save(commit=False)
        option.question = question
        option.save()
        messages.success(request, "Вариант ответа добавлен.")
        return redirect("education_hr_test_edit", module_id=question.test.module_id)
    return render(request, "education_platform/hr_form.html", {"form": form, "title": "Новый вариант ответа"})


@staff_required
def hr_option_edit(request: HttpRequest, option_id: int) -> HttpResponse:
    option = get_object_or_404(QuestionOption, pk=option_id)
    form = QuestionOptionForm(request.POST or None, instance=option)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Вариант ответа обновлен.")
        return redirect("education_hr_test_edit", module_id=option.question.test.module_id)
    return render(request, "education_platform/hr_form.html", {"form": form, "title": "Редактировать вариант ответа"})


@staff_required
@require_POST
def hr_option_delete(request: HttpRequest, option_id: int) -> HttpResponse:
    option = get_object_or_404(QuestionOption, pk=option_id)
    module_id = option.question.test.module_id
    option.delete()
    messages.success(request, "Вариант ответа удален.")
    return redirect("education_hr_test_edit", module_id=module_id)
