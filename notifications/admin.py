from django.contrib import admin

from .models import Notification, ReminderDelivery


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'actor', 'contract', 'created_at', 'read_at')
    list_filter = ('kind', 'created_at', 'read_at')
    search_fields = ('recipient__email', 'actor__email', 'contract__title', 'title')
    readonly_fields = ('recipient', 'actor', 'contract', 'kind', 'title', 'message', 'created_at', 'read_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReminderDelivery)
class ReminderDeliveryAdmin(admin.ModelAdmin):
    list_display = ('milestone', 'recipient', 'reminder_type', 'target_date', 'sent_at')
    list_filter = ('reminder_type', 'target_date')
    search_fields = ('recipient__email', 'milestone__title', 'milestone__contract__title')
    readonly_fields = ('milestone', 'recipient', 'reminder_type', 'target_date', 'sent_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
