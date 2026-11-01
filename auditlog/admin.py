from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ('contract', 'sequence', 'event_type', 'actor', 'occurred_at', 'event_hash')
    list_filter = ('event_type', 'occurred_at')
    search_fields = ('contract__title', 'actor__email', 'event_hash')
    readonly_fields = ('contract', 'sequence', 'event_type', 'actor', 'payload', 'occurred_at', 'previous_hash', 'event_hash')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
