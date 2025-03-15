from django.contrib import admin
from .models import LogFile, LogEntry

@admin.register(LogFile)
class LogFileAdmin(admin.ModelAdmin):
    list_display = ('name', 'uploaded_by', 'uploaded_at', 'status', 'total_entries')
    list_filter = ('status', 'uploaded_at')
    search_fields = ('name', 'uploaded_by__username')
    date_hierarchy = 'uploaded_at'

@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'ip_address', 'http_method', 'resource', 'status_code', 'country')
    list_filter = ('http_method', 'status_code', 'country')
    search_fields = ('ip_address', 'resource', 'country')
    date_hierarchy = 'timestamp'