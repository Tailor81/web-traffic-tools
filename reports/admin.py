from django.contrib import admin
from .models import Report, ReportTemplate

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('name', 'report_type', 'created_by', 'created_at', 'format', 'is_scheduled')
    list_filter = ('report_type', 'format', 'is_scheduled', 'created_at')
    search_fields = ('name', 'description', 'created_by__username')

@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'report_type', 'created_by', 'created_at', 'is_public')
    list_filter = ('report_type', 'is_public', 'created_at')
    search_fields = ('name', 'description', 'created_by__username')