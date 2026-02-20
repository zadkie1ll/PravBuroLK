from django import forms

from .models import Course, Module, ModuleTest, QuestionOption, TestQuestion


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ["name", "description", "image_url", "photo_url", "departments", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "departments": forms.CheckboxSelectMultiple(),
        }


class ModuleForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = ["course", "name", "description", "video_url", "order", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class ModuleTestForm(forms.ModelForm):
    class Meta:
        model = ModuleTest
        fields = ["name", "description", "max_score", "passing_score", "max_attempts", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class TestQuestionForm(forms.ModelForm):
    class Meta:
        model = TestQuestion
        fields = ["text", "question_type", "score", "order"]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 3}),
        }


class QuestionOptionForm(forms.ModelForm):
    class Meta:
        model = QuestionOption
        fields = ["text", "is_correct", "order"]
