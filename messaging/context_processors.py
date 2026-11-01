from django.db.models import Q

from .models import Message


def unread_message_count(request):
    if not request.user.is_authenticated:
        return {'unread_message_count': 0}
    unread = Message.objects.filter(read_at__isnull=True).exclude(sender=request.user).filter(
        Q(conversation__contract__client=request.user) | Q(conversation__contract__freelancer=request.user)
    ).count()
    return {'unread_message_count': unread}
