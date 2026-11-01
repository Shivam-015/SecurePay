from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from auditlog.services import agreement_fingerprint, record_event
from accounts.services import send_email_verification
from contracts.models import Contract, Milestone, Submission
from invoices.models import Invoice
from marketplace.models import Gig
from messaging.models import Conversation, Message
from notifications.models import Notification
from notifications.services import notify_contract_counterparty
from reviews.models import Review
from disputes.models import Dispute, DisputeMessage

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = User
        fields = ('id', 'email', 'display_name', 'role', 'password')
        read_only_fields = ('id',)

    def validate_password(self, value):
        try:
            validate_password(value, user=User(email=self.initial_data.get('email', ''), display_name=self.initial_data.get('display_name', '')))
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create_user(password=password, is_active=False, **validated_data)
        send_email_verification(user=user, request=self.context['request'])
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'email', 'display_name', 'role')
        read_only_fields = fields


class GigSerializer(serializers.ModelSerializer):
    freelancer_name = serializers.CharField(source='freelancer.display_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Gig
        fields = ('id', 'slug', 'title', 'description', 'starting_price', 'currency', 'delivery_days', 'status', 'freelancer', 'freelancer_name', 'category', 'category_name', 'created_at')
        read_only_fields = fields


class MilestoneReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Milestone
        fields = ('id', 'sequence', 'title', 'description', 'amount', 'due_date', 'status', 'submitted_at', 'review_note')
        read_only_fields = fields


class MilestoneInputSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=120)
    description = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    amount = serializers.DecimalField(max_digits=11, decimal_places=2, min_value=Decimal('0.01'))
    due_date = serializers.DateField()


class ContractCreateSerializer(serializers.Serializer):
    gig = serializers.PrimaryKeyRelatedField(queryset=Gig.objects.filter(status=Gig.Status.ACTIVE, category__is_active=True))
    title = serializers.CharField(max_length=120)
    scope = serializers.CharField(max_length=5000)
    terms = serializers.CharField(max_length=3000, required=False, allow_blank=True)
    milestones = MilestoneInputSerializer(many=True, min_length=1, max_length=8)

    def validate_milestones(self, milestones):
        dates = [item['due_date'] for item in milestones]
        if any(day < timezone.localdate() for day in dates):
            raise serializers.ValidationError('Milestone due dates cannot be in the past.')
        if dates != sorted(dates):
            raise serializers.ValidationError('Milestone due dates must follow the plan order.')
        total = sum((item['amount'] for item in milestones), Decimal('0.00'))
        if total > Decimal('999999999.99'):
            raise serializers.ValidationError('The milestone total is above the supported contract amount.')
        return milestones

    def validate(self, attrs):
        request = self.context['request']
        if request.user.role != User.Role.CLIENT:
            raise serializers.ValidationError('Only client accounts can propose a contract.')
        if attrs['gig'].freelancer_id == request.user.pk:
            raise serializers.ValidationError('You cannot create a contract with your own service.')
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context['request']
        gig = validated_data.pop('gig')
        milestones = validated_data.pop('milestones')
        total = sum((item['amount'] for item in milestones), Decimal('0.00'))
        contract = Contract.objects.create(
            client=request.user,
            freelancer=gig.freelancer,
            gig=gig,
            total_amount=total,
            currency=gig.currency,
            **validated_data,
        )
        for sequence, item in enumerate(milestones, start=1):
            Milestone.objects.create(contract=contract, sequence=sequence, **item)
        record_event(contract=contract, actor=request.user, event_type='contract_proposed', payload={
            'gig_id': gig.pk,
            'milestone_count': len(milestones),
            'total_amount': str(total),
            'currency': gig.currency,
            'agreement_hash': agreement_fingerprint(contract),
        })
        notify_contract_counterparty(contract=contract, actor=request.user, kind='contract_proposed', title='New contract proposal', message=f'{request.user.display_name} sent you a contract proposal.')
        return contract


class ContractSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.display_name', read_only=True)
    freelancer_name = serializers.CharField(source='freelancer.display_name', read_only=True)
    milestones = MilestoneReadSerializer(many=True, read_only=True)

    class Meta:
        model = Contract
        fields = ('id', 'gig', 'title', 'scope', 'terms', 'total_amount', 'currency', 'status', 'decision_note', 'client', 'client_name', 'freelancer', 'freelancer_name', 'milestones', 'proposed_at', 'responded_at', 'updated_at')
        read_only_fields = fields


class SubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Submission
        fields = ('id', 'version', 'kind', 'content', 'url', 'file', 'submitted_at', 'review_note')
        read_only_fields = ('id', 'version', 'submitted_at', 'review_note')


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.display_name', read_only=True)

    class Meta:
        model = Message
        fields = ('id', 'sender', 'sender_name', 'body', 'created_at', 'read_at')
        read_only_fields = ('id', 'sender', 'sender_name', 'created_at', 'read_at')

    def validate_body(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Write a message before sending.')
        return value


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ('id', 'kind', 'title', 'message', 'contract', 'created_at', 'read_at')
        read_only_fields = fields


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = ('number', 'contract', 'demo_payment', 'seller_name', 'buyer_name', 'description', 'amount', 'currency', 'issued_at', 'is_demo')
        read_only_fields = fields


class ReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source='reviewer.display_name', read_only=True)

    class Meta:
        model = Review
        fields = ('id', 'contract', 'reviewer', 'reviewer_name', 'reviewee', 'rating', 'comment', 'created_at')
        read_only_fields = ('id', 'reviewer', 'reviewer_name', 'reviewee', 'created_at')


class DisputeMessageSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.display_name', read_only=True)

    class Meta:
        model = DisputeMessage
        fields = ('id', 'author', 'author_name', 'body', 'created_at')
        read_only_fields = ('id', 'author', 'author_name', 'created_at')


class DisputeSerializer(serializers.ModelSerializer):
    messages = DisputeMessageSerializer(many=True, read_only=True)
    milestone_title = serializers.CharField(source='milestone.title', read_only=True)

    class Meta:
        model = Dispute
        fields = ('id', 'contract', 'milestone', 'milestone_title', 'opened_by', 'reason', 'description', 'status', 'outcome', 'resolution_note', 'messages', 'created_at', 'resolved_at')
        read_only_fields = ('id', 'contract', 'opened_by', 'status', 'outcome', 'resolution_note', 'messages', 'created_at', 'resolved_at')
