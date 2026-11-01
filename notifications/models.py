from django.conf import settings
from django.db import models


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_notifications')
    contract = models.ForeignKey('contracts.Contract', on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField(max_length=40)
    title = models.CharField(max_length=120)
    message = models.CharField(max_length=240)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [models.Index(fields=('recipient', 'read_at', '-created_at'), name='notif_recipient_read_idx')]

    def __str__(self):
        return f'{self.recipient} · {self.title}'


class ReminderDelivery(models.Model):
    milestone = models.ForeignKey('contracts.Milestone', on_delete=models.CASCADE, related_name='reminder_deliveries')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='milestone_reminders')
    reminder_type = models.CharField(max_length=16)
    target_date = models.DateField()
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('milestone', 'recipient', 'reminder_type', 'target_date'), name='reminder_delivery_unique')]
