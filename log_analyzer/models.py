from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class ExternalDataSource(models.Model):
    """Model for external data sources like databases or APIs"""
    SOURCE_TYPES = [
        ('mysql', 'MySQL'),
        ('postgresql', 'PostgreSQL'),
        ('mssql', 'Microsoft SQL Server'),
        ('api', 'REST API'),
        ('mongodb', 'MongoDB Atlas'),  #MongoDB 
    ]
    
    name = models.CharField(max_length=100)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    host = models.CharField(max_length=255, blank=True, help_text="Database host or API base URL")
    port = models.IntegerField(null=True, blank=True)
    database = models.CharField(max_length=100, blank=True)
    username = models.CharField(max_length=100, blank=True)
    password = models.CharField(max_length=100, blank=True)
    api_url = models.URLField(blank=True)
    api_key = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return self.name

class LogFile(models.Model):
    """Model for uploaded log files"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='log_files/', null=True, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_entries = models.IntegerField(default=0)
    entries_processed = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, default='None')
    
    def __str__(self):
        return self.name
    
    def get_processing_progress(self):
        """Get processing progress as a percentage"""
        if self.total_entries == 0:
            return 0
        return int((self.entries_processed / self.total_entries) * 100)

class LogEntry(models.Model):
    """Model for individual log entries"""
    log_file = models.ForeignKey(LogFile, related_name='entries', on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    ip_address = models.GenericIPAddressField()
    http_method = models.CharField(max_length=10)
    resource = models.CharField(max_length=255)
    status_code = models.IntegerField()
    country = models.CharField(max_length=100, blank=True, default='Unknown')
    page_category = models.CharField(max_length=50, default='other')

    # Web Traffic & User Behavior Fields
    utm_source = models.CharField(max_length=100, blank=True, null=True)
    utm_campaign = models.CharField(max_length=100, blank=True, null=True)
    session_id = models.CharField(max_length=100, blank=True, null=True)
    user_id = models.CharField(max_length=100, blank=True, null=True)
    product_interest = models.CharField(max_length=255, blank=True, null=True)
    interest_level = models.IntegerField(blank=True, null=True)
    action_type = models.CharField(max_length=50, blank=True, null=True)
    converted = models.BooleanField(default=False)
    visit_duration_sec = models.IntegerField(blank=True, null=True)
    device_type = models.CharField(max_length=50, blank=True, null=True)
    returning_user = models.BooleanField(default=False)

    # Revenue & Transaction Fields
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    purchase_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    currency = models.CharField(max_length=10, default='USD')
    product_id = models.CharField(max_length=100, blank=True, null=True)
    product_name = models.CharField(max_length=255, blank=True, null=True)
    product_category = models.CharField(max_length=100, blank=True, null=True)
    quantity = models.IntegerField(blank=True, null=True)

    # Marketing Attribution Fields
    attribution_channel = models.CharField(max_length=100, blank=True, null=True)
    attribution_campaign = models.CharField(max_length=100, blank=True, null=True)
    discount_code = models.CharField(max_length=50, blank=True, null=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    # Customer Value Fields
    customer_segment = models.CharField(max_length=100, blank=True, null=True)
    customer_lifetime_value = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    repeat_purchase = models.BooleanField(default=False)
    days_since_last_purchase = models.IntegerField(blank=True, null=True)

    # Financial Analysis Fields
    cost_of_goods_sold = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    profit_margin = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    acquisition_cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    roi = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)

    def __str__(self):
        return f"{self.timestamp} - {self.ip_address} - {self.resource}"

    class Meta:
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['status_code']),
            models.Index(fields=['country']),
            models.Index(fields=['page_category']),
        ]