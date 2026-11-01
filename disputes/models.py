from django.conf import settings
from django.db import models


class Dispute(models.Model):
    class Reason(models.TextChoices):
        PAYMENT = 'payment', 'Payment or milestone amount'
        SCOPE = 'scope', 'Scope of work'
        QUALITY = 'quality', 'Quality of delivery'
        DEADLINE = 'deadline', 'Deadline'
        COMMUNICATION = 'communication', 'Communication'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        UNDER_REVIEW = 'under_review', 'Under staff review'
        RESOLVED = 'resolved', 'Resolved'
        DISMISSED = 'dismissed', 'Dismissed'

    class Outcome(models.TextChoices):
        RELEASE_DEMO = 'release_demo', 'Mark demo payment released'
        RETURN_TO_WORK = 'return_to_work', 'Return milestone to work'
        DISMISS = 'dismiss', 'Dismiss and restore previous state'

    contract = models.ForeignKey('contracts.Contract', on_delete=models.PROTECT, related_name='disputes')
    milestone = models.OneToOneField('contracts.Milestone', on_delete=models.PROTECT, related_name='dispute')
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='opened_disputes')
    reason = models.CharField(max_length=20, choices=Reason.choices)
    description = models.TextField(max_length=4000)
    previous_milestone_status = models.CharField(max_length=24)
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.OPEN)
    outcome = models.CharField(max_length=20, choices=Outcome.choices, blank=True)
    resolution_note = models.CharField(max_length=2000, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_disputes')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'Dispute · {self.contract.title} · {self.milestone.title}'


class DisputeMessage(models.Model):
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='dispute_messages')
    body = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'pk')

    def __str__(self):
        return f'Dispute update {self.pk}'
