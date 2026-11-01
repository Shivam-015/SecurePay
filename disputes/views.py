from django.contrib import messages as flash_messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from contracts.models import Milestone

from .forms import DisputeMessageForm, DisputeOpenForm, DisputeResolutionForm
from .models import Dispute
from .services import add_dispute_message, open_dispute, resolve_dispute


@login_required
@require_http_methods(['GET', 'POST'])
def create_dispute(request, milestone_id):
    milestone = get_object_or_404(Milestone.objects.select_related('contract'), pk=milestone_id)
    if request.user.pk not in (milestone.contract.client_id, milestone.contract.freelancer_id):
        raise PermissionDenied
    if request.method == 'POST':
        form = DisputeOpenForm(request.POST)
        if form.is_valid():
            try:
                dispute = open_dispute(milestone_id=milestone.pk, actor=request.user, reason=form.cleaned_data['reason'], description=form.cleaned_data['description'])
                flash_messages.success(request, 'Your dispute has been sent to the other participant and staff queue.')
                return redirect('disputes:detail', dispute_id=dispute.pk)
            except PermissionDenied:
                raise
            except ValidationError as error:
                flash_messages.error(request, error.messages[0])
    else:
        form = DisputeOpenForm()
    return render(request, 'disputes/dispute_form.html', {'milestone': milestone, 'form': form})


@login_required
def dispute_detail(request, dispute_id):
    dispute = get_object_or_404(Dispute.objects.select_related('contract__client', 'contract__freelancer', 'milestone', 'opened_by', 'reviewed_by'), pk=dispute_id)
    if request.user.pk not in (dispute.contract.client_id, dispute.contract.freelancer_id) and not request.user.is_staff:
        raise PermissionDenied
    message_form = DisputeMessageForm()
    resolution_form = DisputeResolutionForm()
    return render(request, 'disputes/dispute_detail.html', {'dispute': dispute, 'message_form': message_form, 'resolution_form': resolution_form})


@login_required
@require_http_methods(['POST'])
def dispute_message(request, dispute_id):
    dispute = get_object_or_404(Dispute, pk=dispute_id)
    form = DisputeMessageForm(request.POST)
    if form.is_valid():
        try:
            add_dispute_message(dispute_id=dispute.pk, actor=request.user, body=form.cleaned_data['body'])
        except PermissionDenied:
            raise
        except ValidationError as error:
            flash_messages.error(request, error.messages[0])
    else:
        flash_messages.error(request, 'Write an update before sending.')
    return redirect('disputes:detail', dispute_id=dispute.pk)


@staff_member_required(login_url='accounts:login')
def dispute_queue(request):
    disputes = Dispute.objects.select_related('contract', 'milestone', 'opened_by').filter(status__in=(Dispute.Status.OPEN, Dispute.Status.UNDER_REVIEW))
    return render(request, 'disputes/queue.html', {'disputes': disputes})


@staff_member_required(login_url='accounts:login')
@require_http_methods(['POST'])
def dispute_resolve(request, dispute_id):
    dispute = get_object_or_404(Dispute, pk=dispute_id)
    form = DisputeResolutionForm(request.POST)
    if form.is_valid():
        try:
            resolve_dispute(dispute_id=dispute.pk, actor=request.user, outcome=form.cleaned_data['outcome'], resolution_note=form.cleaned_data['resolution_note'])
            flash_messages.success(request, 'The dispute decision has been recorded.')
        except ValidationError as error:
            flash_messages.error(request, error.messages[0])
    else:
        flash_messages.error(request, 'Please select a valid outcome and add a staff note.')
    return redirect('disputes:detail', dispute_id=dispute.pk)
