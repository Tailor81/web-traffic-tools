from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.contrib import messages
from django.core.files.base import ContentFile

from .models import Report, ReportTemplate
from .forms import ReportForm, ReportTemplateForm
from .utils import generate_summary_report
from log_analyzer.models import LogFile

import os
import json
from datetime import datetime

@login_required
def report_list(request):
    """View to list all reports"""
    reports = Report.objects.filter(created_by=request.user).order_by('-created_at')
    
    context = {
        'reports': reports,
        'report_count': reports.count(),
    }
    return render(request, 'reports/report_list.html', context)

@login_required
def create_report(request):
    """View to create a new report"""
    if request.method == 'POST':
        form = ReportForm(request.user, request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.created_by = request.user
            report.save()
            
            # Generate the report file
            try:
                generate_summary_report(report)
                report.last_generated = timezone.now()
                report.save()
                messages.success(request, f'Report "{report.name}" created successfully.')
            except Exception as e:
                messages.error(request, f'Error generating report: {str(e)}')
            
            return redirect('reports:report_list')
    else:
        # Check if user has any completed log files
        has_logs = LogFile.objects.filter(uploaded_by=request.user, status='completed').exists()
        if not has_logs:
            messages.warning(request, 'You need at least one processed log file to create a report. Upload and process a log file first.')
            return redirect('log_analyzer:log_list')
            
        form = ReportForm(request.user)
    
    context = {
        'form': form,
        'report_types': Report.REPORT_TYPES,
        'format_choices': Report.FORMAT_CHOICES,
    }
    return render(request, 'reports/create_report.html', context)

@login_required
def report_detail(request, report_id):
    """View to show report details"""
    report = get_object_or_404(Report, id=report_id, created_by=request.user)
    
    context = {
        'report': report,
    }
    return render(request, 'reports/report_detail.html', context)

@login_required
def download_report(request, report_id):
    """View to download a report file"""
    report = get_object_or_404(Report, id=report_id, created_by=request.user)
    
    if not report.file:
        messages.error(request, 'Report file not found.')
        return redirect('reports:report_detail', report_id=report.id)
    
    # Get the file path
    file_path = report.file.path
    
    # Check if file exists
    if not os.path.exists(file_path):
        messages.error(request, 'Report file not found on disk.')
        return redirect('reports:report_detail', report_id=report.id)
    
    # Determine content type based on format
    if report.format == 'pdf':
        content_type = 'application/pdf'
    elif report.format == 'csv':
        content_type = 'text/csv'
    elif report.format == 'excel':
        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:
        content_type = 'application/octet-stream'
    
    # Read file
    with open(file_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
        return response

@login_required
def delete_report(request, report_id):
    """View to delete a report"""
    if request.method == 'POST':
        report = get_object_or_404(Report, id=report_id, created_by=request.user)
        report_name = report.name
        
        # Delete the file if it exists
        if report.file:
            if os.path.exists(report.file.path):
                os.remove(report.file.path)
        
        # Delete the report
        report.delete()
        
        messages.success(request, f'Report "{report_name}" deleted successfully.')
        return redirect('reports:report_list')
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=400)

@login_required
def regenerate_report(request, report_id):
    """View to regenerate a report"""
    if request.method == 'POST':
        report = get_object_or_404(Report, id=report_id, created_by=request.user)
        
        try:
            # Delete old file if it exists
            if report.file:
                if os.path.exists(report.file.path):
                    os.remove(report.file.path)
            
            # Generate new report
            generate_summary_report(report)
            report.last_generated = timezone.now()
            report.save()
            
            messages.success(request, f'Report "{report.name}" regenerated successfully.')
        except Exception as e:
            messages.error(request, f'Error regenerating report: {str(e)}')
        
        return redirect('reports:report_detail', report_id=report.id)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=400)