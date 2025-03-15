from django import forms
from .models import LogFile

class LogFileUploadForm(forms.ModelForm):
    class Meta:
        model = LogFile
        fields = ['file']
        widgets = {
            'file': forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv,.log,.txt'}),
        }