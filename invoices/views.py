from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from .models import Invoice


@login_required
def invoice_list(request):
    invoices = Invoice.objects.filter(Q(buyer=request.user) | Q(seller=request.user)).select_related('contract', 'buyer', 'seller')
    return render(request, 'invoices/invoice_list.html', {'invoices': invoices})


@login_required
def invoice_detail(request, number):
    invoice = get_object_or_404(
        Invoice.objects.select_related('contract', 'buyer', 'seller', 'demo_payment__milestone'),
        number=number,
    )
    if request.user.pk not in (invoice.buyer_id, invoice.seller_id):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    return render(request, 'invoices/invoice_detail.html', {'invoice': invoice})
