from django.conf import settings
from django.db import models


class Conversation(models.Model):
    contract = models.OneToOneField('contracts.Contract', on_delete=models.CASCADE, related_name='conversation')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-updated_at',)

    def __str__(self):
        return f'Messages · {self.contract.title}'


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='sent_contract_messages')
    body = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('created_at', 'pk')
        indexes = [models.Index(fields=('conversation', 'created_at'), name='message_conv_created_idx')]

    def __str__(self):
        return f'Message {self.pk} · {self.conversation_id}'

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('Messages cannot be edited; send a follow-up message instead.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Messages cannot be deleted.')
