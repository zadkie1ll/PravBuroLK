from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("telki", "0002_certificate_url"),
    ]

    operations = [
        migrations.RenameField(
            model_name="march8greeting",
            old_name="certificate_url",
            new_name="certificate_pdf",
        ),
        migrations.AlterField(
            model_name="march8greeting",
            name="certificate_pdf",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="telki/certificates/",
                verbose_name="PDF-сертификат",
            ),
        ),
    ]
