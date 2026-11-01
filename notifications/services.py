from .models import Notification


def notify_contract_counterparty(*, contract, actor, kind, title, message):
    """Send an in-app alert to the other contract participant; never include secret or payment data."""
    recipients = [contract.client, contract.freelancer]
    if actor:
        recipients = [user for user in recipients if user.pk != actor.pk]
    return [Notification.objects.create(
        recipient=recipient,
        actor=actor,
        contract=contract,
        kind=kind,
        title=title,
        message=message,
    ) for recipient in recipients]
