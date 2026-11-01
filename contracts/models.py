from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models


class Contract(models.Model):
    class Status(models.TextChoices):
        PROPOSED = 'proposed', 'Awaiting freelancer response'
        ACCEPTED = 'accepted', 'Accepted'
        IN_PROGRESS = 'in_progress', 'In progress'
        COMPLETED = 'completed', 'Completed'
        REJECTED = 'rejected', 'Declined'
        WITHDRAWN = 'withdrawn', 'Withdrawn'

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='client_contracts',
        limit_choices_to={'role': 'client'},
    )
    freelancer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='freelancer_contracts',
        limit_choices_to={'role': 'freelancer'},
    )
    gig = models.ForeignKey(
        'marketplace.Gig',
        on_delete=models.SET_NULL,
        related_name='contracts',
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=120)
    scope = models.TextField(max_length=5000)
    terms = models.TextField(max_length=3000, blank=True)
    total_amount = models.DecimalField(
        max_digits=11,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    currency = models.CharField(
        max_length=3,
        default='INR',
        validators=[RegexValidator(r'^[A-Z]{3}$', 'Use a three-letter uppercase currency code.')],
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PROPOSED)
    decision_note = models.CharField(max_length=500, blank=True)
    proposed_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-proposed_at',)
        indexes = [
            models.Index(fields=('client', 'status'), name='contract_client_status_idx'),
            models.Index(fields=('freelancer', 'status'), name='contract_freelancer_status_idx'),
        ]
        constraints = [
            models.CheckConstraint(condition=~models.Q(client=models.F('freelancer')), name='contract_parties_differ'),
            models.CheckConstraint(condition=models.Q(total_amount__gt=0), name='contract_total_positive'),
        ]

    def __str__(self):
        return f'{self.title} ({self.get_status_display()})'


class Milestone(models.Model):
    """Agreed milestone plan attached to a contract proposal."""

    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='milestones')
    sequence = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=120)
    description = models.TextField(max_length=2000, blank=True)
    amount = models.DecimalField(
        max_digits=11,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    due_date = models.DateField()
    class Status(models.TextChoices):
        AWAITING_FUNDING = 'awaiting_funding', 'Awaiting demo funding'
        FUNDED = 'funded', 'Demo funded'
        SUBMITTED = 'submitted', 'Work submitted'
        REVISION_REQUESTED = 'revision_requested', 'Changes requested'
        DISPUTED = 'disputed', 'In dispute'
        RELEASED = 'released', 'Demo payment released'

    status = models.CharField(max_length=24, choices=Status.choices, default=Status.AWAITING_FUNDING)
    submitted_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=1000, blank=True)

    class Meta:
        ordering = ('sequence',)
        constraints = [
            models.UniqueConstraint(fields=('contract', 'sequence'), name='contract_milestone_sequence_unique'),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='milestone_amount_positive'),
        ]

    def __str__(self):
        return f'{self.contract.title} — {self.sequence}. {self.title}'


def submission_upload_to(instance, filename):
    from pathlib import Path
    from uuid import uuid4
    return f'private_submissions/{uuid4().hex}{Path(filename).suffix.lower()}'


class Submission(models.Model):
    class Kind(models.TextChoices):
        TEXT = 'text', 'Written update'
        LINK = 'link', 'External link'
        FILE = 'file', 'File'

    milestone = models.ForeignKey(Milestone, on_delete=models.CASCADE, related_name='submissions')
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='milestone_submissions')
    version = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=8, choices=Kind.choices)
    content = models.TextField(max_length=5000, blank=True)
    url = models.URLField(max_length=1000, blank=True)
    file = models.FileField(upload_to=submission_upload_to, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    review_note = models.CharField(max_length=1000, blank=True)

    class Meta:
        ordering = ('-version',)
        constraints = [models.UniqueConstraint(fields=('milestone', 'version'), name='submission_milestone_version_unique')]

    def __str__(self):
        return f'{self.milestone} — submission {self.version}'
