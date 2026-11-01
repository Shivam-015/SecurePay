from django.contrib import admin

from .models import Category, Gig


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('name',)


@admin.register(Gig)
class GigAdmin(admin.ModelAdmin):
    list_display = ('title', 'freelancer', 'category', 'starting_price', 'currency', 'status', 'created_at')
    list_filter = ('status', 'category', 'currency')
    search_fields = ('title', 'description', 'freelancer__email', 'freelancer__display_name')
    readonly_fields = ('slug', 'created_at', 'updated_at')
    list_select_related = ('freelancer', 'category')
