import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


def invoice_number():
    from django.utils import timezone
    return f'DEMO-{timezone.now():%Y}-{uuid.uuid4().hex[:10].upper()}'


class Invoice(models.Model):
    number = models.CharField(max_length=24, unique=True, default=invoice_number, editable=False)
    contract = models.ForeignKey('contracts.Contract', on_delete=models.PROTECT, related_name='invoices')
    demo_payment = models.OneToOneField('payments.DemoPayment', on_delete=models.PROTECT, related_name='invoice')
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='issued_invoices')
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='received_invoices')
    seller_name = models.CharField(max_length=80)
    buyer_name = models.CharField(max_length=80)
    description = models.CharField(max_length=240)
    amount = models.DecimalField(max_digits=11, decimal_places=2, validators=[MinValueValidator(0.01)])
    currency = models.CharField(max_length=3)
    issued_at = models.DateTimeField(auto_now_add=True)
    is_demo = models.BooleanField(default=True, editable=False)

    class Meta:
        ordering = ('-issued_at',)

    def __str__(self):
        return self.number
