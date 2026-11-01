from django.contrib import admin

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    can_delete = False
    readonly_fields = ('sender', 'body', 'created_at', 'read_at')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('contract', 'created_at', 'updated_at')
    search_fields = ('contract__title', 'contract__client__email', 'contract__freelancer__email')
    readonly_fields = ('contract', 'created_at', 'updated_at')
    inlines = (MessageInline,)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
