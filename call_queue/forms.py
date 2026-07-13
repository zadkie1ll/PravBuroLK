from django import forms

from leadreport.models import SalesManager

from .models import CallEntityType, CallResult
from .services.bitrix.deal_service import BitrixDealService


class CallSessionCreateForm(forms.Form):
    entity_type = forms.ChoiceField(
        label="Что обзваниваем",
        choices=CallEntityType.choices,
        initial=CallEntityType.DEAL,
    )
    date_from = forms.DateField(
        label="Дата от",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = forms.DateField(
        label="Дата до",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    stage_id = forms.ChoiceField(label="Стадия сделки", required=False)
    source_id = forms.ChoiceField(label="Источник", required=False)
    responsible_id = forms.ChoiceField(label="Ответственный", required=False)
    only_unanswered = forms.BooleanField(label="Только недозвоны", required=False)
    only_without_repeat = forms.BooleanField(
        label="Только без повторного недозвона",
        required=False,
    )

    def __init__(self, *args, bitrix_service: BitrixDealService | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        service = bitrix_service or BitrixDealService()
        entity_type = (
            (self.data.get("entity_type") if self.is_bound else None)
            or self.initial.get("entity_type")
            or CallEntityType.DEAL
        )
        blank = [("", "---------")]
        self.fields["stage_id"].choices = blank + service.get_stage_choices(entity_type)
        self.fields["source_id"].choices = blank + service.get_source_choices(entity_type)
        self.fields["responsible_id"].choices = blank + service.get_responsible_choices()
        self.fields["stage_id"].label = "Стадия сделки" if entity_type == CallEntityType.DEAL else "Статус лида"

        for name in ("entity_type", "date_from", "date_to", "stage_id", "source_id", "responsible_id"):
            self.fields[name].widget.attrs.setdefault(
                "class",
                "w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-amber-500",
            )
        for name in ("only_unanswered", "only_without_repeat"):
            self.fields[name].widget.attrs.setdefault("class", "h-4 w-4 rounded border-slate-300")

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")
        if date_from and date_to and date_from > date_to:
            raise forms.ValidationError("Дата начала не может быть позже даты окончания.")
        return cleaned_data


class CallResultForm(forms.Form):
    queue_item_id = forms.IntegerField(widget=forms.HiddenInput())
    comment = forms.CharField(
        label="Комментарий",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Комментарий по звонку",
                "class": "w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-amber-500",
            }
        ),
    )


class MegafonTestCallForm(forms.Form):
    sales_manager = forms.ModelChoiceField(
        label="Менеджер",
        queryset=SalesManager.objects.filter(is_active=True).order_by("name"),
        empty_label=None,
        widget=forms.Select(
            attrs={
                "class": "w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-amber-500",
            }
        ),
    )
    clid = forms.CharField(
        label="Исходящий номер",
        required=False,
        max_length=64,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Если пусто, возьмем из менеджера",
                "class": "w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-amber-500",
            }
        ),
    )
    show_phone = forms.BooleanField(
        label="Показывать номер менеджеру",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(
            attrs={"class": "h-4 w-4 rounded border-slate-300"}
        ),
    )


class MegafonPhoneListForm(forms.Form):
    phone_list = forms.CharField(
        label="Список номеров",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 8,
                "placeholder": "Один номер на строку, через запятую или точку с запятой",
                "class": "w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-amber-500",
            }
        ),
    )

    def clean_phone_list(self):
        raw_value = self.cleaned_data.get("phone_list", "")
        normalized = raw_value.replace(",", "\n").replace(";", "\n")
        phones = []
        seen = set()
        for chunk in normalized.splitlines():
            phone = "".join(ch for ch in chunk if ch.isdigit() or ch == "+").strip()
            if not phone or phone in seen:
                continue
            seen.add(phone)
            phones.append(phone)
        return phones


class CustomQueueAddForm(forms.Form):
    entity_type = forms.ChoiceField(
        label="Что добавляем",
        choices=CallEntityType.choices,
        initial=CallEntityType.DEAL,
        widget=forms.Select(
            attrs={
                "class": "w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-amber-500",
            }
        ),
    )
    query = forms.CharField(
        label="Телефон или имя клиента",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Например: +7 900 123-45-67 или Иванов",
                "class": "w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-amber-500",
            }
        ),
    )
    category_id = forms.ChoiceField(
        label="Канбан",
        required=False,
        widget=forms.Select(
            attrs={
                "class": "w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-amber-500",
                "data-category-field": "1",
            }
        ),
    )

    def __init__(self, *args, bitrix_service: BitrixDealService | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        service = bitrix_service or BitrixDealService()
        entity_type = (
            (self.data.get("entity_type") if self.is_bound else None)
            or self.initial.get("entity_type")
            or CallEntityType.DEAL
        )
        is_deal = entity_type == CallEntityType.DEAL
        category_choices = service.get_deal_category_choices() if is_deal else []
        self.fields["category_id"].choices = [("", "Все канбаны")] + category_choices
        if not is_deal:
            self.initial["category_id"] = ""

    def clean_query(self):
        query = (self.cleaned_data.get("query") or "").strip()
        if not query:
            raise forms.ValidationError("Введите номер телефона или имя клиента.")
        return query


class ProductionRecallForm(forms.Form):
    entity_type = forms.ChoiceField(
        label="Что обзваниваем",
        choices=CallEntityType.choices,
        initial=CallEntityType.DEAL,
        widget=forms.Select(
            attrs={
                "class": "w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-amber-500",
            }
        ),
    )
    date_from = forms.DateField(
        label="Дата от",
        required=False,
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-amber-500",
            }
        ),
    )
    date_to = forms.DateField(
        label="Дата до",
        required=False,
        widget=forms.DateInput(
            attrs={
                "type": "date",
                "class": "w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-amber-500",
            }
        ),
    )
    stage_id = forms.ChoiceField(
        label="Колонка CRM",
        required=False,
        widget=forms.Select(
            attrs={
                "class": "w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:border-amber-500",
            }
        ),
    )
    auto_dial = forms.BooleanField(
        label="Автоматически переходить к следующему номеру после недозвона",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(
            attrs={"class": "h-4 w-4 rounded border-slate-300"}
        ),
    )

    def __init__(self, *args, bitrix_service: BitrixDealService | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        service = bitrix_service or BitrixDealService()
        entity_type = (
            (self.data.get("entity_type") if self.is_bound else None)
            or self.initial.get("entity_type")
            or CallEntityType.DEAL
        )
        is_deal = entity_type == CallEntityType.DEAL

        submitted_stage = (self.data.get("stage_id") if self.is_bound else None) or self.initial.get("stage_id") or ""
        stage_choices = service.get_stage_choices(entity_type)
        if submitted_stage and submitted_stage not in {value for value, _label in stage_choices}:
            stage_choices = stage_choices + [(submitted_stage, submitted_stage)]
        self.fields["stage_id"].choices = [("", "Все стадии")] + stage_choices
        self.fields["stage_id"].label = "Стадия сделки" if is_deal else "Статус лида"

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")
        if not date_from:
            self.add_error("date_from", "Укажите дату.")
        if not date_to:
            self.add_error("date_to", "Укажите дату.")
        if date_from and date_to and date_from > date_to:
            raise forms.ValidationError("Дата начала не может быть позже даты окончания.")
        return cleaned_data
