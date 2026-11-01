from django.contrib import admin

from .models import Contract, Milestone


class MilestoneInline(admin.TabularInline):
    model = Milestone
    extra = 0
    can_delete = False
    readonly_fields = ('sequence', 'title', 'description', 'amount', 'due_date')


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ('title', 'client', 'freelancer', 'total_amount', 'currency', 'status', 'proposed_at')
    list_filter = ('status', 'currency', 'proposed_at')
    search_fields = ('title', 'client__email', 'freelancer__email')
    readonly_fields = ('client', 'freelancer', 'gig', 'title', 'scope', 'terms', 'total_amount', 'currency', 'status', 'decision_note', 'proposed_at', 'responded_at', 'updated_at')
    inlines = (MilestoneInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
