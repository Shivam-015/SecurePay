from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import DemoPayment


@admin.register(DemoPayment)
class DemoPaymentAdmin(admin.ModelAdmin):
    list_display = ('reference', 'milestone', 'initiated_by', 'amount', 'currency', 'status', 'created_at', 'released_at')
    list_filter = ('status', 'currency', 'created_at')
    search_fields = ('reference', 'milestone__title', 'milestone__contract__title', 'initiated_by__email')
    readonly_fields = ('milestone', 'initiated_by', 'reference', 'amount', 'currency', 'status', 'created_at', 'released_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
