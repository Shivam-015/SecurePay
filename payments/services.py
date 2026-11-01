from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from auditlog.services import record_event
from notifications.services import notify_contract_counterparty
from invoices.services import issue_demo_invoice
from fraud.services import evaluate_demo_payment
from contracts.models import Contract, Milestone

from .models import DemoPayment


@transaction.atomic
def simulate_funding(*, milestone_id, actor):
    milestone = Milestone.objects.select_for_update().select_related('contract').get(pk=milestone_id)
    contract = milestone.contract
    if actor.pk != contract.client_id or actor.role != actor.Role.CLIENT:
        raise PermissionDenied('Only the client on this contract can record demo funding.')
    if contract.status not in (Contract.Status.ACCEPTED, Contract.Status.IN_PROGRESS):
        raise ValidationError('The contract must be accepted before demo funding.')
    if milestone.status != Milestone.Status.AWAITING_FUNDING:
        raise ValidationError('This milestone is not awaiting demo funding.')
    payment = DemoPayment.objects.create(
        milestone=milestone,
        initiated_by=actor,
        amount=milestone.amount,
        currency=contract.currency,
        status=DemoPayment.Status.FUNDED,
    )
    evaluate_demo_payment(payment)
    milestone.status = Milestone.Status.FUNDED
    milestone.save(update_fields=('status',))
    if contract.status == Contract.Status.ACCEPTED:
        contract.status = Contract.Status.IN_PROGRESS
        contract.save(update_fields=('status', 'updated_at'))
    record_event(contract=contract, actor=actor, event_type='demo_funding_recorded', payload={
        'milestone_id': milestone.pk,
        'amount': str(payment.amount),
        'currency': payment.currency,
        'demo_reference': payment.reference.hex,
    })
    notify_contract_counterparty(contract=contract, actor=actor, kind='demo_funding', title='Milestone demo funded', message=f'{actor.display_name} recorded demo funding for “{milestone.title}”.')
    return payment


@transaction.atomic
def simulate_release(*, milestone_id, actor):
    milestone = Milestone.objects.select_for_update().select_related('contract').get(pk=milestone_id)
    contract = milestone.contract
    if actor.pk != contract.client_id or actor.role != actor.Role.CLIENT:
        raise PermissionDenied('Only the client on this contract can approve and release this demo payment.')
    if milestone.status != Milestone.Status.SUBMITTED:
        raise ValidationError('A submitted milestone is required before release.')
    payment = milestone.payments.select_for_update().filter(status=DemoPayment.Status.FUNDED).first()
    if not payment:
        raise ValidationError('There is no funded demo payment to release.')
    payment.status = DemoPayment.Status.RELEASED
    payment.released_at = timezone.now()
    payment.save(update_fields=('status', 'released_at'))
    milestone.status = Milestone.Status.RELEASED
    milestone.save(update_fields=('status',))
    if not contract.milestones.exclude(status=Milestone.Status.RELEASED).exists():
        contract.status = Contract.Status.COMPLETED
        contract.save(update_fields=('status', 'updated_at'))
    invoice = issue_demo_invoice(payment)
    record_event(contract=contract, actor=actor, event_type='demo_payment_released', payload={
        'milestone_id': milestone.pk,
        'amount': str(payment.amount),
        'currency': payment.currency,
        'demo_reference': payment.reference.hex,
        'contract_completed': contract.status == Contract.Status.COMPLETED,
    })
    record_event(contract=contract, actor=actor, event_type='demo_invoice_issued', payload={'invoice_number': invoice.number, 'milestone_id': milestone.pk, 'amount': str(invoice.amount), 'currency': invoice.currency})
    notify_contract_counterparty(contract=contract, actor=actor, kind='demo_payment_released', title='Milestone approved', message=f'{actor.display_name} approved and marked “{milestone.title}” released in the demo workflow.')
    return payment
