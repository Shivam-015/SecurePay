from django.shortcuts import render

# Create your views here.
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from contracts.models import Contract, Milestone

from .services import simulate_funding, simulate_release


@login_required
@require_POST
def fund_milestone(request, milestone_id):
    milestone = get_object_or_404(Milestone.objects.select_related('contract'), pk=milestone_id)
    try:
        payment = simulate_funding(milestone_id=milestone.pk, actor=request.user)
        messages.success(request, f'Demo funding recorded. Reference: DEMO-{payment.reference.hex[:12].upper()}. No money was charged.')
    except PermissionDenied:
        raise
    except ValidationError as error:
        messages.error(request, error.messages[0])
    return redirect('contracts:contract_detail', pk=milestone.contract_id)


@login_required
@require_POST
def release_milestone(request, milestone_id):
    milestone = get_object_or_404(Milestone.objects.select_related('contract'), pk=milestone_id)
    try:
        simulate_release(milestone_id=milestone.pk, actor=request.user)
        messages.success(request, 'Demo payment marked released. This is a project simulation; no money moved.')
    except PermissionDenied:
        raise
    except ValidationError as error:
        messages.error(request, error.messages[0])
    return redirect('contracts:contract_detail', pk=milestone.contract_id)
