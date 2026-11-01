import hashlib
import hmac
import json

from django.db import transaction
from django.utils import timezone

from contracts.models import Contract

from .models import AuditEvent


def _digest(*, contract_id, sequence, event_type, actor_id, payload, occurred_at, previous_hash):
    canonical = json.dumps({
        'contract_id': contract_id,
        'sequence': sequence,
        'event_type': event_type,
        'actor_id': actor_id,
        'payload': payload,
        'occurred_at': occurred_at.isoformat(),
        'previous_hash': previous_hash,
    }, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def agreement_fingerprint_input(contract):
    """Return the canonicalizable fields bound when a proposal is created."""
    return {
        'contract_id': contract.pk,
        'client_id': contract.client_id,
        'freelancer_id': contract.freelancer_id,
        'title': contract.title,
        'scope': contract.scope,
        'terms': contract.terms,
        'total_amount': str(contract.total_amount),
        'currency': contract.currency,
        'milestones': [
            {
                'sequence': item.sequence,
                'title': item.title,
                'description': item.description,
                'amount': str(item.amount),
                'due_date': item.due_date.isoformat(),
            }
            for item in contract.milestones.order_by('sequence')
        ],
    }


def agreement_fingerprint(contract):
    """Fingerprint the agreed terms and ordered plan, excluding changing statuses."""
    canonical = json.dumps(agreement_fingerprint_input(contract), sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


@transaction.atomic
def record_event(*, contract, actor, event_type, payload=None):
    locked_contract = Contract.objects.select_for_update().get(pk=contract.pk)
    previous = locked_contract.audit_events.order_by('-sequence').first()
    sequence = previous.sequence + 1 if previous else 1
    previous_hash = previous.event_hash if previous else ''
    occurred_at = timezone.now()
    payload = payload or {}
    actor_id = actor.pk if actor and actor.is_authenticated else None
    event_hash = _digest(
        contract_id=locked_contract.pk,
        sequence=sequence,
        event_type=event_type,
        actor_id=actor_id,
        payload=payload,
        occurred_at=occurred_at,
        previous_hash=previous_hash,
    )
    return AuditEvent.objects.create(
        contract=locked_contract,
        sequence=sequence,
        event_type=event_type,
        actor_id=actor_id,
        payload=payload,
        occurred_at=occurred_at,
        previous_hash=previous_hash,
        event_hash=event_hash,
    )


def verify_contract_chain(contract_id):
    previous_hash = ''
    expected_sequence = 1
    for event in AuditEvent.objects.filter(contract_id=contract_id).order_by('sequence'):
        if event.sequence != expected_sequence or event.previous_hash != previous_hash:
            return False
        expected = _digest(
            contract_id=event.contract_id,
            sequence=event.sequence,
            event_type=event.event_type,
            actor_id=event.actor_id,
            payload=event.payload,
            occurred_at=event.occurred_at,
            previous_hash=event.previous_hash,
        )
        if not hmac.compare_digest(event.event_hash, expected):
            return False
        previous_hash = event.event_hash
        expected_sequence += 1
    return True


def build_contract_evidence(contract):
    """Build a participant-safe, portable snapshot of an agreement and its ledger."""
    events = list(contract.audit_events.select_related('actor').order_by('sequence'))
    chain_valid = bool(events) and verify_contract_chain(contract.pk)
    proposal_event = next((event for event in events if event.event_type == 'contract_proposed'), None)
    proposal_payload = proposal_event.payload if proposal_event and isinstance(proposal_event.payload, dict) else {}
    recorded_fingerprint = proposal_payload.get('agreement_hash')
    accepted_fingerprints = [
        event.payload.get('agreement_hash')
        for event in events
        if event.event_type == 'contract_accepted'
        and isinstance(event.payload, dict)
        and isinstance(event.payload.get('agreement_hash'), str)
    ]
    current_fingerprint = agreement_fingerprint(contract)
    all_fingerprints = ([recorded_fingerprint] if recorded_fingerprint else []) + accepted_fingerprints
    agreement_valid = bool(
        isinstance(recorded_fingerprint, str)
        and hmac.compare_digest(recorded_fingerprint, current_fingerprint)
        and all(hmac.compare_digest(value, recorded_fingerprint) for value in all_fingerprints)
    )
    integrity_status = (
        'no_events' if not events else
        'failed' if not chain_valid or (recorded_fingerprint and not agreement_valid) else
        'unanchored' if not recorded_fingerprint else
        'verified'
    )
    fingerprint_input = agreement_fingerprint_input(contract)
    return {
        'format': 'securepay.contract-evidence',
        'version': 1,
        'generated_at': timezone.now().isoformat(),
        'notice': (
            'College project evidence export. Payments are simulations. '
            'Hash chaining detects changes when verified; it is not a digital signature '
            'or an externally anchored record.'
        ),
        'verification_spec': {
            'algorithm': 'SHA-256',
            'canonical_json': 'UTF-8; keys sorted; separators are comma and colon without spaces; ensure_ascii=false.',
            'event_hash_fields': ['contract_id', 'sequence', 'event_type', 'actor_id', 'payload', 'occurred_at', 'previous_hash'],
            'agreement_hash_fields': list(fingerprint_input.keys()),
        },
        'integrity': {
            'status': integrity_status,
            'event_chain_valid': chain_valid,
            'agreement_fingerprint_valid': agreement_valid if recorded_fingerprint else None,
            'acceptance_matches_agreement': bool(recorded_fingerprint and accepted_fingerprints and agreement_valid),
            'agreement_fingerprint': current_fingerprint,
            'event_count': len(events),
            'last_event_hash': events[-1].event_hash if events else None,
        },
        'agreement': {
            'id': contract.pk,
            'client_id': contract.client_id,
            'freelancer_id': contract.freelancer_id,
            'title': contract.title,
            'scope': contract.scope,
            'terms': contract.terms,
            'status': contract.status,
            'client': contract.client.display_name,
            'freelancer': contract.freelancer.display_name,
            'total_amount': str(contract.total_amount),
            'currency': contract.currency,
            'proposed_at': contract.proposed_at.isoformat(),
            'responded_at': contract.responded_at.isoformat() if contract.responded_at else None,
            'milestones': [
                {
                    'sequence': item.sequence,
                    'title': item.title,
                    'description': item.description,
                    'amount': str(item.amount),
                    'due_date': item.due_date.isoformat(),
                    'status': item.status,
                }
                for item in contract.milestones.order_by('sequence')
            ],
        },
        'agreement_fingerprint_input': fingerprint_input,
        'events': [
            {
                'contract_id': event.contract_id,
                'sequence': event.sequence,
                'event_type': event.event_type,
                'actor_id': event.actor_id,
                'actor': event.actor.display_name if event.actor else None,
                'occurred_at': event.occurred_at.isoformat(),
                'payload': event.payload,
                'previous_hash': event.previous_hash,
                'event_hash': event.event_hash,
            }
            for event in events
        ],
    }
