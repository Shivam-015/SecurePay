from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from auditlog.services import build_contract_evidence, record_event
from accounts.models import User as AccountUser
from accounts.services import send_email_verification, verify_email_token
from contracts.forms import SubmissionForm
from contracts.models import Contract, Milestone
from contracts.services import respond_to_proposal, submit_milestone, withdraw_proposal, request_revision
from disputes.models import Dispute
from disputes.services import add_dispute_message, open_dispute, resolve_dispute
from invoices.models import Invoice
from marketplace.models import Gig
from messaging.models import Conversation, Message
from notifications.models import Notification
from notifications.services import notify_contract_counterparty
from payments.services import simulate_funding, simulate_release
from reviews.models import Review

from .serializers import (
    ContractCreateSerializer, ContractSerializer, DisputeMessageSerializer,
    DisputeSerializer, GigSerializer, InvoiceSerializer, MessageSerializer,
    NotificationSerializer, RegisterSerializer, ReviewSerializer,
    SubmissionSerializer, UserSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = (permissions.AllowAny,)


@api_view(('POST',))
@permission_classes((permissions.AllowAny,))
def verify_email_api(request):
    token = request.data.get('token', '')
    if not isinstance(token, str) or not token or len(token) > 1000:
        raise ValidationError({'token': 'A valid verification token is required.'})
    if not verify_email_token(token):
        raise ValidationError({'token': 'This link is invalid, expired, or already used.'})
    return Response({'verified': True})


@api_view(('POST',))
@permission_classes((permissions.AllowAny,))
def resend_email_verification_api(request):
    email = request.data.get('email', '')
    if not isinstance(email, str) or len(email) > 254:
        raise ValidationError({'email': 'Enter a valid email address.'})
    user = AccountUser.objects.filter(email__iexact=email.strip(), is_active=False).first()
    if user:
        send_email_verification(user=user, request=request)
    return Response({'detail': 'If verification is needed for that account, a link has been sent.'})


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class GigViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = GigSerializer
    permission_classes = (permissions.AllowAny,)
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = Gig.objects.filter(status=Gig.Status.ACTIVE, category__is_active=True).select_related('freelancer', 'category')
        category = self.request.query_params.get('category')
        search = self.request.query_params.get('search')
        if category:
            queryset = queryset.filter(category__slug=category)
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(description__icontains=search) | Q(freelancer__display_name__icontains=search))
        return queryset


class ContractListCreateView(generics.ListCreateAPIView):
    def get_queryset(self):
        return Contract.objects.filter(Q(client=self.request.user) | Q(freelancer=self.request.user)).select_related('client', 'freelancer', 'gig').prefetch_related('milestones')

    def get_serializer_class(self):
        return ContractCreateSerializer if self.request.method == 'POST' else ContractSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contract = serializer.save()
        return Response(ContractSerializer(contract, context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED)


class ContractDetailView(generics.RetrieveAPIView):
    serializer_class = ContractSerializer

    def get_queryset(self):
        return Contract.objects.filter(Q(client=self.request.user) | Q(freelancer=self.request.user)).select_related('client', 'freelancer', 'gig').prefetch_related('milestones')


class ContractEvidenceView(generics.RetrieveAPIView):
    """Participant-only portable agreement snapshot with a verified event chain."""

    def get_queryset(self):
        return Contract.objects.filter(Q(client=self.request.user) | Q(freelancer=self.request.user)).select_related('client', 'freelancer')

    def retrieve(self, request, *args, **kwargs):
        contract = self.get_object()
        return Response(build_contract_evidence(contract))


@api_view(('POST',))
def contract_action(request, contract_id):
    contract = get_object_or_404(Contract.objects.filter(Q(client=request.user) | Q(freelancer=request.user)), pk=contract_id)
    action_name = request.data.get('action')
    note = str(request.data.get('note', ''))[:500]
    if action_name == 'withdraw':
        withdraw_proposal(contract_id=contract.pk, actor=request.user, note=note)
    elif action_name in ('accept', 'decline'):
        decision = Contract.Status.ACCEPTED if action_name == 'accept' else Contract.Status.REJECTED
        respond_to_proposal(contract_id=contract.pk, actor=request.user, decision=decision, note=note)
    else:
        raise ValidationError({'action': 'Use accept, decline, or withdraw.'})
    contract.refresh_from_db()
    return Response(ContractSerializer(contract).data)


@api_view(('POST',))
def milestone_fund(request, milestone_id):
    milestone = get_object_or_404(Milestone.objects.filter(Q(contract__client=request.user) | Q(contract__freelancer=request.user)), pk=milestone_id)
    payment = simulate_funding(milestone_id=milestone.pk, actor=request.user)
    return Response({'reference': str(payment.reference), 'amount': payment.amount, 'currency': payment.currency, 'status': payment.get_status_display(), 'demo_only': True}, status=status.HTTP_201_CREATED)


@api_view(('POST',))
def milestone_release(request, milestone_id):
    milestone = get_object_or_404(Milestone.objects.filter(Q(contract__client=request.user) | Q(contract__freelancer=request.user)), pk=milestone_id)
    payment = simulate_release(milestone_id=milestone.pk, actor=request.user)
    return Response({'reference': str(payment.reference), 'status': payment.get_status_display(), 'demo_only': True})


@api_view(('POST',))
@parser_classes((JSONParser, FormParser, MultiPartParser))
def milestone_submit(request, milestone_id):
    milestone = get_object_or_404(Milestone.objects.filter(Q(contract__client=request.user) | Q(contract__freelancer=request.user)), pk=milestone_id)
    form = SubmissionForm(request.data, request.FILES or None)
    if not form.is_valid():
        raise ValidationError(form.errors)
    values = {key: form.cleaned_data[key] for key in ('kind', 'content', 'url', 'file')}
    submission = submit_milestone(milestone_id=milestone.pk, actor=request.user, values=values)
    return Response(SubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)


@api_view(('POST',))
def milestone_revision(request, milestone_id):
    milestone = get_object_or_404(Milestone.objects.filter(Q(contract__client=request.user) | Q(contract__freelancer=request.user)), pk=milestone_id)
    note = str(request.data.get('note', '')).strip()
    if not note or len(note) > 1000:
        raise ValidationError({'note': 'Provide a note of 1 to 1000 characters.'})
    updated = request_revision(milestone_id=milestone.pk, actor=request.user, note=note)
    return Response({'milestone_id': updated.pk, 'status': updated.get_status_display()})


class ContractMessagesView(generics.ListCreateAPIView):
    serializer_class = MessageSerializer

    def get_conversation(self):
        contract = get_object_or_404(Contract.objects.filter(Q(client=self.request.user) | Q(freelancer=self.request.user)), pk=self.kwargs['contract_id'])
        self.contract = contract
        self.conversation, _ = Conversation.objects.get_or_create(contract=contract)
        return self.conversation

    def get_queryset(self):
        conversation = self.get_conversation()
        Message.objects.filter(conversation=conversation, read_at__isnull=True).exclude(sender=self.request.user).update(read_at=timezone.now())
        return conversation.messages.select_related('sender').all()

    def perform_create(self, serializer):
        conversation = self.get_conversation()
        with transaction.atomic():
            message = serializer.save(conversation=conversation, sender=self.request.user)
            Conversation.objects.filter(pk=conversation.pk).update(updated_at=message.created_at)
            record_event(contract=self.contract, actor=self.request.user, event_type='message_sent', payload={'message_id': message.pk})
            notify_contract_counterparty(contract=self.contract, actor=self.request.user, kind='message_received', title='New contract message', message='A new message is waiting in the contract conversation.')


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        queryset = Notification.objects.filter(recipient=self.request.user).select_related('contract')
        if self.request.query_params.get('unread') in ('true', '1'):
            queryset = queryset.filter(read_at__isnull=True)
        return queryset


@api_view(('POST',))
def notification_mark_read(request, notification_id):
    notification = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=('read_at',))
    return Response(NotificationSerializer(notification).data)


class InvoiceListView(generics.ListAPIView):
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        return Invoice.objects.filter(Q(buyer=self.request.user) | Q(seller=self.request.user)).select_related('contract')


class DisputeListCreateView(generics.ListCreateAPIView):
    serializer_class = DisputeSerializer

    def get_queryset(self):
        return Dispute.objects.filter(Q(contract__client=self.request.user) | Q(contract__freelancer=self.request.user)).select_related('contract', 'milestone').prefetch_related('messages')

    def create(self, request, *args, **kwargs):
        milestone_id = request.data.get('milestone_id')
        reason = request.data.get('reason')
        description = str(request.data.get('description', '')).strip()
        if not milestone_id or not reason or not description or len(description) > 4000:
            raise ValidationError({'detail': 'milestone_id, reason, and a description of 1 to 4000 characters are required.'})
        dispute = open_dispute(milestone_id=milestone_id, actor=request.user, reason=reason, description=description)
        return Response(DisputeSerializer(dispute).data, status=status.HTTP_201_CREATED)


class DisputeDetailView(generics.RetrieveAPIView):
    serializer_class = DisputeSerializer

    def get_queryset(self):
        queryset = Dispute.objects.select_related('contract', 'milestone', 'opened_by').prefetch_related('messages__author')
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(Q(contract__client=self.request.user) | Q(contract__freelancer=self.request.user))


@api_view(('POST',))
def dispute_add_message(request, dispute_id):
    disputes = Dispute.objects.all() if request.user.is_staff else Dispute.objects.filter(
        Q(contract__client=request.user) | Q(contract__freelancer=request.user)
    )
    get_object_or_404(disputes, pk=dispute_id)
    body = str(request.data.get('body', '')).strip()
    if not body or len(body) > 4000:
        raise ValidationError({'body': 'Provide a message of 1 to 4000 characters.'})
    item = add_dispute_message(dispute_id=dispute_id, actor=request.user, body=body)
    return Response(DisputeMessageSerializer(item).data, status=status.HTTP_201_CREATED)


@api_view(('POST',))
@permission_classes((permissions.IsAdminUser,))
def dispute_resolve_api(request, dispute_id):
    get_object_or_404(Dispute, pk=dispute_id)
    outcome = request.data.get('outcome')
    note = str(request.data.get('resolution_note', '')).strip()
    if not note or len(note) > 2000:
        raise ValidationError({'resolution_note': 'Provide a staff note of 1 to 2000 characters.'})
    dispute = resolve_dispute(dispute_id=dispute_id, actor=request.user, outcome=outcome, resolution_note=note)
    return Response(DisputeSerializer(dispute).data)


@api_view(('POST',))
def review_create(request):
    contract_id = request.data.get('contract')
    contract = get_object_or_404(Contract.objects.select_related('client', 'freelancer'), pk=contract_id)
    if request.user.pk not in (contract.client_id, contract.freelancer_id):
        raise PermissionDenied
    if contract.status != Contract.Status.COMPLETED:
        raise ValidationError({'contract': 'Reviews are available after the contract is completed.'})
    if Review.objects.filter(contract=contract, reviewer=request.user).exists():
        raise ValidationError({'contract': 'You have already reviewed this contract.'})
    try:
        rating = int(request.data.get('rating'))
    except (TypeError, ValueError) as error:
        raise ValidationError({'rating': 'Choose a rating from 1 to 5.'}) from error
    if rating not in range(1, 6):
        raise ValidationError({'rating': 'Choose a rating from 1 to 5.'})
    reviewee = contract.freelancer if request.user.pk == contract.client_id else contract.client
    with transaction.atomic():
        review = Review.objects.create(contract=contract, reviewer=request.user, reviewee=reviewee, rating=rating, comment=str(request.data.get('comment', '')).strip()[:2000])
        record_event(contract=contract, actor=request.user, event_type='review_submitted', payload={'review_id': review.pk, 'rating': rating})
        notify_contract_counterparty(contract=contract, actor=request.user, kind='review_submitted', title='A contract review was added', message=f'{request.user.display_name} left a review after completing the contract.')
    return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)
