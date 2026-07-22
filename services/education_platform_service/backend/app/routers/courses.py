from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from ..auth import get_current_user
from ..db import get_db
from ..models import (
    AnswerError,
    Course,
    Department,
    LearningProgress,
    LearningProgressStatus,
    Module,
    ModuleTest,
    TestAttempt,
    TestAttemptStatus,
    TestQuestion,
    User,
)
from ..schemas import (
    CourseOut,
    ModuleMaterialOut,
    ModuleOut,
    ProgressUpdateRequest,
    QuestionOptionOut,
    SubmitTestRequest,
    TestOut,
    TestQuestionOut,
)
from .auth import _department_codes

router = APIRouter(tags=["courses"])


def _user_can_access_course(user: User, course: Course) -> bool:
    if user.is_staff:
        return True
    codes = _department_codes(user)
    if not codes:
        return False
    return any(d.code in codes and d.is_active for d in course.departments)


def _get_accessible_module_or_404(user: User, module_id: int, db: Session) -> Module:
    module = (
        db.query(Module)
        .options(joinedload(Module.course).joinedload(Course.departments))
        .filter(Module.id == module_id, Module.is_active.is_(True))
        .first()
    )
    if not module or not module.course.is_active:
        raise HTTPException(status_code=404, detail="Модуль не найден")
    if not _user_can_access_course(user, module.course):
        raise HTTPException(status_code=404, detail="Модуль не найден")
    return module


@router.get("/courses")
def get_courses(
    department: str = Query(default=""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    department_codes = _department_codes(current_user)
    if current_user.is_staff and department and db.query(Department).filter(Department.code == department, Department.is_active.is_(True)).first():
        department_codes = [department]
    if not department_codes:
        raise HTTPException(status_code=400, detail="Отдел не указан")

    courses = (
        db.query(Course)
        .join(Course.departments)
        .filter(Course.is_active.is_(True), Department.code.in_(department_codes), Department.is_active.is_(True))
        .distinct()
        .all()
    )

    module_ids = [m.id for c in courses for m in c.modules if m.is_active]
    progress_rows = (
        db.query(LearningProgress.block_id, LearningProgress.status)
        .filter(LearningProgress.user_id == current_user.id, LearningProgress.block_id.in_(module_ids))
        .all()
    )
    progress_map = dict(progress_rows)

    result = []
    for course in courses:
        active_modules = [m for m in course.modules if m.is_active]
        completed = sum(1 for m in active_modules if progress_map.get(m.id) == LearningProgressStatus.COMPLETED.value)
        result.append(
            CourseOut(
                id=course.id,
                name=course.name,
                description=course.description,
                image_url=course.image_url,
                photo_url=course.photo_url,
                modules_count=len(active_modules),
                completed_modules=completed,
            )
        )
    return {"detail": "ok", "courses": result}


@router.get("/modules")
def get_modules(
    course: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    course_obj = db.query(Course).options(joinedload(Course.departments)).filter(Course.id == course, Course.is_active.is_(True)).first()
    if not course_obj:
        raise HTTPException(status_code=404, detail="Курс не найден")
    if not _user_can_access_course(current_user, course_obj):
        raise HTTPException(status_code=404, detail="Курс не найден")

    modules = [m for m in course_obj.modules if m.is_active]
    module_ids = [m.id for m in modules]
    progress_rows = (
        db.query(LearningProgress.block_id, LearningProgress.status)
        .filter(LearningProgress.user_id == current_user.id, LearningProgress.block_id.in_(module_ids))
        .all()
    )
    progress_map = dict(progress_rows)

    result = []
    for module in modules:
        materials = [
            ModuleMaterialOut(
                id=material.id,
                title=material.title,
                material_type=material.material_type,
                url=f"/materials/{material.id}/file",
                order=material.order,
            )
            for material in module.materials
            if material.is_active
        ]
        result.append(
            ModuleOut(
                id=module.id,
                name=module.name,
                description=module.description,
                video_url=f"/modules/{module.id}/video" if module.private_video else module.video_url,
                video_is_private=bool(module.private_video),
                materials=materials,
                order=module.order,
                status=progress_map.get(module.id, LearningProgressStatus.NOT_STARTED.value),
            )
        )
    return {"detail": "ok", "modules": result}


def _serialize_test(test: ModuleTest) -> dict:
    questions = [
        TestQuestionOut(
            id=q.id,
            text=q.text,
            question_type=q.question_type,
            options=[QuestionOptionOut(id=o.id, text=o.text) for o in q.options],
            score=q.score,
            order=q.order,
        )
        for q in test.questions
    ]
    return {
        "id": test.id,
        "name": test.name,
        "description": test.description,
        "max_score": test.max_score,
        "passing_score": test.passing_score,
        "max_attempts": test.max_attempts,
        "questions": questions,
    }


@router.get("/tests")
def get_test(
    module: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    accessible_module = _get_accessible_module_or_404(current_user, module, db)
    test = (
        db.query(ModuleTest)
        .options(joinedload(ModuleTest.questions).joinedload(TestQuestion.options))
        .filter(ModuleTest.module_id == accessible_module.id, ModuleTest.is_active.is_(True))
        .first()
    )
    if not test:
        raise HTTPException(status_code=404, detail="Тест не найден")

    attempts_used = (
        db.query(TestAttempt)
        .filter(
            TestAttempt.user_id == current_user.id,
            TestAttempt.test_id == test.id,
            TestAttempt.status.in_([TestAttemptStatus.COMPLETED.value, TestAttemptStatus.FAILED.value]),
        )
        .count()
    )
    attempts_left = max(test.max_attempts - attempts_used, 0)
    payload = _serialize_test(test)
    payload["attempts_left"] = attempts_left
    return {"detail": "ok", "test": TestOut(**payload)}


@router.post("/progress")
def update_module_progress(
    payload: ProgressUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    allowed_status = {s.value for s in LearningProgressStatus}
    if payload.status not in allowed_status:
        raise HTTPException(status_code=400, detail="Некорректный статус")

    module = _get_accessible_module_or_404(current_user, payload.module_id, db)

    if payload.status == LearningProgressStatus.COMPLETED.value:
        test = db.query(ModuleTest).filter(ModuleTest.module_id == module.id, ModuleTest.is_active.is_(True)).first()
        if test and test.questions:
            passed = (
                db.query(TestAttempt)
                .filter(
                    TestAttempt.user_id == current_user.id,
                    TestAttempt.test_id == test.id,
                    TestAttempt.status == TestAttemptStatus.COMPLETED.value,
                    TestAttempt.passed.is_(True),
                )
                .first()
            )
            if not passed:
                raise HTTPException(status_code=400, detail="Сначала нужно пройти тест")

    now = datetime.now(timezone.utc)
    progress = (
        db.query(LearningProgress)
        .filter(LearningProgress.user_id == current_user.id, LearningProgress.block_id == payload.module_id)
        .first()
    )
    if progress is None:
        progress = LearningProgress(
            user_id=current_user.id,
            block_id=payload.module_id,
            status=payload.status,
            started_at=now if payload.status in {LearningProgressStatus.IN_PROGRESS.value, LearningProgressStatus.COMPLETED.value} else None,
            completed_at=now if payload.status == LearningProgressStatus.COMPLETED.value else None,
            last_activity_at=now,
        )
        db.add(progress)
    elif progress.status != payload.status:
        progress.status = payload.status
        if payload.status == LearningProgressStatus.IN_PROGRESS.value and not progress.started_at:
            progress.started_at = now
        if payload.status == LearningProgressStatus.COMPLETED.value:
            progress.completed_at = now
        progress.last_activity_at = now

    db.commit()
    return {"detail": "ok", "module_id": payload.module_id, "status": progress.status}


def _evaluate_question(question: TestQuestion, answer_payload: dict) -> tuple[bool, dict, dict]:
    correct_options = [o for o in question.options if o.is_correct]
    correct_ids = {o.id for o in correct_options}

    if question.question_type == "choice":
        user_id = answer_payload.get("id")
        is_correct = user_id in correct_ids and len(correct_ids) == 1
        return is_correct, {"id": user_id}, {"id": next(iter(correct_ids), None)}

    if question.question_type == "multi_choice":
        user_ids = set(answer_payload.get("ids") or [])
        is_correct = user_ids == correct_ids
        return is_correct, {"ids": sorted(user_ids)}, {"ids": sorted(correct_ids)}

    user_text = str(answer_payload.get("text") or "").strip().lower()
    expected_texts = [o.text.strip().lower() for o in correct_options if o.text.strip()]
    if expected_texts:
        is_correct = user_text in expected_texts
        return is_correct, {"text": user_text}, {"text": expected_texts}
    is_correct = bool(user_text)
    return is_correct, {"text": user_text}, {"text": "any non-empty text"}


@router.post("/tests/submit")
def submit_test(
    payload: SubmitTestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    module = _get_accessible_module_or_404(current_user, payload.module_id, db)
    test = (
        db.query(ModuleTest)
        .options(joinedload(ModuleTest.questions).joinedload(TestQuestion.options))
        .filter(ModuleTest.module_id == module.id, ModuleTest.is_active.is_(True))
        .first()
    )
    if not test:
        raise HTTPException(status_code=404, detail="Тест не найден")
    if not test.questions:
        raise HTTPException(status_code=400, detail="В тесте нет вопросов")

    attempts_total = db.query(TestAttempt).filter(TestAttempt.user_id == current_user.id, TestAttempt.test_id == test.id).count()
    if attempts_total >= test.max_attempts:
        return {"detail": "Попытки закончились", "attempts_left": 0, "passed": False, "score": 0}

    score = 0.0
    dynamic_max = 0.0
    now = datetime.now(timezone.utc)

    attempt = TestAttempt(
        user_id=current_user.id,
        test_id=test.id,
        status=TestAttemptStatus.IN_PROGRESS.value,
        attempt_number=attempts_total + 1,
        meta={"answers": payload.answers, "module_id": payload.module_id},
    )
    db.add(attempt)
    db.flush()

    for question in test.questions:
        dynamic_max += question.score
        answer_payload = payload.answers.get(str(question.id)) or payload.answers.get(question.id) or {}
        is_correct, user_answer, correct_answer = _evaluate_question(question, answer_payload)
        if is_correct:
            score += question.score
        else:
            db.add(
                AnswerError(
                    attempt_id=attempt.id,
                    question_id=question.id,
                    answer_type=question.question_type if question.question_type in {"choice", "text"} else "other",
                    error_type="wrong_answer",
                    user_answer=user_answer,
                    correct_answer=correct_answer,
                )
            )

    max_score = test.max_score if test.max_score > 0 else dynamic_max
    passing_score = test.passing_score if test.passing_score > 0 else max_score
    passed = score >= passing_score
    attempt.status = TestAttemptStatus.COMPLETED.value if passed else TestAttemptStatus.FAILED.value
    attempt.score = score
    attempt.max_score = max_score
    attempt.passed = passed
    attempt.finished_at = now

    if passed:
        progress = (
            db.query(LearningProgress)
            .filter(LearningProgress.user_id == current_user.id, LearningProgress.block_id == payload.module_id)
            .first()
        )
        if progress is None:
            progress = LearningProgress(user_id=current_user.id, block_id=payload.module_id)
            db.add(progress)
        progress.status = LearningProgressStatus.COMPLETED.value
        if not progress.started_at:
            progress.started_at = now
        progress.completed_at = now
        progress.last_activity_at = now

    db.commit()
    attempts_left = max(test.max_attempts - (attempts_total + 1), 0)
    return {"detail": "ok", "score": score, "passed": passed, "attempts_left": attempts_left}
