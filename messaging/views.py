from django.contrib import messages as flash_messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from auditlog.services import record_event
from contracts.models import Contract
from notifications.services import notify_contract_counterparty

from .forms import MessageForm
from .models import Conversation, Message


@login_required
def inbox(request):
    conversations = Conversation.objects.filter(
        Q(contract__client=request.user) | Q(contract__freelancer=request.user)
    ).select_related('contract__client', 'contract__freelancer').annotate(
        last_message_at=Max('messages__created_at'),
        unread_count=Count('messages', filter=Q(messages__read_at__isnull=True) & ~Q(messages__sender=request.user)),
    ).order_by('-last_message_at', '-updated_at')
    return render(request, 'messaging/inbox.html', {'conversations': conversations})


@login_required
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def conversation_detail(request, contract_id):
    contract = get_object_or_404(
        Contract.objects.select_related('client', 'freelancer'),
        Q(pk=contract_id) & (Q(client=request.user) | Q(freelancer=request.user)),
    )
    conversation, _ = Conversation.objects.get_or_create(contract=contract)
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = request.user
            message.save()
            Conversation.objects.filter(pk=conversation.pk).update(updated_at=message.created_at)
            record_event(contract=contract, actor=request.user, event_type='message_sent', payload={'message_id': message.pk})
            notify_contract_counterparty(
                contract=contract,
                actor=request.user,
                kind='message_received',
                title='New contract message',
                message='A new message is waiting in the contract conversation.',
            )
            return redirect('messaging:conversation', contract_id=contract.pk)
    else:
        form = MessageForm()

    Message.objects.filter(
        conversation=conversation,
        read_at__isnull=True,
    ).exclude(sender=request.user).update(read_at=timezone.now())
    messages_qs = conversation.messages.select_related('sender').all()
    return render(request, 'messaging/conversation.html', {
        'contract': contract,
        'conversation': conversation,
        'conversation_messages': messages_qs,
        'form': form,
    })
