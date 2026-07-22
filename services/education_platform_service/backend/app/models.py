import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Table,
    Text,
    UniqueConstraint,
    Column,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class LearningProgressStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class TestAttemptStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class QuestionType(str, enum.Enum):
    CHOICE = "choice"
    MULTI_CHOICE = "multi_choice"
    TEXT = "text"


user_departments = Table(
    "user_departments",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("department_id", ForeignKey("departments.id"), primary_key=True),
)

course_departments = Table(
    "course_departments",
    Base.metadata,
    Column("course_id", ForeignKey("courses.id"), primary_key=True),
    Column("department_id", ForeignKey("departments.id"), primary_key=True),
)


class User(Base):
    """Свой пользователь сервиса (JWT-логин). TraineeProfile из оригинала
    (birthday/started_at/stats/departments) свёрнут прямо в эту таблицу —
    отдельного "Django User" тут нет, разводить профиль некуда."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(150), default="")
    last_name: Mapped[str] = mapped_column(String(150), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)

    birthday: Mapped[date | None] = mapped_column(Date, nullable=True)
    started_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    departments: Mapped[list["Department"]] = relationship(secondary=user_departments)


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str] = mapped_column(String(1000), default="")
    photo_url: Mapped[str] = mapped_column(String(1000), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    departments: Mapped[list["Department"]] = relationship(secondary=course_departments)
    modules: Mapped[list["Module"]] = relationship(back_populates="course", order_by="Module.order")


class Module(Base):
    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    video_url: Mapped[str] = mapped_column(String(1000), default="")
    private_video: Mapped[str] = mapped_column(String(500), default="")
    order: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    course: Mapped["Course"] = relationship(back_populates="modules")
    materials: Mapped[list["ModuleMaterial"]] = relationship(back_populates="module", order_by="ModuleMaterial.order")
    test: Mapped["ModuleTest"] = relationship(back_populates="module", uselist=False)


class ModuleMaterial(Base):
    __tablename__ = "module_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id"))
    title: Mapped[str] = mapped_column(String(255))
    material_type: Mapped[str] = mapped_column(String(32), default="pdf")
    file: Mapped[str] = mapped_column(String(500))
    order: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    module: Mapped["Module"] = relationship(back_populates="materials")


class ModuleTest(Base):
    __tablename__ = "module_tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id"), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    max_score: Mapped[float] = mapped_column(Float, default=0)
    passing_score: Mapped[float] = mapped_column(Float, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    module: Mapped["Module"] = relationship(back_populates="test")
    questions: Mapped[list["TestQuestion"]] = relationship(back_populates="test", order_by="TestQuestion.order")


class TestQuestion(Base):
    __tablename__ = "test_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("module_tests.id"))
    text: Mapped[str] = mapped_column(Text)
    question_type: Mapped[str] = mapped_column(String(32), default=QuestionType.CHOICE.value)
    score: Mapped[float] = mapped_column(Float, default=0)
    order: Mapped[int] = mapped_column(Integer, default=1)

    test: Mapped["ModuleTest"] = relationship(back_populates="questions")
    options: Mapped[list["QuestionOption"]] = relationship(back_populates="question", order_by="QuestionOption.order")


class QuestionOption(Base):
    __tablename__ = "question_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("test_questions.id"))
    text: Mapped[str] = mapped_column(String(500))
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[int] = mapped_column(Integer, default=1)

    question: Mapped["TestQuestion"] = relationship(back_populates="options")


class LearningProgress(Base):
    __tablename__ = "learning_progress"
    __table_args__ = (UniqueConstraint("user_id", "block_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    block_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(32), default=LearningProgressStatus.NOT_STARTED.value)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_step: Mapped[str] = mapped_column(String(128), default="")
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TestAttempt(Base):
    __tablename__ = "test_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    test_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(32), default=TestAttemptStatus.IN_PROGRESS.value)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AnswerError(Base):
    __tablename__ = "answer_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("test_attempts.id"), index=True)
    question_id: Mapped[int] = mapped_column(Integer, index=True)
    answer_type: Mapped[str] = mapped_column(String(16), default="choice")
    error_type: Mapped[str] = mapped_column(String(64), default="")
    user_answer: Mapped[dict] = mapped_column(JSON, default=dict)
    correct_answer: Mapped[dict] = mapped_column(JSON, default=dict)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
