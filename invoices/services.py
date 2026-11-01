from .models import Invoice


def issue_demo_invoice(payment):
    contract = payment.milestone.contract
    invoice, _ = Invoice.objects.get_or_create(
        demo_payment=payment,
        defaults={
            'contract': contract,
            'seller': contract.freelancer,
            'buyer': contract.client,
            'seller_name': contract.freelancer.display_name,
            'buyer_name': contract.client.display_name,
            'description': f'{contract.title} — {payment.milestone.title}'[:240],
            'amount': payment.amount,
            'currency': payment.currency,
        },
    )
    return invoice
