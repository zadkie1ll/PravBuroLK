from django.db import migrations

UTM_SOURCES = [
    "youtube-stas", "youtube-pb", "vk-stas", "vk-pb",
    "instagram-stas", "instagram-pb", "telegram-stas", "telegram-pb",
    "tiktok-old", "tiktok-new", "dzen", "max", "taplink", "site",
    "avito", "partner", "email", "bot", "chat", "checklist",
]

UTM_MEDIUMS = ["cpc", "organic"]

BOT_BLOCKS = [
    ("consultation", "Старт бесплатной консультации, бот сразу начинает опрос"),
    ("chat", "Приглашение в закрытый чат поддержки должников"),
    ("pristavi", "Заявление приставу о сохранении прожиточного минимума при взыскании"),
    ("kollektory", "Видео о правах должника при общении с коллекторами"),
    ("mfc", "Видео об условиях бесплатного банкротства через МФЦ"),
    ("prikaz", "Заявление на отмену судебного приказа"),
    ("sid", "Видео про списание долга по сроку исковой давности"),
    ("detskie", "Заявление приставу о снятии ареста со счёта с детскими пособиями"),
    ("otmena", "Заявление на отзыв согласия банку на списание со счетов"),
    ("checklist", "Меню бесплатных чек-листов и гайдов"),
]


def seed(apps, schema_editor):
    UtmSource = apps.get_model("urlshorter", "UtmSource")
    UtmMedium = apps.get_model("urlshorter", "UtmMedium")
    BotBlock = apps.get_model("urlshorter", "BotBlock")

    for code in UTM_SOURCES:
        UtmSource.objects.get_or_create(code=code)

    for code in UTM_MEDIUMS:
        UtmMedium.objects.get_or_create(code=code)

    for key, title in BOT_BLOCKS:
        BotBlock.objects.get_or_create(key=key, defaults={"title": title})


def unseed(apps, schema_editor):
    UtmSource = apps.get_model("urlshorter", "UtmSource")
    UtmMedium = apps.get_model("urlshorter", "UtmMedium")
    BotBlock = apps.get_model("urlshorter", "BotBlock")

    UtmSource.objects.filter(code__in=UTM_SOURCES).delete()
    UtmMedium.objects.filter(code__in=UTM_MEDIUMS).delete()
    BotBlock.objects.filter(key__in=[key for key, _ in BOT_BLOCKS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("urlshorter", "0002_botblock_utmmedium_utmsource_marketinglink_and_more"),
    ]

    operations = [
        migrations.RunPython(seed, reverse_code=unseed),
    ]
