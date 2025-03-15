from django.contrib import admin
from .models import DashboardPreference

@admin.register(DashboardPreference)
class DashboardPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'dashboard_type', 'is_default', 'updated_at')
    list_filter = ('dashboard_type', 'is_default')
    search_fields = ('user__username',)
    date_hierarchy = 'updated_at'