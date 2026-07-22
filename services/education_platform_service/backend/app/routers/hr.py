from __future__ import annotations

import secrets
import string

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from ..auth import hash_password, require_staff
from ..db import get_db
from ..models import (
    Course,
    Department,
    LearningProgress,
    LearningProgressStatus,
    Module,
    ModuleMaterial,
    ModuleTest,
    QuestionOption,
    TestAttempt,
    TestQuestion,
    User,
)
from ..schemas import (
    DepartmentOut,
    HrCourseIn,
    HrCourseOut,
    HrCourseProgressRowOut,
    HrCourseTreeOut,
    HrMaterialIn,
    HrMaterialOut,
    HrModuleIn,
    HrModuleOut,
    HrModuleProgressRowOut,
    HrOptionIn,
    HrQuestionIn,
    HrQuestionOptionOut,
    HrQuestionOut,
    HrTestIn,
    HrTestOut,
    HrTestSummaryOut,
    HrTraineeCreateIn,
    HrTraineeCreateOut,
    HrTraineeDetailOut,
    HrTraineeListItemOut,
    HrTraineeUpdateIn,
)
from ..services.file_streaming import save_upload

router = APIRouter(prefix="/hr", tags=["hr"], dependencies=[Depends(require_staff)])


def _generate_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _departments_by_codes(codes: list[str], db: Session) -> list[Department]:
    if not codes:
        return []
    return db.query(Department).filter(Department.code.in_(codes)).all()


def _course_out(course: Course) -> HrCourseOut:
    return HrCourseOut(
        id=course.id,
        name=course.name,
        description=course.description,
        image_url=course.image_url,
        photo_url=course.photo_url,
        department_codes=[d.code for d in course.departments],
        is_active=course.is_active,
    )


# ---- courses ----


@router.get("/departments")
def list_departments(db: Session = Depends(get_db)):
    departments = db.query(Department).filter(Department.is_active.is_(True)).order_by(Department.name).all()
    return [DepartmentOut(code=d.code, name=d.name) for d in departments]


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    courses = (
        db.query(Course)
        .options(
            joinedload(Course.departments),
            joinedload(Course.modules).joinedload(Module.materials),
            joinedload(Course.modules).joinedload(Module.test).joinedload(ModuleTest.questions),
        )
        .order_by(Course.id)
        .all()
    )
    result = []
    for course in courses:
        modules_out = []
        for module in sorted(course.modules, key=lambda m: (m.order, m.id)):
            test_out = (
                HrTestSummaryOut(id=module.test.id, name=module.test.name, is_active=module.test.is_active, questions_count=len(module.test.questions))
                if module.test
                else None
            )
            modules_out.append(
                HrModuleOut(
                    id=module.id,
                    course_id=module.course_id,
                    name=module.name,
                    description=module.description,
                    video_url=module.video_url,
                    private_video=module.private_video,
                    order=module.order,
                    is_active=module.is_active,
                    materials=[
                        HrMaterialOut(id=m.id, title=m.title, material_type=m.material_type, file=m.file, order=m.order, is_active=m.is_active)
                        for m in sorted(module.materials, key=lambda m: (m.order, m.id))
                    ],
                    test=test_out,
                )
            )
        result.append(HrCourseTreeOut(**_course_out(course).model_dump(), modules=modules_out))
    return result


@router.post("/courses", response_model=HrCourseOut, status_code=201)
def create_course(payload: HrCourseIn, db: Session = Depends(get_db)):
    course = Course(
        name=payload.name,
        description=payload.description,
        image_url=payload.image_url,
        photo_url=payload.photo_url,
        is_active=payload.is_active,
    )
    course.departments = _departments_by_codes(payload.department_codes, db)
    db.add(course)
    db.commit()
    db.refresh(course)
    return _course_out(course)


@router.put("/courses/{course_id}", response_model=HrCourseOut)
def update_course(course_id: int, payload: HrCourseIn, db: Session = Depends(get_db)):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")
    course.name = payload.name
    course.description = payload.description
    course.image_url = payload.image_url
    course.photo_url = payload.photo_url
    course.is_active = payload.is_active
    course.departments = _departments_by_codes(payload.department_codes, db)
    db.commit()
    db.refresh(course)
    return _course_out(course)


# ---- modules ----


def _module_out(module: Module) -> HrModuleOut:
    test_out = (
        HrTestSummaryOut(id=module.test.id, name=module.test.name, is_active=module.test.is_active, questions_count=len(module.test.questions))
        if module.test
        else None
    )
    return HrModuleOut(
        id=module.id,
        course_id=module.course_id,
        name=module.name,
        description=module.description,
        video_url=module.video_url,
        private_video=module.private_video,
        order=module.order,
        is_active=module.is_active,
        materials=[
            HrMaterialOut(id=m.id, title=m.title, material_type=m.material_type, file=m.file, order=m.order, is_active=m.is_active)
            for m in module.materials
        ],
        test=test_out,
    )


@router.post("/modules", response_model=HrModuleOut, status_code=201)
def create_module(
    course_id: int = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    video_url: str = Form(""),
    order: int = Form(1),
    is_active: bool = Form(True),
    private_video: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    if not db.get(Course, course_id):
        raise HTTPException(status_code=404, detail="Курс не найден")
    module = Module(
        course_id=course_id,
        name=name,
        description=description,
        video_url=video_url,
        order=order,
        is_active=is_active,
        private_video=save_upload(private_video, "education/videos") if private_video and private_video.filename else "",
    )
    db.add(module)
    db.flush()
    db.add(
        ModuleTest(
            module_id=module.id,
            name="Проверка модуля",
            description="",
            max_score=0,
            passing_score=0,
            max_attempts=3,
            is_active=True,
        )
    )
    db.commit()
    db.refresh(module)
    return _module_out(module)


@router.put("/modules/{module_id}", response_model=HrModuleOut)
def update_module(
    module_id: int,
    course_id: int = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    video_url: str = Form(""),
    order: int = Form(1),
    is_active: bool = Form(True),
    private_video: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    module = db.get(Module, module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Модуль не найден")
    module.course_id = course_id
    module.name = name
    module.description = description
    module.video_url = video_url
    module.order = order
    module.is_active = is_active
    if private_video and private_video.filename:
        module.private_video = save_upload(private_video, "education/videos")
    db.commit()
    db.refresh(module)
    return _module_out(module)


# ---- materials ----


@router.post("/modules/{module_id}/materials", response_model=HrMaterialOut, status_code=201)
def create_material(
    module_id: int,
    title: str = Form(...),
    material_type: str = Form("pdf"),
    order: int = Form(1),
    is_active: bool = Form(True),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not db.get(Module, module_id):
        raise HTTPException(status_code=404, detail="Модуль не найден")
    material = ModuleMaterial(
        module_id=module_id,
        title=title,
        material_type=material_type,
        order=order,
        is_active=is_active,
        file=save_upload(file, "education/materials"),
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return HrMaterialOut(id=material.id, title=material.title, material_type=material.material_type, file=material.file, order=material.order, is_active=material.is_active)


@router.put("/materials/{material_id}", response_model=HrMaterialOut)
def update_material(
    material_id: int,
    title: str = Form(...),
    material_type: str = Form("pdf"),
    order: int = Form(1),
    is_active: bool = Form(True),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    material = db.get(ModuleMaterial, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Материал не найден")
    material.title = title
    material.material_type = material_type
    material.order = order
    material.is_active = is_active
    if file and file.filename:
        material.file = save_upload(file, "education/materials")
    db.commit()
    db.refresh(material)
    return HrMaterialOut(id=material.id, title=material.title, material_type=material.material_type, file=material.file, order=material.order, is_active=material.is_active)


@router.delete("/materials/{material_id}")
def delete_material(material_id: int, db: Session = Depends(get_db)):
    material = db.get(ModuleMaterial, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Материал не найден")
    db.delete(material)
    db.commit()
    return {"detail": "ok"}


# ---- tests / questions / options ----


def _test_out(test: ModuleTest) -> HrTestOut:
    return HrTestOut(
        id=test.id,
        module_id=test.module_id,
        name=test.name,
        description=test.description,
        max_score=test.max_score,
        passing_score=test.passing_score,
        max_attempts=test.max_attempts,
        is_active=test.is_active,
        questions=[
            HrQuestionOut(
                id=q.id,
                text=q.text,
                question_type=q.question_type,
                score=q.score,
                order=q.order,
                options=[HrQuestionOptionOut(id=o.id, text=o.text, is_correct=o.is_correct, order=o.order) for o in sorted(q.options, key=lambda o: (o.order, o.id))],
            )
            for q in sorted(test.questions, key=lambda q: (q.order, q.id))
        ],
    )


@router.get("/tests/{module_id}", response_model=HrTestOut)
def get_or_create_test(module_id: int, db: Session = Depends(get_db)):
    module = db.get(Module, module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Модуль не найден")
    test = db.query(ModuleTest).options(joinedload(ModuleTest.questions).joinedload(TestQuestion.options)).filter(ModuleTest.module_id == module_id).first()
    if not test:
        test = ModuleTest(module_id=module_id, name=f"Тест: {module.name}", max_attempts=3)
        db.add(test)
        db.commit()
        db.refresh(test)
    return _test_out(test)


@router.put("/tests/{test_id}", response_model=HrTestOut)
def update_test(test_id: int, payload: HrTestIn, db: Session = Depends(get_db)):
    test = db.query(ModuleTest).options(joinedload(ModuleTest.questions).joinedload(TestQuestion.options)).filter(ModuleTest.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Тест не найден")
    test.name = payload.name
    test.description = payload.description
    test.max_score = payload.max_score
    test.passing_score = payload.passing_score
    test.max_attempts = payload.max_attempts
    test.is_active = payload.is_active
    db.commit()
    db.refresh(test)
    return _test_out(test)


@router.post("/tests/{test_id}/questions", response_model=HrQuestionOut, status_code=201)
def create_question(test_id: int, payload: HrQuestionIn, db: Session = Depends(get_db)):
    if not db.get(ModuleTest, test_id):
        raise HTTPException(status_code=404, detail="Тест не найден")
    question = TestQuestion(test_id=test_id, text=payload.text, question_type=payload.question_type, score=payload.score, order=payload.order)
    db.add(question)
    db.commit()
    db.refresh(question)
    return HrQuestionOut(id=question.id, text=question.text, question_type=question.question_type, score=question.score, order=question.order, options=[])


@router.put("/questions/{question_id}", response_model=HrQuestionOut)
def update_question(question_id: int, payload: HrQuestionIn, db: Session = Depends(get_db)):
    question = db.query(TestQuestion).options(joinedload(TestQuestion.options)).filter(TestQuestion.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Вопрос не найден")
    question.text = payload.text
    question.question_type = payload.question_type
    question.score = payload.score
    question.order = payload.order
    db.commit()
    db.refresh(question)
    return HrQuestionOut(
        id=question.id,
        text=question.text,
        question_type=question.question_type,
        score=question.score,
        order=question.order,
        options=[HrQuestionOptionOut(id=o.id, text=o.text, is_correct=o.is_correct, order=o.order) for o in question.options],
    )


@router.delete("/questions/{question_id}")
def delete_question(question_id: int, db: Session = Depends(get_db)):
    question = db.get(TestQuestion, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Вопрос не найден")
    db.delete(question)
    db.commit()
    return {"detail": "ok"}


@router.post("/questions/{question_id}/options", response_model=HrQuestionOptionOut, status_code=201)
def create_option(question_id: int, payload: HrOptionIn, db: Session = Depends(get_db)):
    if not db.get(TestQuestion, question_id):
        raise HTTPException(status_code=404, detail="Вопрос не найден")
    option = QuestionOption(question_id=question_id, text=payload.text, is_correct=payload.is_correct, order=payload.order)
    db.add(option)
    db.commit()
    db.refresh(option)
    return HrQuestionOptionOut(id=option.id, text=option.text, is_correct=option.is_correct, order=option.order)


@router.put("/options/{option_id}", response_model=HrQuestionOptionOut)
def update_option(option_id: int, payload: HrOptionIn, db: Session = Depends(get_db)):
    option = db.get(QuestionOption, option_id)
    if not option:
        raise HTTPException(status_code=404, detail="Вариант ответа не найден")
    option.text = payload.text
    option.is_correct = payload.is_correct
    option.order = payload.order
    db.commit()
    db.refresh(option)
    return HrQuestionOptionOut(id=option.id, text=option.text, is_correct=option.is_correct, order=option.order)


@router.delete("/options/{option_id}")
def delete_option(option_id: int, db: Session = Depends(get_db)):
    option = db.get(QuestionOption, option_id)
    if not option:
        raise HTTPException(status_code=404, detail="Вариант ответа не найден")
    db.delete(option)
    db.commit()
    return {"detail": "ok"}


# ---- trainees ----


def _trainee_list_item(user: User, db: Session) -> HrTraineeListItemOut:
    progress_count = db.query(LearningProgress).filter(LearningProgress.user_id == user.id).count()
    completed_count = db.query(LearningProgress).filter(LearningProgress.user_id == user.id, LearningProgress.status == LearningProgressStatus.COMPLETED.value).count()
    attempts_count = db.query(TestAttempt).filter(TestAttempt.user_id == user.id).count()
    passed_attempts_count = db.query(TestAttempt).filter(TestAttempt.user_id == user.id, TestAttempt.passed.is_(True)).count()
    return HrTraineeListItemOut(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        is_active=user.is_active,
        departments=[DepartmentOut(code=d.code, name=d.name) for d in user.departments],
        progress_count=progress_count,
        completed_count=completed_count,
        attempts_count=attempts_count,
        passed_attempts_count=passed_attempts_count,
    )


@router.get("/trainees", response_model=list[HrTraineeListItemOut])
def list_trainees(db: Session = Depends(get_db)):
    users = db.query(User).options(joinedload(User.departments)).order_by(User.username).all()
    return [_trainee_list_item(u, db) for u in users]


@router.post("/trainees", response_model=HrTraineeCreateOut, status_code=201)
def create_trainee(payload: HrTraineeCreateIn, db: Session = Depends(get_db)):
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="username обязателен")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="Пользователь с таким логином уже существует")

    password = payload.password or _generate_password()
    user = User(
        username=username,
        hashed_password=hash_password(password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        is_active=payload.is_active,
    )
    user.departments = _departments_by_codes(payload.department_codes, db)
    db.add(user)
    db.commit()
    db.refresh(user)
    return HrTraineeCreateOut(username=user.username, password=password, user=_trainee_list_item(user, db))


def _build_course_rows(user: User, db: Session) -> list[HrCourseProgressRowOut]:
    department_ids = [d.id for d in user.departments]
    if not department_ids:
        return []
    courses = (
        db.query(Course)
        .join(Course.departments)
        .filter(Course.is_active.is_(True), Department.id.in_(department_ids))
        .distinct()
        .options(joinedload(Course.modules).joinedload(Module.test))
        .order_by(Course.id)
        .all()
    )
    rows = []
    for course in courses:
        modules = sorted(course.modules, key=lambda m: (m.order, m.id))
        module_ids = [m.id for m in modules]
        progress_map = {
            p.block_id: p
            for p in db.query(LearningProgress).filter(LearningProgress.user_id == user.id, LearningProgress.block_id.in_(module_ids))
        }
        module_rows = []
        completed = 0
        for module in modules:
            progress = progress_map.get(module.id)
            status = progress.status if progress else LearningProgressStatus.NOT_STARTED.value
            if status == LearningProgressStatus.COMPLETED.value:
                completed += 1
            test = module.test
            attempts_used = 0
            latest_score = None
            latest_passed = None
            if test:
                attempts_used = db.query(TestAttempt).filter(TestAttempt.user_id == user.id, TestAttempt.test_id == test.id).count()
                latest = (
                    db.query(TestAttempt)
                    .filter(TestAttempt.user_id == user.id, TestAttempt.test_id == test.id)
                    .order_by(TestAttempt.created_at.desc())
                    .first()
                )
                if latest:
                    latest_score = latest.score
                    latest_passed = latest.passed
            module_rows.append(
                HrModuleProgressRowOut(
                    module_id=module.id,
                    module_name=module.name,
                    status=status,
                    test_id=test.id if test else None,
                    attempts_used=attempts_used,
                    latest_score=latest_score,
                    latest_passed=latest_passed,
                )
            )
        rows.append(
            HrCourseProgressRowOut(
                course_id=course.id,
                course_name=course.name,
                total=len(modules),
                completed=completed,
                modules=module_rows,
            )
        )
    return rows


@router.get("/trainees/{user_id}", response_model=HrTraineeDetailOut)
def trainee_detail(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).options(joinedload(User.departments)).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Стажёр не найден")
    return HrTraineeDetailOut(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        is_active=user.is_active,
        departments=[DepartmentOut(code=d.code, name=d.name) for d in user.departments],
        course_rows=_build_course_rows(user, db),
    )


@router.put("/trainees/{user_id}", response_model=HrTraineeDetailOut)
def update_trainee(user_id: int, payload: HrTraineeUpdateIn, db: Session = Depends(get_db)):
    user = db.query(User).options(joinedload(User.departments)).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Стажёр не найден")
    user.departments = _departments_by_codes(payload.department_codes, db)
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return HrTraineeDetailOut(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        is_active=user.is_active,
        departments=[DepartmentOut(code=d.code, name=d.name) for d in user.departments],
        course_rows=_build_course_rows(user, db),
    )
