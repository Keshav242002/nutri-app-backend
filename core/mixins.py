from django.db import models


class TimestampedModel(models.Model):
    """Abstract base providing created_at and updated_at on every model."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
