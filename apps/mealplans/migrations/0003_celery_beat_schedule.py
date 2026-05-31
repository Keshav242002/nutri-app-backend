"""
Idempotent data migration: provision the three Celery beat PeriodicTask rows.

Using get_or_create ensures this is safe to re-run (e.g., after a db reset +
re-migration). The reverse migration deletes only the rows created here.
"""

import json

from django.db import migrations


def create_beat_schedule(apps: object, schema_editor: object) -> None:
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    hourly, _ = IntervalSchedule.objects.get_or_create(
        every=60,
        period="minutes",
    )

    daily_2am, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="2",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone="UTC",
    )

    PeriodicTask.objects.get_or_create(
        name="generate-plans-today-hourly",
        defaults={
            "interval": hourly,
            "task": "apps.mealplans.tasks.generate_plans_for_all_users",
            "args": json.dumps(["today"]),
            "enabled": True,
        },
    )

    PeriodicTask.objects.get_or_create(
        name="generate-plans-tomorrow-hourly",
        defaults={
            "interval": hourly,
            "task": "apps.mealplans.tasks.generate_plans_for_all_users",
            "args": json.dumps(["tomorrow"]),
            "enabled": True,
        },
    )

    PeriodicTask.objects.get_or_create(
        name="recompute-summaries-daily",
        defaults={
            "crontab": daily_2am,
            "task": "apps.tracker.tasks.recompute_yesterday_summaries",
            "args": json.dumps([]),
            "enabled": True,
        },
    )


def delete_beat_schedule(apps: object, schema_editor: object) -> None:
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(
        name__in=[
            "generate-plans-today-hourly",
            "generate-plans-tomorrow-hourly",
            "recompute-summaries-daily",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("mealplans", "0002_grocerylist"),
        ("django_celery_beat", "__latest__"),
    ]

    operations = [
        migrations.RunPython(create_beat_schedule, reverse_code=delete_beat_schedule),
    ]
