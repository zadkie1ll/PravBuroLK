import csv
import secrets
import string
from urllib.parse import urlencode

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt

from .models import (
    BOT_PREVIEW_USER_AGENTS,
    BotBlock,
    MarketingClick,
    MarketingLink,
    UrlShortener,
    UtmMedium,
    UtmSource,
    validate_utm_free_text,
)

BOT_BASE_URL = "https://t.me/pravburohelpBot"
SOURCE_ALPHABET = string.ascii_lowercase + string.digits

GROUP_BY_FIELDS = {
    "utm_source": "link__utm_source__code",
    "utm_medium": "link__utm_medium__code",
    "utm_campaign": "link__utm_campaign",
    "utm_content": "link__utm_content",
    "utm_term": "link__utm_term",
    "link_type": "link__link_type",
    "destination": "link__destination",
    "bot_block": "link__bot_block__key",
}

FILTER_LOOKUPS = {
    "utm_source": "link__utm_source__code",
    "utm_medium": "link__utm_medium__code",
    "utm_campaign": "link__utm_campaign",
    "utm_content": "link__utm_content",
    "utm_term": "link__utm_term",
    "link_type": "link__link_type",
    "destination": "link__destination__icontains",
}


def _generate_unique_source():
    while True:
        code = "".join(secrets.choice(SOURCE_ALPHABET) for _ in range(7))
        collides = (
            MarketingLink.objects.filter(source=code).exists()
            or UrlShortener.objects.filter(source=code).exists()
        )
        if not collides:
            return code


def _build_destination_with_utm(link: MarketingLink) -> str:
    if link.link_type == MarketingLink.LINK_TYPE_BOT:
        parts = [link.bot_block.key, link.utm_source.code, link.utm_medium.code, link.utm_campaign]
        return f"{BOT_BASE_URL}?start=" + "_".join(parts)

    params = {}
    if link.link_type == MarketingLink.LINK_TYPE_SITE:
        params["utm_source"] = link.utm_source.code
        params["utm_medium"] = link.utm_medium.code
    params["utm_campaign"] = link.utm_campaign
    if link.utm_content:
        params["utm_content"] = link.utm_content
    if link.utm_term:
        params["utm_term"] = link.utm_term

    separator = "&" if "?" in link.destination else "?"
    return f"{link.destination}{separator}{urlencode(params)}"


def _build_public_link(link: MarketingLink, request) -> str:
    base = request.build_absolute_uri(reverse("marketing_link_redirect"))
    return f"{base}?source={link.source}"


@login_required
def marketing_link_form(request):
    utm_sources = UtmSource.objects.filter(is_active=True).order_by("code")
    utm_mediums = UtmMedium.objects.filter(is_active=True).order_by("code")
    bot_blocks = BotBlock.objects.filter(is_active=True).order_by("key")

    known_campaigns = MarketingLink.objects.exclude(utm_campaign="").values_list("utm_campaign", flat=True).distinct()
    known_contents = MarketingLink.objects.exclude(utm_content="").values_list("utm_content", flat=True).distinct()
    known_terms = MarketingLink.objects.exclude(utm_term="").values_list("utm_term", flat=True).distinct()

    result_link = None
    is_existing = False
    errors = []

    if request.method == "POST":
        link_type = request.POST.get("link_type")
        destination = request.POST.get("destination", "").strip()
        utm_source_obj = UtmSource.objects.filter(id=request.POST.get("utm_source"), is_active=True).first()
        utm_medium_obj = UtmMedium.objects.filter(id=request.POST.get("utm_medium"), is_active=True).first()
        utm_campaign = request.POST.get("utm_campaign", "").strip().lower()
        utm_content = request.POST.get("utm_content", "").strip().lower()
        utm_term = request.POST.get("utm_term", "").strip().lower()
        bot_block_obj = None

        if link_type not in dict(MarketingLink.LINK_TYPE_CHOICES):
            errors.append("Не выбран тип назначения.")
        if not utm_source_obj:
            errors.append("Выберите источник (utm_source).")
        if not utm_medium_obj:
            errors.append("Выберите тип трафика (utm_medium).")
        if not utm_campaign:
            errors.append("Заполните utm_campaign.")

        if link_type == MarketingLink.LINK_TYPE_BOT:
            bot_block_obj = BotBlock.objects.filter(id=request.POST.get("bot_block"), is_active=True).first()
            if not bot_block_obj:
                errors.append("Выберите блок бота.")
            destination = BOT_BASE_URL
        elif not destination:
            errors.append("Укажите целевую ссылку.")

        for field_name, value in (("utm_campaign", utm_campaign), ("utm_content", utm_content), ("utm_term", utm_term)):
            if value:
                try:
                    validate_utm_free_text(value)
                except ValidationError as e:
                    errors.append(f"{field_name}: {e.message}")

        if not errors:
            existing = MarketingLink.objects.filter(
                link_type=link_type,
                destination=destination,
                utm_source=utm_source_obj,
                utm_medium=utm_medium_obj,
                utm_campaign=utm_campaign,
                utm_content=utm_content,
                utm_term=utm_term,
                bot_block=bot_block_obj,
            ).first()

            if existing:
                result_link, is_existing = existing, True
            else:
                result_link = MarketingLink.objects.create(
                    source=_generate_unique_source(),
                    link_type=link_type,
                    destination=destination,
                    utm_source=utm_source_obj,
                    utm_medium=utm_medium_obj,
                    utm_campaign=utm_campaign,
                    utm_content=utm_content,
                    utm_term=utm_term,
                    bot_block=bot_block_obj,
                )

    return render(request, "marketing_link_form.html", {
        "utm_sources": utm_sources,
        "utm_mediums": utm_mediums,
        "bot_blocks": bot_blocks,
        "errors": errors,
        "result_link": result_link,
        "is_existing": is_existing,
        "public_link": _build_public_link(result_link, request) if result_link else None,
        "known_campaigns": known_campaigns,
        "known_contents": known_contents,
        "known_terms": known_terms,
    })


@csrf_exempt
def marketing_link_redirect(request):
    source = request.GET.get("source")
    if not source:
        return redirect("index")

    link = get_object_or_404(MarketingLink, source=source)

    user_agent = request.META.get("HTTP_USER_AGENT", "") or ""
    is_bot_preview = any(bot_ua.lower() in user_agent.lower() for bot_ua in BOT_PREVIEW_USER_AGENTS)

    MarketingClick.objects.create(
        link=link,
        ip_address=request.META.get("REMOTE_ADDR"),
        user_agent=user_agent,
        is_bot_preview=is_bot_preview,
    )

    return redirect(_build_destination_with_utm(link))


@login_required
def marketing_stats(request):
    qs = MarketingClick.objects.filter(is_bot_preview=False).select_related(
        "link", "link__utm_source", "link__utm_medium", "link__bot_block"
    )

    click_from = parse_date(request.GET.get("click_from") or "")
    click_to = parse_date(request.GET.get("click_to") or "")
    created_from = parse_date(request.GET.get("created_from") or "")
    created_to = parse_date(request.GET.get("created_to") or "")

    if click_from:
        qs = qs.filter(clicked_at__date__gte=click_from)
    if click_to:
        qs = qs.filter(clicked_at__date__lte=click_to)
    if created_from:
        qs = qs.filter(link__created_at__date__gte=created_from)
    if created_to:
        qs = qs.filter(link__created_at__date__lte=created_to)

    for param, lookup in FILTER_LOOKUPS.items():
        value = request.GET.get(param)
        if value:
            qs = qs.filter(**{lookup: value})

    group_by = request.GET.get("group_by") or "utm_source"
    group_field = GROUP_BY_FIELDS.get(group_by, GROUP_BY_FIELDS["utm_source"])

    raw_grouped = qs.values(group_field).annotate(clicks=Count("id")).order_by("-clicks")
    grouped = [
        {"group_value": row[group_field] if row[group_field] not in (None, "") else "—", "clicks": row["clicks"]}
        for row in raw_grouped
    ]
    total_clicks = sum(row["clicks"] for row in grouped)

    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="marketing_stats.csv"'
        writer = csv.writer(response)
        writer.writerow([group_by, "clicks"])
        for row in grouped:
            writer.writerow([row["group_value"], row["clicks"]])
        return response

    return render(request, "marketing_stats.html", {
        "grouped": grouped,
        "group_field": group_field,
        "group_by": group_by,
        "group_options": list(GROUP_BY_FIELDS.keys()),
        "total_clicks": total_clicks,
        "utm_sources": UtmSource.objects.filter(is_active=True).order_by("code"),
        "utm_mediums": UtmMedium.objects.filter(is_active=True).order_by("code"),
        "link_types": MarketingLink.LINK_TYPE_CHOICES,
        "filters": request.GET,
    })


@staff_member_required
def marketing_dictionaries(request):
    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "add_source":
            code = request.POST.get("code", "").strip().lower()
            if code:
                try:
                    validate_utm_free_text(code)
                    UtmSource.objects.get_or_create(code=code)
                except ValidationError:
                    pass

        elif action == "toggle_source":
            obj = get_object_or_404(UtmSource, id=request.POST.get("id"))
            obj.is_active = not obj.is_active
            obj.save()

        elif action == "add_medium":
            code = request.POST.get("code", "").strip().lower()
            if code:
                try:
                    validate_utm_free_text(code)
                    UtmMedium.objects.get_or_create(code=code)
                except ValidationError:
                    pass

        elif action == "toggle_medium":
            obj = get_object_or_404(UtmMedium, id=request.POST.get("id"))
            obj.is_active = not obj.is_active
            obj.save()

        elif action == "add_bot_block":
            key = request.POST.get("key", "").strip().lower()
            title = request.POST.get("title", "").strip()
            if key and title:
                try:
                    validate_utm_free_text(key)
                    BotBlock.objects.get_or_create(key=key, defaults={"title": title})
                except ValidationError:
                    pass

        elif action == "toggle_bot_block":
            obj = get_object_or_404(BotBlock, id=request.POST.get("id"))
            obj.is_active = not obj.is_active
            obj.save()

        return redirect("marketing_dictionaries")

    return render(request, "marketing_dictionaries.html", {
        "utm_sources": UtmSource.objects.order_by("-is_active", "code"),
        "utm_mediums": UtmMedium.objects.order_by("-is_active", "code"),
        "bot_blocks": BotBlock.objects.order_by("-is_active", "key"),
    })
