from django.conf import settings
from django.db import models


class RiskSignal(models.Model):
    class Severity(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'

    class Status(models.TextChoices):
        OPEN = 'open', 'Needs review'
        REVIEWED = 'reviewed', 'Reviewed'
        DISMISSED = 'dismissed', 'Dismissed'

    contract = models.ForeignKey('contracts.Contract', on_delete=models.PROTECT, related_name='risk_signals')
    demo_payment = models.ForeignKey('payments.DemoPayment', on_delete=models.PROTECT, related_name='risk_signals')
    subject = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='risk_signals')
    rule_code = models.CharField(max_length=48)
    severity = models.CharField(max_length=8, choices=Severity.choices)
    score = models.PositiveSmallIntegerField()
    summary = models.CharField(max_length=240)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_risk_signals')

    class Meta:
        ordering = ('status', '-created_at')
        constraints = [models.UniqueConstraint(fields=('demo_payment', 'rule_code'), name='risk_payment_rule_unique')]
        indexes = [models.Index(fields=('status', 'severity', '-created_at'), name='risk_status_severity_idx')]

    def __str__(self):
        return f'{self.get_severity_display()} · {self.rule_code} · {self.contract.title}'

    @property
    def display_rule(self):
        return {
            'LARGE_DEMO_AMOUNT': 'Large simulated milestone amount',
            'RAPID_DEMO_ACTIVITY': 'Rapid simulated funding activity',
            'REPEATED_PAIR_ACTIVITY': 'Repeated activity between a participant pair',
        }.get(self.rule_code, self.rule_code.replace('_', ' ').capitalize())
