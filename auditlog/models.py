from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    LABELS = {
        'contract_proposed': 'Contract proposal sent',
        'contract_accepted': 'Proposal accepted',
        'contract_declined': 'Proposal declined',
        'contract_withdrawn': 'Proposal withdrawn',
        'demo_funding_recorded': 'Demo funding recorded',
        'milestone_submitted': 'Milestone delivery submitted',
        'milestone_revision_requested': 'Changes requested',
        'demo_payment_released': 'Demo payment marked released',
        'message_sent': 'Contract message sent',
        'dispute_message_sent': 'Dispute update added',
        'review_submitted': 'Contract review submitted',
        'demo_invoice_issued': 'Demo invoice issued',
        'dispute_opened': 'Milestone dispute opened',
        'dispute_resolved': 'Milestone dispute resolved',
    }
    contract = models.ForeignKey('contracts.Contract', on_delete=models.PROTECT, related_name='audit_events')
    sequence = models.PositiveIntegerField()
    event_type = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_events')
    payload = models.JSONField(default=dict)
    occurred_at = models.DateTimeField()
    previous_hash = models.CharField(max_length=64, blank=True)
    event_hash = models.CharField(max_length=64, unique=True)

    class Meta:
        ordering = ('sequence',)
        constraints = [models.UniqueConstraint(fields=('contract', 'sequence'), name='audit_contract_sequence_unique')]
        indexes = [models.Index(fields=('contract', 'sequence'), name='audit_contract_sequence_idx')]

    def __str__(self):
        return f'{self.contract_id} · {self.sequence} · {self.event_type}'

    @property
    def display_label(self):
        return self.LABELS.get(self.event_type, self.event_type.replace('_', ' ').capitalize())

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('Audit events cannot be edited; append a new event instead.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Audit events cannot be deleted.')
