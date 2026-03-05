from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("telki", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="march8greeting",
            old_name="certificate_pdf",
            new_name="certificate_url",
        ),
        migrations.AlterField(
            model_name="march8greeting",
            name="certificate_url",
            field=models.URLField(blank=True, null=True, verbose_name="Ссылка на сертификат"),
        ),
    ]
