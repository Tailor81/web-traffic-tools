from django import forms
from .models import Report, ReportTemplate
from log_analyzer.models import LogFile

class ReportForm(forms.ModelForm):
    """Form for creating a new report"""
    
    log_file = forms.ModelChoiceField(
        queryset=LogFile.objects.filter(status='completed'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = Report
        fields = ['name', 'description', 'log_file', 'report_type', 'format']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'report_type': forms.Select(attrs={'class': 'form-select'}),
            'format': forms.Select(attrs={'class': 'form-select'}),
        }
        
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter log files by the current user
        self.fields['log_file'].queryset = LogFile.objects.filter(
            uploaded_by=user, 
            status='completed'
        )

class ReportTemplateForm(forms.ModelForm):
    """Form for creating a new report template"""
    
    class Meta:
        model = ReportTemplate
        fields = ['name', 'description', 'report_type', 'is_public']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'report_type': forms.Select(attrs={'class': 'form-select'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }