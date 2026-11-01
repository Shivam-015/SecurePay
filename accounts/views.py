from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from django.db.models import Exists, OuterRef, Q

from contracts.models import Contract, Milestone
from invoices.models import Invoice
from marketplace.models import Gig
from messaging.models import Message
from notifications.models import Notification
from reviews.models import Review

from .forms import EmailAuthenticationForm, SignUpForm, VerificationEmailForm
from .services import send_email_verification, verify_email_token


def home(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    return render(request, 'accounts/home.html')


class AccountLoginView(LoginView):
    authentication_form = EmailAuthenticationForm
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True


class AccountLogoutView(LogoutView):
    # Django's LogoutView accepts POST only; this prevents state changes by link/GET.
    http_method_names = ['post', 'options']


@require_http_methods(['GET', 'POST'])
def signup(request):
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        user.is_active = False
        user.save()
        form.save_m2m()
        send_email_verification(user=user, request=request)
        return redirect('accounts:verification_sent')
    return render(request, 'accounts/signup.html', {'form': form})


def verification_sent(request):
    return render(request, 'accounts/verification_sent.html')


@require_http_methods(['GET', 'POST'])
def verify_email(request, token):
    if request.method == 'GET':
        return render(request, 'accounts/verify_email.html', {'token': token})
    if verify_email_token(token):
        messages.success(request, 'Your email is verified. You can now sign in.')
        return redirect('accounts:login')
    messages.error(request, 'That verification link is invalid, expired, or already used.')
    return redirect('accounts:resend_verification')


@require_http_methods(['GET', 'POST'])
def resend_verification(request):
    form = VerificationEmailForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = User.objects.filter(email__iexact=form.cleaned_data['email'], is_active=False).first()
        if user:
            send_email_verification(user=user, request=request)
        return redirect('accounts:verification_sent')
    return render(request, 'accounts/resend_verification.html', {'form': form})


@login_required
def dashboard(request):
    user = request.user
    contracts = Contract.objects.filter(Q(client=user) | Q(freelancer=user)).select_related('client', 'freelancer', 'gig')
    is_client = user.role == user.Role.CLIENT
    active_contracts = contracts.filter(status__in=(Contract.Status.ACCEPTED, Contract.Status.IN_PROGRESS))
    pending_contracts = contracts.filter(status=Contract.Status.PROPOSED, **({'client': user} if is_client else {'freelancer': user}))
    review_exists = Review.objects.filter(contract_id=OuterRef('pk'), reviewer=user)
    review_due = contracts.filter(status=Contract.Status.COMPLETED).annotate(has_review=Exists(review_exists)).filter(has_review=False)
    if is_client:
        awaiting_milestones = Milestone.objects.filter(contract__client=user, status=Milestone.Status.SUBMITTED).count()
    else:
        awaiting_milestones = Milestone.objects.filter(contract__freelancer=user, status__in=(Milestone.Status.FUNDED, Milestone.Status.REVISION_REQUESTED)).count()
    unread_message_count = Message.objects.filter(read_at__isnull=True).exclude(sender=user).filter(
        Q(conversation__contract__client=user) | Q(conversation__contract__freelancer=user)
    ).count()
    invoice_query = Invoice.objects.filter(Q(buyer=user) | Q(seller=user)).select_related('contract')
    context = {
        'contract_count': contracts.count(),
        'active_contract_count': active_contracts.count(),
        'pending_contract_count': pending_contracts.count(),
        'completed_contract_count': contracts.filter(status=Contract.Status.COMPLETED).count(),
        'awaiting_milestone_count': awaiting_milestones,
        'unread_notifications': Notification.objects.filter(recipient=user, read_at__isnull=True).count(),
        'unread_messages': unread_message_count,
        'review_due_contracts': review_due.select_related('client', 'freelancer')[:4],
        'review_due_count': review_due.count(),
        'recent_contracts': contracts.order_by('-updated_at')[:5],
        'recent_invoices': invoice_query[:4],
        'received_reviews': Review.objects.filter(reviewee=user).select_related('reviewer', 'contract')[:4],
        'active_gig_count': Gig.objects.filter(freelancer=user, status=Gig.Status.ACTIVE).count() if not is_client else 0,
        'is_client': is_client,
    }
    return render(request, 'accounts/dashboard.html', context)
