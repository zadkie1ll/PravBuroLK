from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lead_control", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="leadmonitor",
            name="last_moderator_task_created_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Когда в последний раз создали задачу модератору",
            ),
        ),
        migrations.AddField(
            model_name="leadmonitor",
            name="last_moderator_task_id",
            field=models.BigIntegerField(
                blank=True,
                null=True,
                verbose_name="ID последней задачи модератору в Bitrix24",
            ),
        ),
    ]
