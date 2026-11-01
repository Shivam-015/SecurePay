from django.contrib import admin

from .models import RiskSignal


@admin.register(RiskSignal)
class RiskSignalAdmin(admin.ModelAdmin):
    list_display = ('rule_code', 'severity', 'score', 'contract', 'subject', 'status', 'created_at', 'reviewed_by')
    list_filter = ('severity', 'status', 'rule_code', 'created_at')
    search_fields = ('contract__title', 'subject__email', 'summary')
    readonly_fields = ('contract', 'demo_payment', 'subject', 'rule_code', 'severity', 'score', 'summary', 'status', 'created_at', 'reviewed_at', 'reviewed_by')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
