from django.contrib import admin

from .models import Invoice


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('number', 'contract', 'buyer', 'seller', 'amount', 'currency', 'issued_at', 'is_demo')
    list_filter = ('currency', 'issued_at', 'is_demo')
    search_fields = ('number', 'contract__title', 'buyer__email', 'seller__email')
    readonly_fields = ('number', 'contract', 'demo_payment', 'seller', 'buyer', 'seller_name', 'buyer_name', 'description', 'amount', 'currency', 'issued_at', 'is_demo')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
