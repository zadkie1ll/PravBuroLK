# yourapp/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Department, Course, Module, ModuleMaterial, ModuleTest, TestQuestion, QuestionOption,
    TraineeProfile, LearningProgress, TestAttempt, AnswerError, ProgressEvent
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active', 'course_count')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')
    ordering = ('name',)

    def course_count(self, obj):
        return obj.courses.count()
    course_count.short_description = "Курсов"


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'module_count', 'departments_list')
    list_filter = ('is_active', 'departments')
    search_fields = ('name', 'description')
    filter_horizontal = ('departments',)

    def module_count(self, obj):
        return obj.modules.count()
    module_count.short_description = "Модулей"

    def departments_list(self, obj):
        return ", ".join(d.code for d in obj.departments.all()[:3]) + ("..." if obj.departments.count() > 3 else "")
    departments_list.short_description = "Департаменты"


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'course', 'order', 'is_active', 'has_private_video', 'has_test')
    list_filter = ('is_active', 'course')
    search_fields = ('name', 'description', 'course__name')
    raw_id_fields = ('course',)

    def has_private_video(self, obj):
        return bool(obj.private_video)
    has_private_video.boolean = True
    has_private_video.short_description = "Приватное видео"

    def has_test(self, obj):
        return bool(obj.test)
    has_test.boolean = True
    has_test.short_description = "Есть тест"


@admin.register(ModuleMaterial)
class ModuleMaterialAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'material_type', 'order', 'is_active')
    list_filter = ('is_active', 'material_type', 'module__course')
    search_fields = ('title', 'module__name', 'module__course__name')
    raw_id_fields = ('module',)


@admin.register(ModuleTest)
class ModuleTestAdmin(admin.ModelAdmin):
    list_display = ('name', 'module', 'max_score', 'passing_score', 'max_attempts', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description', 'module__name')
    raw_id_fields = ('module',)


@admin.register(TestQuestion)
class TestQuestionAdmin(admin.ModelAdmin):
    list_display = ('order', 'short_text', 'question_type', 'score', 'test')
    list_filter = ('question_type', 'test__module__course')
    search_fields = ('text', 'test__name', 'test__module__name')
    raw_id_fields = ('test',)

    def short_text(self, obj):
        return (obj.text[:80] + "...") if len(obj.text) > 80 else obj.text
    short_text.short_description = "Вопрос"


@admin.register(QuestionOption)
class QuestionOptionAdmin(admin.ModelAdmin):
    list_display = ('short_text', 'is_correct', 'order', 'question')
    list_filter = ('is_correct', 'question__test__module__course')
    search_fields = ('text', 'question__text')
    raw_id_fields = ('question',)

    def short_text(self, obj):
        return obj.text[:60] + "..." if len(obj.text) > 60 else obj.text
    short_text.short_description = "Вариант"


@admin.register(LearningProgress)
class LearningProgressAdmin(admin.ModelAdmin):
    list_display = ('trainee_link', 'block_id', 'status', 'started_at', 'completed_at', 'last_activity_at')
    list_filter = ('status', 'trainee__is_active')
    search_fields = ('trainee__user__username', 'trainee__user__email', 'block_id')
    date_hierarchy = 'last_activity_at'
    readonly_fields = ('created_at', 'updated_at')

    def trainee_link(self, obj):
        return format_html('<a href="/admin/yourapp/traineeprofile/{}/">{}</a>', obj.trainee_id, obj.trainee)
    trainee_link.short_description = "Стажёр"
    trainee_link.admin_order_field = 'trainee__user__username'


@admin.register(TestAttempt)
class TestAttemptAdmin(admin.ModelAdmin):
    list_display = ('trainee_link', 'test_id', 'attempt_number', 'status', 'score_display', 'passed', 'started_at', 'finished_at')
    list_filter = ('status', 'passed', 'attempt_number')
    search_fields = ('trainee__user__username', 'test_id')
    date_hierarchy = 'started_at'
    readonly_fields = ('created_at', 'updated_at', 'started_at')

    def trainee_link(self, obj):
        return format_html('<a href="/admin/yourapp/traineeprofile/{}/">{}</a>', obj.trainee_id, obj.trainee)
    trainee_link.short_description = "Стажёр"
    trainee_link.admin_order_field = 'trainee__user__username'

    def score_display(self, obj):
        if obj.score is None:
            return "—"
        return f"{obj.score:.1f} / {obj.max_score:.1f}" if obj.max_score else f"{obj.score:.1f}"
    score_display.short_description = "Результат"


@admin.register(AnswerError)
class AnswerErrorAdmin(admin.ModelAdmin):
    list_display = ('attempt_link', 'question_id', 'answer_type', 'error_type', 'created_at')
    list_filter = ('answer_type', 'error_type', 'attempt__status')
    search_fields = ('attempt__trainee__user__username', 'question_id', 'error_type')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)

    def attempt_link(self, obj):
        return format_html(
            '<a href="/admin/yourapp/testattempt/{}/">Попытка #{} (trainee {})</a>',
            obj.attempt_id, obj.attempt.attempt_number, obj.attempt.trainee_id
        )
    attempt_link.short_description = "Попытка"
    attempt_link.allow_tags = True


@admin.register(ProgressEvent)
class ProgressEventAdmin(admin.ModelAdmin):
    list_display = ('trainee_link', 'event_type', 'created_at')
    list_filter = ('event_type',)
    search_fields = ('trainee__user__username', 'event_type')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)

    def trainee_link(self, obj):
        return format_html('<a href="/admin/yourapp/traineeprofile/{}/">{}</a>', obj.trainee_id, obj.trainee)
    trainee_link.short_description = "Стажёр"
    trainee_link.admin_order_field = 'trainee__user__username'
