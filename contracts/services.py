from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from auditlog.services import agreement_fingerprint, record_event
from notifications.services import notify_contract_counterparty

from .models import Contract, Milestone, Submission


@transaction.atomic
def respond_to_proposal(*, contract_id, actor, decision, note=''):
    contract = Contract.objects.select_for_update().get(pk=contract_id)
    if contract.status != Contract.Status.PROPOSED:
        raise ValidationError('This proposal has already received a response or is no longer open.')
    if actor.pk != contract.freelancer_id or actor.role != actor.Role.FREELANCER:
        raise PermissionDenied('Only the named freelancer can respond to this proposal.')
    if decision not in (Contract.Status.ACCEPTED, Contract.Status.REJECTED):
        raise ValidationError('That response is not available.')
    contract.status = decision
    contract.decision_note = note.strip()
    contract.responded_at = timezone.now()
    contract.save(update_fields=('status', 'decision_note', 'responded_at', 'updated_at'))
    payload = {'status': contract.status}
    if decision == Contract.Status.ACCEPTED:
        payload['agreement_hash'] = agreement_fingerprint(contract)
    record_event(contract=contract, actor=actor, event_type='contract_accepted' if decision == Contract.Status.ACCEPTED else 'contract_declined', payload=payload)
    accepted = decision == Contract.Status.ACCEPTED
    notify_contract_counterparty(contract=contract, actor=actor, kind='contract_accepted' if accepted else 'contract_declined', title='Proposal accepted' if accepted else 'Proposal declined', message=f'{actor.display_name} {"accepted" if accepted else "declined"} your contract proposal.')
    return contract


@transaction.atomic
def withdraw_proposal(*, contract_id, actor, note=''):
    contract = Contract.objects.select_for_update().get(pk=contract_id)
    if contract.status != Contract.Status.PROPOSED:
        raise ValidationError('Only an unanswered proposal can be withdrawn.')
    if actor.pk != contract.client_id or actor.role != actor.Role.CLIENT:
        raise PermissionDenied('Only the client who sent this proposal can withdraw it.')
    contract.status = Contract.Status.WITHDRAWN
    contract.decision_note = note.strip()
    contract.responded_at = timezone.now()
    contract.save(update_fields=('status', 'decision_note', 'responded_at', 'updated_at'))
    record_event(contract=contract, actor=actor, event_type='contract_withdrawn', payload={'status': contract.status})
    notify_contract_counterparty(contract=contract, actor=actor, kind='contract_withdrawn', title='Proposal withdrawn', message=f'{actor.display_name} withdrew the contract proposal.')
    return contract


@transaction.atomic
def submit_milestone(*, milestone_id, actor, values):
    milestone = Milestone.objects.select_for_update().select_related('contract').get(pk=milestone_id)
    if actor.pk != milestone.contract.freelancer_id or actor.role != actor.Role.FREELANCER:
        raise PermissionDenied('Only the assigned freelancer can submit this milestone.')
    if milestone.contract.status not in (Contract.Status.ACCEPTED, Contract.Status.IN_PROGRESS):
        raise ValidationError('This contract is not active.')
    if milestone.status not in (Milestone.Status.FUNDED, Milestone.Status.REVISION_REQUESTED):
        raise ValidationError('This milestone must be demo funded before work can be submitted.')
    if not milestone.payments.filter(status='funded').exists():
        raise ValidationError('No demo funding record exists for this milestone.')
    version = (milestone.submissions.aggregate(last=Max('version'))['last'] or 0) + 1
    submission = Submission(milestone=milestone, submitted_by=actor, version=version, **values)
    submission.save()
    milestone.status = Milestone.Status.SUBMITTED
    milestone.submitted_at = timezone.now()
    milestone.review_note = ''
    milestone.save(update_fields=('status', 'submitted_at', 'review_note'))
    record_event(contract=milestone.contract, actor=actor, event_type='milestone_submitted', payload={'milestone_id': milestone.pk, 'version': version, 'kind': submission.kind})
    notify_contract_counterparty(contract=milestone.contract, actor=actor, kind='milestone_submitted', title='Milestone delivery submitted', message=f'{actor.display_name} submitted a delivery for “{milestone.title}”.')
    return submission


@transaction.atomic
def request_revision(*, milestone_id, actor, note):
    milestone = Milestone.objects.select_for_update().select_related('contract').get(pk=milestone_id)
    if actor.pk != milestone.contract.client_id or actor.role != actor.Role.CLIENT:
        raise PermissionDenied('Only the client who owns this contract can request changes.')
    if milestone.status != Milestone.Status.SUBMITTED:
        raise ValidationError('Changes can only be requested after a submission.')
    note = note.strip()
    if not note:
        raise ValidationError('Please explain what needs to change.')
    milestone.status = Milestone.Status.REVISION_REQUESTED
    milestone.review_note = note
    milestone.save(update_fields=('status', 'review_note'))
    latest = milestone.submissions.order_by('-version').first()
    if latest:
        latest.review_note = note
        latest.save(update_fields=('review_note',))
    record_event(contract=milestone.contract, actor=actor, event_type='milestone_revision_requested', payload={'milestone_id': milestone.pk})
    notify_contract_counterparty(contract=milestone.contract, actor=actor, kind='revision_requested', title='Changes requested', message=f'{actor.display_name} requested changes to “{milestone.title}”.')
    return milestone
