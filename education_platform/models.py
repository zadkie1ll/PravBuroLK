from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models

private_storage = FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


class Department(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Course(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    image_url = models.URLField(max_length=1000, blank=True)
    photo_url = models.URLField(max_length=1000, blank=True)
    departments = models.ManyToManyField(Department, related_name="courses", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class Module(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="modules")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    video_url = models.URLField(max_length=1000, blank=True)
    private_video = models.FileField(
        upload_to="education/videos/",
        storage=private_storage,
        blank=True,
    )
    order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["course_id", "order", "id"]

    def __str__(self):
        return f"{self.course.name}: {self.name}"


class ModuleMaterial(models.Model):
    class MaterialType(models.TextChoices):
        PDF = "pdf", "PDF"

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="materials")
    title = models.CharField(max_length=255)
    material_type = models.CharField(max_length=32, choices=MaterialType.choices, default=MaterialType.PDF)
    file = models.FileField(
        upload_to="education/materials/",
        storage=private_storage,
    )
    order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["module_id", "order", "id"]

    def __str__(self):
        return f"{self.module.name}: {self.title}"


class ModuleTest(models.Model):
    module = models.OneToOneField(Module, on_delete=models.CASCADE, related_name="test")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    max_score = models.FloatField(default=0)
    passing_score = models.FloatField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["module_id"]

    def __str__(self):
        return f"Test: {self.name}"


class TestQuestion(models.Model):
    class QuestionType(models.TextChoices):
        CHOICE = "choice", "Choice"
        MULTI_CHOICE = "multi_choice", "Multi choice"
        TEXT = "text", "Text"

    test = models.ForeignKey(ModuleTest, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    question_type = models.CharField(max_length=32, choices=QuestionType.choices, default=QuestionType.CHOICE)
    score = models.FloatField(default=0)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["test_id", "order", "id"]

    def __str__(self):
        return f"Q{self.order}: {self.text[:60]}"


class QuestionOption(models.Model):
    question = models.ForeignKey(TestQuestion, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["question_id", "order", "id"]

    def __str__(self):
        return self.text


class TraineeProfile(models.Model):
    """
    Профиль стажёра (надстройка над обычным Django User).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trainee_profile",
    )

    birthday = models.DateField(null=True, blank=True)

    started_at = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    departments = models.ManyToManyField(Department, related_name="trainees", blank=True)

    stats = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        full_name = self.user.get_full_name() or self.user.username
        return f"Trainee: {full_name}"


class LearningProgress(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        PAUSED = "paused", "Paused"

    trainee = models.ForeignKey(
        TraineeProfile,
        on_delete=models.CASCADE,
        related_name="learning_progress",
    )
    block_id = models.IntegerField(db_index=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.NOT_STARTED,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    current_step = models.CharField(max_length=128, blank=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    meta = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("trainee", "block_id")
        indexes = [
            models.Index(fields=["trainee", "status"]),
            models.Index(fields=["block_id", "status"]),
        ]

    def __str__(self):
        return f"Progress: {self.trainee_id} block {self.block_id} ({self.status})"


class TestAttempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        ABORTED = "aborted", "Aborted"

    trainee = models.ForeignKey(
        TraineeProfile,
        on_delete=models.CASCADE,
        related_name="test_attempts",
    )
    test_id = models.IntegerField(db_index=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
    )
    attempt_number = models.IntegerField(default=1)
    score = models.FloatField(null=True, blank=True)
    max_score = models.FloatField(null=True, blank=True)
    passed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    meta = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["trainee", "test_id"]),
            models.Index(fields=["test_id", "status"]),
        ]

    def __str__(self):
        return f"Attempt: {self.trainee_id} test {self.test_id} #{self.attempt_number}"


class AnswerError(models.Model):
    class AnswerType(models.TextChoices):
        CHOICE = "choice", "Choice"
        TEXT = "text", "Text"
        OTHER = "other", "Other"

    attempt = models.ForeignKey(
        TestAttempt,
        on_delete=models.CASCADE,
        related_name="errors",
    )
    question_id = models.IntegerField(db_index=True)
    answer_type = models.CharField(
        max_length=16,
        choices=AnswerType.choices,
        default=AnswerType.CHOICE,
    )
    error_type = models.CharField(max_length=64)
    user_answer = models.JSONField(default=dict, blank=True)
    correct_answer = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["attempt", "question_id"]),
            models.Index(fields=["question_id"]),
        ]

    def __str__(self):
        return f"Error: attempt {self.attempt_id} question {self.question_id}"


class ProgressEvent(models.Model):
    trainee = models.ForeignKey(
        TraineeProfile,
        on_delete=models.CASCADE,
        related_name="progress_events",
    )
    event_type = models.CharField(max_length=64)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["trainee", "created_at"]),
            models.Index(fields=["event_type", "created_at"]),
        ]

    def __str__(self):
        return f"Event: {self.trainee_id} {self.event_type}"
