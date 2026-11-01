from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import RiskSignal


@staff_member_required(login_url='accounts:login')
def queue(request):
    signals = RiskSignal.objects.select_related('contract', 'demo_payment', 'subject', 'reviewed_by')
    return render(request, 'fraud/queue.html', {'signals': signals, 'open_count': signals.filter(status=RiskSignal.Status.OPEN).count()})


@staff_member_required(login_url='accounts:login')
@require_POST
def update_status(request, signal_id):
    signal = get_object_or_404(RiskSignal, pk=signal_id)
    action = request.POST.get('action')
    if signal.status == RiskSignal.Status.OPEN and action in (RiskSignal.Status.REVIEWED, RiskSignal.Status.DISMISSED):
        signal.status = action
        signal.reviewed_at = timezone.now()
        signal.reviewed_by = request.user
        signal.save(update_fields=('status', 'reviewed_at', 'reviewed_by'))
    return redirect('fraud:queue')
