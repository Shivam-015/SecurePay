import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class DemoPayment(models.Model):
    """A local simulation record. It does not represent or move real money."""

    class Status(models.TextChoices):
        FUNDED = 'funded', 'Demo funded'
        RELEASED = 'released', 'Demo released'

    milestone = models.ForeignKey('contracts.Milestone', on_delete=models.PROTECT, related_name='payments')
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='demo_payments')
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    amount = models.DecimalField(max_digits=11, decimal_places=2, validators=[MinValueValidator(0.01)])
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.FUNDED)
    created_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'DEMO-{self.reference} ({self.get_status_display()})'
