from django import forms
from .models import ExternalDataSource, LogFile

class LogFileUploadForm(forms.ModelForm):
    class Meta:
        model = LogFile
        fields = ['file']
        widgets = {
            'file': forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv,.log,.txt'}),
        }
        
        
#External database connection

class ExternalDataSourceForm(forms.ModelForm):
    """Form for creating/editing an external data source"""
    
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=False)
    api_key = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=False)
    
    class Meta:
        model = ExternalDataSource
        fields = ['name', 'source_type', 'host', 'port', 'database', 'username', 'password', 'api_url', 'api_key']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'source_type': forms.Select(attrs={'class': 'form-select'}),
            'host': forms.TextInput(attrs={'class': 'form-control'}),
            'port': forms.NumberInput(attrs={'class': 'form-control'}),
            'database': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'api_url': forms.URLInput(attrs={'class': 'form-control'}),
        }