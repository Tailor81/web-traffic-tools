from django.db import models
from django.contrib.auth.models import User
from log_analyzer.models import LogFile

class Report(models.Model):
    """Model to store generated reports"""
    
    REPORT_TYPES = (
        ('summary', 'Summary Report'),
        ('detailed', 'Detailed Analysis'),
        ('geographic', 'Geographic Report'),
        ('performance', 'Performance Report'),
        ('custom', 'Custom Report'),
    )
    
    FORMAT_CHOICES = (
        ('pdf', 'PDF'),
        ('csv', 'CSV'),
        ('excel', 'Excel'),
    )
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports')
    created_at = models.DateTimeField(auto_now_add=True)
    log_file = models.ForeignKey(LogFile, on_delete=models.CASCADE, related_name='reports')
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)
    format = models.CharField(max_length=20, choices=FORMAT_CHOICES)
    parameters = models.JSONField(default=dict, blank=True)
    file = models.FileField(upload_to='reports/', null=True, blank=True)
    is_scheduled = models.BooleanField(default=False)
    schedule_frequency = models.CharField(max_length=50, blank=True, null=True)
    last_generated = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at']

class ReportTemplate(models.Model):
    """Model to store report templates"""
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='report_templates')
    created_at = models.DateTimeField(auto_now_add=True)
    report_type = models.CharField(max_length=50, choices=Report.REPORT_TYPES)
    template_data = models.JSONField(default=dict)
    is_public = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at']