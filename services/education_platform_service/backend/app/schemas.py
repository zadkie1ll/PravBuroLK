from pydantic import BaseModel


class RegisterRequest(BaseModel):
    username: str
    password: str
    department: str


class LoginRequest(BaseModel):
    username: str
    password: str
    department: str | None = None


class DepartmentOut(BaseModel):
    code: str
    name: str


class UserOut(BaseModel):
    id: int
    username: str
    first_name: str
    last_name: str
    department: str
    departments: list[DepartmentOut]
    is_staff: bool = False


class TokenResponse(BaseModel):
    detail: str = "ok"
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class CourseOut(BaseModel):
    id: int
    name: str
    description: str
    image_url: str
    photo_url: str
    modules_count: int
    completed_modules: int


class ModuleMaterialOut(BaseModel):
    id: int
    title: str
    material_type: str
    url: str
    order: int


class ModuleOut(BaseModel):
    id: int
    name: str
    description: str
    video_url: str
    video_is_private: bool
    materials: list[ModuleMaterialOut]
    order: int
    status: str


class QuestionOptionOut(BaseModel):
    id: int
    text: str


class TestQuestionOut(BaseModel):
    id: int
    text: str
    question_type: str
    options: list[QuestionOptionOut]
    score: float
    order: int


class TestOut(BaseModel):
    id: int
    name: str
    description: str
    max_score: float
    passing_score: float
    max_attempts: int
    questions: list[TestQuestionOut]
    attempts_left: int


class ProgressUpdateRequest(BaseModel):
    module_id: int
    status: str


class SubmitTestRequest(BaseModel):
    module_id: int
    answers: dict = {}


# ---- HR ----


class HrCourseIn(BaseModel):
    name: str
    description: str = ""
    image_url: str = ""
    photo_url: str = ""
    department_codes: list[str] = []
    is_active: bool = True


class HrCourseOut(BaseModel):
    id: int
    name: str
    description: str
    image_url: str
    photo_url: str
    department_codes: list[str]
    is_active: bool


class HrMaterialOut(BaseModel):
    id: int
    title: str
    material_type: str
    file: str
    order: int
    is_active: bool


class HrTestSummaryOut(BaseModel):
    id: int
    name: str
    is_active: bool
    questions_count: int


class HrModuleOut(BaseModel):
    id: int
    course_id: int
    name: str
    description: str
    video_url: str
    private_video: str
    order: int
    is_active: bool
    materials: list[HrMaterialOut]
    test: HrTestSummaryOut | None


class HrCourseTreeOut(HrCourseOut):
    modules: list[HrModuleOut]


class HrModuleIn(BaseModel):
    course_id: int
    name: str
    description: str = ""
    video_url: str = ""
    order: int = 1
    is_active: bool = True


class HrMaterialIn(BaseModel):
    title: str
    material_type: str = "pdf"
    order: int = 1
    is_active: bool = True


class HrTestIn(BaseModel):
    name: str
    description: str = ""
    max_score: float = 0
    passing_score: float = 0
    max_attempts: int = 3
    is_active: bool = True


class HrQuestionOptionOut(BaseModel):
    id: int
    text: str
    is_correct: bool
    order: int


class HrQuestionOut(BaseModel):
    id: int
    text: str
    question_type: str
    score: float
    order: int
    options: list[HrQuestionOptionOut]


class HrTestOut(BaseModel):
    id: int
    module_id: int
    name: str
    description: str
    max_score: float
    passing_score: float
    max_attempts: int
    is_active: bool
    questions: list[HrQuestionOut]


class HrQuestionIn(BaseModel):
    text: str
    question_type: str = "choice"
    score: float = 0
    order: int = 1


class HrOptionIn(BaseModel):
    text: str
    is_correct: bool = False
    order: int = 1


class HrTraineeListItemOut(BaseModel):
    id: int
    username: str
    first_name: str
    last_name: str
    is_active: bool
    departments: list[DepartmentOut]
    progress_count: int
    completed_count: int
    attempts_count: int
    passed_attempts_count: int


class HrTraineeCreateIn(BaseModel):
    username: str
    first_name: str = ""
    last_name: str = ""
    password: str = ""
    department_codes: list[str] = []
    is_active: bool = True


class HrTraineeCreateOut(BaseModel):
    detail: str = "ok"
    username: str
    password: str
    user: HrTraineeListItemOut


class HrTraineeUpdateIn(BaseModel):
    department_codes: list[str] = []
    is_active: bool = True


class HrModuleProgressRowOut(BaseModel):
    module_id: int
    module_name: str
    status: str
    test_id: int | None
    attempts_used: int
    latest_score: float | None
    latest_passed: bool | None


class HrCourseProgressRowOut(BaseModel):
    course_id: int
    course_name: str
    total: int
    completed: int
    modules: list[HrModuleProgressRowOut]


class HrTraineeDetailOut(BaseModel):
    id: int
    username: str
    first_name: str
    last_name: str
    is_active: bool
    departments: list[DepartmentOut]
    course_rows: list[HrCourseProgressRowOut]
