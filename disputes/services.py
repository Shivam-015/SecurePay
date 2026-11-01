from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from auditlog.services import record_event
from contracts.models import Contract, Milestone
from invoices.services import issue_demo_invoice
from notifications.services import notify_contract_counterparty
from payments.models import DemoPayment

from .models import Dispute, DisputeMessage


@transaction.atomic
def open_dispute(*, milestone_id, actor, reason, description):
    milestone = Milestone.objects.select_for_update().select_related('contract').get(pk=milestone_id)
    contract = milestone.contract
    if actor.pk not in (contract.client_id, contract.freelancer_id):
        raise PermissionDenied('Only a contract participant can open a dispute.')
    if contract.status not in (Contract.Status.ACCEPTED, Contract.Status.IN_PROGRESS):
        raise ValidationError('Disputes can only be opened on an active contract.')
    allowed = (Milestone.Status.FUNDED, Milestone.Status.SUBMITTED, Milestone.Status.REVISION_REQUESTED)
    if milestone.status not in allowed:
        raise ValidationError('This milestone is not in a state that can be disputed.')
    if hasattr(milestone, 'dispute'):
        raise ValidationError('A dispute has already been opened for this milestone.')
    dispute = Dispute.objects.create(
        contract=contract,
        milestone=milestone,
        opened_by=actor,
        reason=reason,
        description=description.strip(),
        previous_milestone_status=milestone.status,
    )
    milestone.status = Milestone.Status.DISPUTED
    milestone.save(update_fields=('status',))
    record_event(contract=contract, actor=actor, event_type='dispute_opened', payload={'dispute_id': dispute.pk, 'milestone_id': milestone.pk})
    notify_contract_counterparty(contract=contract, actor=actor, kind='dispute_opened', title='A milestone dispute was opened', message=f'{actor.display_name} opened a dispute about "{milestone.title}".')
    return dispute


@transaction.atomic
def add_dispute_message(*, dispute_id, actor, body):
    dispute = Dispute.objects.select_for_update().select_related('contract', 'milestone').get(pk=dispute_id)
    if actor.pk not in (dispute.contract.client_id, dispute.contract.freelancer_id) and not actor.is_staff:
        raise PermissionDenied('Only the participants or an assigned staff reviewer can update this dispute.')
    if dispute.status in (Dispute.Status.RESOLVED, Dispute.Status.DISMISSED):
        raise ValidationError('This dispute is closed to new updates.')
    item = DisputeMessage.objects.create(dispute=dispute, author=actor, body=body.strip())
    record_event(
        contract=dispute.contract,
        actor=actor,
        event_type='dispute_message_sent',
        payload={'dispute_id': dispute.pk, 'message_id': item.pk},
    )
    if actor.pk in (dispute.contract.client_id, dispute.contract.freelancer_id):
        notify_contract_counterparty(contract=dispute.contract, actor=actor, kind='dispute_update', title='New dispute update', message='A participant added information to an open dispute.')
    return item


@transaction.atomic
def resolve_dispute(*, dispute_id, actor, outcome, resolution_note):
    dispute = Dispute.objects.select_for_update().select_related('contract', 'milestone').get(pk=dispute_id)
    if not actor.is_staff:
        raise PermissionDenied('Only staff can resolve a dispute.')
    if dispute.status not in (Dispute.Status.OPEN, Dispute.Status.UNDER_REVIEW):
        raise ValidationError('This dispute has already been closed.')
    if outcome not in Dispute.Outcome.values:
        raise ValidationError('Select a valid resolution outcome.')
    milestone = Milestone.objects.select_for_update().get(pk=dispute.milestone_id)
    contract = dispute.contract
    if outcome == Dispute.Outcome.RELEASE_DEMO:
        if dispute.previous_milestone_status != Milestone.Status.SUBMITTED:
            raise ValidationError('A demo payment can only be marked released when the dispute was opened after a delivery submission.')
        payment = milestone.payments.select_for_update().filter(status=DemoPayment.Status.FUNDED).first()
        if not payment:
            raise ValidationError('No funded demo payment is available to release.')
        payment.status = DemoPayment.Status.RELEASED
        payment.released_at = timezone.now()
        payment.save(update_fields=('status', 'released_at'))
        milestone.status = Milestone.Status.RELEASED
        issue_demo_invoice(payment)
        milestone.save(update_fields=('status',))
        if not contract.milestones.exclude(status=Milestone.Status.RELEASED).exists():
            contract.status = Contract.Status.COMPLETED
            contract.save(update_fields=('status', 'updated_at'))
    elif outcome == Dispute.Outcome.RETURN_TO_WORK:
        milestone.status = Milestone.Status.REVISION_REQUESTED if dispute.previous_milestone_status == Milestone.Status.SUBMITTED else dispute.previous_milestone_status
        milestone.review_note = resolution_note.strip()
        milestone.save(update_fields=('status', 'review_note'))
    else:
        milestone.status = dispute.previous_milestone_status
        milestone.save(update_fields=('status',))

    if outcome == Dispute.Outcome.RELEASE_DEMO:
        milestone.save(update_fields=('status',))
    dispute.outcome = outcome
    dispute.resolution_note = resolution_note.strip()
    dispute.reviewed_by = actor
    dispute.resolved_at = timezone.now()
    dispute.status = Dispute.Status.DISMISSED if outcome == Dispute.Outcome.DISMISS else Dispute.Status.RESOLVED
    dispute.save(update_fields=('outcome', 'resolution_note', 'reviewed_by', 'resolved_at', 'status', 'updated_at'))
    record_event(contract=contract, actor=actor, event_type='dispute_resolved', payload={'dispute_id': dispute.pk, 'outcome': outcome})
    notify_contract_counterparty(contract=contract, actor=None, kind='dispute_resolved', title='Dispute decision recorded', message=f'Staff recorded an outcome for the dispute about "{milestone.title}".')
    return dispute
