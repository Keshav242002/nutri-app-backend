"""
Idempotent data migration: provision the notification-pruning Celery beat task.

Mirrors apps/mealplans/migrations/0003_celery_beat_schedule.py — get_or_create makes it
safe to re-run (e.g. after a db reset). The reverse deletes only the row created here.
"""

import json

from django.db import migrations


def create_beat_schedule(apps: object, schema_editor: object) -> None:
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    daily_3am, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="3",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone="UTC",
    )

    PeriodicTask.objects.get_or_create(
        name="prune-old-notifications-daily",
        defaults={
            "crontab": daily_3am,
            "task": "apps.notifications.tasks.prune_old_notifications",
            "args": json.dumps([]),
            "enabled": True,
        },
    )


def delete_beat_schedule(apps: object, schema_editor: object) -> None:
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name="prune-old-notifications-daily").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
        ("django_celery_beat", "__latest__"),
    ]

    operations = [
        migrations.RunPython(create_beat_schedule, reverse_code=delete_beat_schedule),
    ]
