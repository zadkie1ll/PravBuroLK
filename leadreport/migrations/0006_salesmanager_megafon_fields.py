from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("leadreport", "0005_issuedcredentiallog"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesmanager",
            name="megafon_clid",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="salesmanager",
            name="megafon_group",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="salesmanager",
            name="megafon_user",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
    ]
