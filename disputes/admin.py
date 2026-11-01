from django.contrib import admin

from .models import Dispute, DisputeMessage


class DisputeMessageInline(admin.TabularInline):
    model = DisputeMessage
    extra = 0
    can_delete = False
    readonly_fields = ('author', 'body', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = ('contract', 'milestone', 'opened_by', 'reason', 'status', 'created_at', 'reviewed_by')
    list_filter = ('status', 'reason', 'created_at')
    search_fields = ('contract__title', 'milestone__title', 'opened_by__email', 'description')
    readonly_fields = ('contract', 'milestone', 'opened_by', 'reason', 'description', 'previous_milestone_status', 'status', 'outcome', 'resolution_note', 'reviewed_by', 'created_at', 'updated_at', 'resolved_at')
    inlines = (DisputeMessageInline,)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
