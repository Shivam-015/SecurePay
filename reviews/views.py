from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from auditlog.services import record_event
from contracts.models import Contract
from notifications.services import notify_contract_counterparty

from .forms import ReviewForm
from .models import Review


@login_required
@require_http_methods(['GET', 'POST'])
def review_contract(request, contract_id):
    contract = get_object_or_404(Contract.objects.select_related('client', 'freelancer'), pk=contract_id)
    if request.user.pk not in (contract.client_id, contract.freelancer_id):
        raise PermissionDenied
    if contract.status != Contract.Status.COMPLETED:
        messages.error(request, 'Reviews open after all milestones are marked released.')
        return redirect('contracts:contract_detail', pk=contract.pk)
    existing = Review.objects.filter(contract=contract, reviewer=request.user).first()
    if existing:
        messages.info(request, 'You have already reviewed this contract.')
        return redirect('contracts:contract_detail', pk=contract.pk)
    form = ReviewForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        reviewee = contract.freelancer if request.user.pk == contract.client_id else contract.client
        with transaction.atomic():
            review = form.save(commit=False)
            review.contract = contract
            review.reviewer = request.user
            review.reviewee = reviewee
            review.save()
            record_event(contract=contract, actor=request.user, event_type='review_submitted', payload={'review_id': review.pk, 'rating': review.rating})
            notify_contract_counterparty(contract=contract, actor=request.user, kind='review_submitted', title='A contract review was added', message=f'{request.user.display_name} left a review after completing the contract.')
        messages.success(request, 'Your review has been shared on the service profile.')
        return redirect('contracts:contract_detail', pk=contract.pk)
    return render(request, 'reviews/review_form.html', {'contract': contract, 'form': form})
