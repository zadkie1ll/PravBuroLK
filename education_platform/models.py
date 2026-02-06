from django.conf import settings
from django.db import models


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
