from django.db import models
from django.contrib.auth.models import User
import os

class LogFile(models.Model):
    """Model to store uploaded log files"""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )
    
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='logs/')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='log_files')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    processed_at = models.DateTimeField(null=True, blank=True)
    total_entries = models.IntegerField(default=0)
    entries_processed = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.name
    
    def filename(self):
        return os.path.basename(self.file.name)
    
    def get_processing_progress(self):
        if self.total_entries == 0:
            return 0
        return int((self.entries_processed / self.total_entries) * 100)

class LogEntry(models.Model):
    """Model to store parsed log entries"""
    
    log_file = models.ForeignKey(LogFile, on_delete=models.CASCADE, related_name='entries')
    timestamp = models.DateTimeField()
    ip_address = models.GenericIPAddressField()
    http_method = models.CharField(max_length=10)
    resource = models.TextField()
    status_code = models.IntegerField()
    
    # Enriched data
    country = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    page_category = models.CharField(max_length=50, null=True, blank=True)
    
    def __str__(self):
        return f"{self.timestamp} - {self.ip_address} - {self.resource}"
    
    class Meta:
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['resource']),
            models.Index(fields=['status_code']),
            models.Index(fields=['country']),
            models.Index(fields=['page_category']),
        ]