"""Notification template registry.

One entry per category. `title` and `body` are `str.format` templates rendered with
the `context` dict passed to `dispatch()`. `route` is the client deep-link target stored
in `Notification.data`. Adding a notification type is a one-entry data change here.
"""

from __future__ import annotations

from typing import TypedDict

from apps.notifications.models import (
    CATEGORY_DAILY_TARGET,
    CATEGORY_GOAL_UPDATED,
    CATEGORY_PLAN_READY,
    CATEGORY_STREAK,
)


class NotificationTemplate(TypedDict):
    title: str
    body: str
    route: str


TEMPLATES: dict[str, NotificationTemplate] = {
    CATEGORY_DAILY_TARGET: {
        "title": "Target hit! 🎯",
        "body": "You met your calorie and protein goals today. Great work!",
        "route": "tracker/today",
    },
    CATEGORY_GOAL_UPDATED: {
        "title": "New targets ready",
        "body": "Your daily target is now {target_calories} kcal.",
        "route": "profile",
    },
    CATEGORY_PLAN_READY: {
        "title": "Today's meal plan is ready 🍽️",
        "body": "Your personalized plan for {plan_date} is waiting.",
        "route": "mealplan/today",
    },
    CATEGORY_STREAK: {
        "title": "{streak_days}-day streak! 🔥",
        "body": "You've logged all your meals {streak_days} days in a row. Keep it going!",
        "route": "tracker/today",
    },
}


def render(category: str, context: dict[str, object]) -> tuple[str, str, str]:
    """Return (title, body, route) for a category rendered with context."""
    template = TEMPLATES[category]
    title = template["title"].format(**context)
    body = template["body"].format(**context)
    return title, body, template["route"]
