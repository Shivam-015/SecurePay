from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from marketplace.models import Gig
from auditlog.services import agreement_fingerprint, build_contract_evidence, record_event
from notifications.services import notify_contract_counterparty
from reviews.models import Review

from .forms import ContractProposalForm, ContractResponseForm, MilestonePlanFormSet, RevisionForm, SubmissionForm
from .models import Contract, Milestone, Submission
from .services import request_revision, respond_to_proposal, submit_milestone, withdraw_proposal


@login_required
@require_http_methods(['GET', 'POST'])
def contract_create(request, gig_slug):
    if request.user.role != request.user.Role.CLIENT:
        messages.error(request, 'Only client accounts can propose a contract.')
        return redirect('marketplace:gig_list')
    gig = get_object_or_404(
        Gig.objects.select_related('freelancer', 'category'),
        slug=gig_slug,
        status=Gig.Status.ACTIVE,
        category__is_active=True,
    )
    if gig.freelancer_id == request.user.pk:
        messages.error(request, 'You cannot create a contract with your own service listing.')
        return redirect('marketplace:gig_detail', slug=gig.slug)

    initial = {'title': gig.title}
    contract_form = ContractProposalForm(request.POST or None, initial=initial)
    formset = MilestonePlanFormSet(request.POST or None, instance=Contract())
    if request.method == 'POST' and contract_form.is_valid() and formset.is_valid():
        total = sum(
            (form.cleaned_data['amount'] for form in formset.forms if form.cleaned_data and not form.cleaned_data.get('DELETE', False)),
            Decimal('0.00'),
        )
        with transaction.atomic():
            contract = contract_form.save(commit=False)
            contract.client = request.user
            contract.freelancer = gig.freelancer
            contract.gig = gig
            contract.total_amount = total
            contract.currency = gig.currency
            contract.save()
            formset.instance = contract
            formset.save()
            record_event(contract=contract, actor=request.user, event_type='contract_proposed', payload={
                'gig_id': gig.pk,
                'milestone_count': formset.total_form_count(),
                'total_amount': str(total),
                'currency': contract.currency,
                'agreement_hash': agreement_fingerprint(contract),
            })
            notify_contract_counterparty(contract=contract, actor=request.user, kind='contract_proposed', title='New contract proposal', message=f'{request.user.display_name} sent you a contract proposal.')
        messages.success(request, 'Your proposal has been sent to the freelancer.')
        return redirect('contracts:contract_detail', pk=contract.pk)

    return render(request, 'contracts/contract_form.html', {
        'gig': gig,
        'contract_form': contract_form,
        'milestone_formset': formset,
    })


@login_required
def contract_list(request):
    contracts = Contract.objects.filter(
        Q(client=request.user) | Q(freelancer=request.user)
    ).select_related('client', 'freelancer', 'gig').prefetch_related('milestones')
    return render(request, 'contracts/contract_list.html', {'contracts': contracts})


@login_required
def contract_detail(request, pk):
    contract = get_object_or_404(
        Contract.objects.select_related('client', 'freelancer', 'gig').prefetch_related('milestones__submissions', 'milestones__payments', 'milestones__dispute'),
        Q(pk=pk) & (Q(client=request.user) | Q(freelancer=request.user)),
    )
    for milestone in contract.milestones.all():
        milestone.latest_demo_payment = milestone.payments.all()[0] if milestone.payments.all() else None
        try:
            milestone.dispute_record = milestone.dispute
        except Milestone.dispute.RelatedObjectDoesNotExist:
            milestone.dispute_record = None
    response_form = ContractResponseForm()
    return render(request, 'contracts/contract_detail.html', {
        'contract': contract,
        'response_form': response_form,
        'revision_form': RevisionForm(),
        'audit_events': contract.audit_events.select_related('actor').all(),
        'contract_evidence': build_contract_evidence(contract),
        'has_reviewed': Review.objects.filter(contract=contract, reviewer=request.user).exists(),
    })


@login_required
def contract_evidence_export(request, pk):
    contract = get_object_or_404(
        Contract.objects.filter(Q(client=request.user) | Q(freelancer=request.user)),
        pk=pk,
    )
    response = JsonResponse(build_contract_evidence(contract), json_dumps_params={'indent': 2})
    response['Content-Disposition'] = f'attachment; filename="securepay-contract-{contract.pk}-evidence.json"'
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
@require_POST
def contract_action(request, pk, action):
    if action not in ('accept', 'reject', 'withdraw'):
        raise PermissionDenied('That action is not available.')
    contract = get_object_or_404(
        Contract.objects.filter(Q(client=request.user) | Q(freelancer=request.user)),
        pk=pk,
    )
    form = ContractResponseForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Please check your response note and try again.')
        return redirect('contracts:contract_detail', pk=contract.pk)
    try:
        if action == 'withdraw':
            withdraw_proposal(contract_id=contract.pk, actor=request.user, note=form.cleaned_data['note'])
            messages.success(request, 'Your proposal has been withdrawn.')
        else:
            decision = Contract.Status.ACCEPTED if action == 'accept' else Contract.Status.REJECTED
            respond_to_proposal(
                contract_id=contract.pk,
                actor=request.user,
                decision=decision,
                note=form.cleaned_data['note'],
            )
            messages.success(request, 'Your response has been recorded.')
    except PermissionDenied:
        raise
    except ValidationError as error:
        messages.error(request, error.messages[0])
    return redirect('contracts:contract_detail', pk=contract.pk)


@login_required
@require_http_methods(['GET', 'POST'])
def milestone_submit(request, milestone_id):
    milestone = get_object_or_404(Milestone.objects.select_related('contract'), pk=milestone_id)
    if request.user.pk not in (milestone.contract.client_id, milestone.contract.freelancer_id):
        raise PermissionDenied
    form = SubmissionForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        values = {key: form.cleaned_data[key] for key in ('kind', 'content', 'url', 'file')}
        try:
            submit_milestone(milestone_id=milestone.pk, actor=request.user, values=values)
            messages.success(request, 'Your milestone delivery has been submitted to the client.')
            return redirect('contracts:contract_detail', pk=milestone.contract_id)
        except PermissionDenied:
            raise
        except ValidationError as error:
            messages.error(request, error.messages[0])
    return render(request, 'contracts/submission_form.html', {'milestone': milestone, 'form': form})


@login_required
@require_POST
def milestone_revision(request, milestone_id):
    milestone = get_object_or_404(Milestone.objects.select_related('contract'), pk=milestone_id)
    form = RevisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Please add a note explaining the requested changes.')
        return redirect('contracts:contract_detail', pk=milestone.contract_id)
    try:
        request_revision(milestone_id=milestone.pk, actor=request.user, note=form.cleaned_data['note'])
        messages.success(request, 'Revision request sent to the freelancer.')
    except PermissionDenied:
        raise
    except ValidationError as error:
        messages.error(request, error.messages[0])
    return redirect('contracts:contract_detail', pk=milestone.contract_id)


@login_required
def submission_download(request, submission_id):
    submission = get_object_or_404(
        Submission.objects.select_related('milestone__contract'),
        pk=submission_id,
        milestone__contract__in=Contract.objects.filter(Q(client=request.user) | Q(freelancer=request.user)),
    )
    if not submission.file:
        raise Http404
    try:
        response = FileResponse(submission.file.open('rb'), as_attachment=True, filename=submission.file.name.rsplit('/', 1)[-1])
    except OSError as exc:
        raise Http404 from exc
    response['X-Content-Type-Options'] = 'nosniff'
    return response
