from datetime import timedelta

from django.utils import timezone

from payments.models import DemoPayment

from .models import RiskSignal


def evaluate_demo_payment(payment):
    """Simple educational heuristics. Signals call for review and never block a workflow."""
    contract = payment.milestone.contract
    checks = []
    if payment.amount >= 100000:
        checks.append((
            'LARGE_DEMO_AMOUNT', RiskSignal.Severity.MEDIUM, 45,
            'The simulated milestone amount is at least 100,000 in the contract currency.',
        ))
    recent_count = DemoPayment.objects.filter(
        initiated_by=payment.initiated_by,
        created_at__gte=timezone.now() - timedelta(minutes=10),
    ).count()
    if recent_count >= 3:
        checks.append((
            'RAPID_DEMO_ACTIVITY', RiskSignal.Severity.MEDIUM, 55,
            'This account recorded three or more demo funding actions within ten minutes.',
        ))
    pair_count = DemoPayment.objects.filter(
        milestone__contract__client_id=contract.client_id,
        milestone__contract__freelancer_id=contract.freelancer_id,
        created_at__gte=timezone.now() - timedelta(hours=24),
    ).count()
    if pair_count >= 4:
        checks.append((
            'REPEATED_PAIR_ACTIVITY', RiskSignal.Severity.LOW, 30,
            'Four or more demo funding actions were recorded for this client-freelancer pair in 24 hours.',
        ))
    return [RiskSignal.objects.get_or_create(
        demo_payment=payment,
        rule_code=code,
        defaults={
            'contract': contract,
            'subject': payment.initiated_by,
            'severity': severity,
            'score': score,
            'summary': summary,
        },
    )[0] for code, severity, score, summary in checks]
