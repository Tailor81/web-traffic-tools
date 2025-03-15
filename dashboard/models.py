from django.db import models
from django.contrib.auth.models import User

class DashboardPreference(models.Model):
    """Store user dashboard preferences"""
    
    DASHBOARD_TYPES = (
        ('traffic', 'Traffic Overview'),
        ('geo', 'Geographic Analysis'),
        ('conversion', 'Conversion Metrics'),
        ('custom', 'Custom Dashboard'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dashboard_preferences')
    dashboard_type = models.CharField(max_length=20, choices=DASHBOARD_TYPES, default='traffic')
    settings = models.JSONField(default=dict, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}'s {self.get_dashboard_type_display()} Dashboard"
    
    class Meta:
        unique_together = ('user', 'dashboard_type')