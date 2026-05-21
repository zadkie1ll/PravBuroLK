from django.contrib.auth import get_user_model
from django import forms

from .models import Course, Department, Module, ModuleMaterial, ModuleTest, QuestionOption, TestQuestion


class TraineeAccountForm(forms.Form):
    username = forms.CharField(label="Логин", max_length=150)
    first_name = forms.CharField(label="Имя", max_length=150, required=False)
    last_name = forms.CharField(label="Фамилия", max_length=150, required=False)
    email = forms.EmailField(label="Email", required=False)
    password = forms.CharField(label="Пароль", max_length=128, required=False)
    departments = forms.ModelMultipleChoiceField(
        label="Отделы",
        queryset=Department.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
    )
    is_active = forms.BooleanField(label="Активен", required=False, initial=True)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Пользователь с таким логином уже существует.")
        return username


class TraineeDepartmentsForm(forms.Form):
    departments = forms.ModelMultipleChoiceField(
        label="Отделы",
        queryset=Department.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    is_active = forms.BooleanField(label="Активен", required=False)


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
        fields = ["course", "name", "description", "private_video", "video_url", "order", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class ModuleMaterialForm(forms.ModelForm):
    class Meta:
        model = ModuleMaterial
        fields = ["title", "material_type", "file", "order", "is_active"]


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
