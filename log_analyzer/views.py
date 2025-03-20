from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.contrib import messages

from .models import ExternalDataSource, LogFile, LogEntry
from .forms import ExternalDataSourceForm, LogFileUploadForm
from .utils import import_from_external_source, parse_log_file, enrich_log_data, generate_test_data, analyze_log_data, test_external_connection

import pandas as pd
from io import StringIO, BytesIO
import csv
import threading
import time

@login_required
def log_list(request):
    """View to list all uploaded log files"""
    logs = LogFile.objects.filter(uploaded_by=request.user).order_by('-uploaded_at')
    
    context = {
        'logs': logs,
        'form': LogFileUploadForm()
    }
    return render(request, 'log_analyzer/log_list.html', context)

@login_required
def upload_log(request):
    """View to handle log file uploads"""
    if request.method == 'POST':
        form = LogFileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            log_file = form.save(commit=False)
            log_file.uploaded_by = request.user
            log_file.name = request.FILES['file'].name
            log_file.save()
            
            messages.success(request, f'Log file "{log_file.name}" uploaded successfully.')
            
            # Start processing in background (in a real app, use Celery)
            threading.Thread(target=process_log_file, args=(log_file.id,)).start()
            
            return redirect('log_analyzer:log_list')
    else:
        form = LogFileUploadForm()
    
    return render(request, 'log_analyzer/upload_log.html', {'form': form})

@login_required
def log_detail(request, log_id):
    """View to show log file details and analysis"""
    log_file = get_object_or_404(LogFile, id=log_id, uploaded_by=request.user)
    
    # Get sample entries (limit to 100 for performance)
    entries = LogEntry.objects.filter(log_file=log_file).order_by('-timestamp')[:100]
    
    # If processing is complete, show analysis
    analysis = None
    if log_file.status == 'completed':
        # Convert entries to list of dicts for analysis
        entry_dicts = []
        for entry in LogEntry.objects.filter(log_file=log_file):
            entry_dicts.append({
                'timestamp': entry.timestamp,
                'ip_address': entry.ip_address,
                'http_method': entry.http_method,
                'resource': entry.resource,
                'status_code': entry.status_code,
                'country': entry.country,
                'page_category': entry.page_category
            })
        
        analysis = analyze_log_data(entry_dicts)
    
    context = {
        'log_file': log_file,
        'entries': entries,
        'analysis': analysis
    }
    return render(request, 'log_analyzer/log_detail.html', context)

@login_required
def generate_test_log(request):
    """Generate test log data for demonstration"""
    if request.method == 'POST':
        try:
            num_entries = int(request.POST.get('num_entries', 1000))
            num_entries = min(max(100, num_entries), 10000)  # Limit between 100 and 10000
            
            # Create a StringIO object to hold the CSV data
            csv_buffer = StringIO()
            writer = csv.writer(csv_buffer)
            
            # Write header
            writer.writerow(['timestamp', 'ip_address', 'http_method', 'resource', 'status_code', 'country', 'page_category'])
            
            # Generate and write test data
            test_data = generate_test_data(num_entries)
            for entry in test_data:
                writer.writerow([
                    entry['timestamp'],
                    entry['ip_address'],
                    entry['http_method'],
                    entry['resource'],
                    entry['status_code'],
                    entry['country'],
                    entry['page_category']
                ])
            
            # Create a response with the CSV file
            response = HttpResponse(csv_buffer.getvalue(), content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="test_log_data.csv"'
            
            return response
            
        except ValueError:
            messages.error(request, 'Invalid number of entries specified.')
            return redirect('log_analyzer:log_list')
    
    return redirect('log_analyzer:log_list')

@login_required
def check_log_status(request, log_id):
    """API endpoint to check log processing status"""
    log_file = get_object_or_404(LogFile, id=log_id, uploaded_by=request.user)
    
    return JsonResponse({
        'status': log_file.status,
        'progress': log_file.get_processing_progress(),
        'total_entries': log_file.total_entries,
        'entries_processed': log_file.entries_processed
    })

@login_required
def export_log_data(request, log_id):
    """Export log data as CSV"""
    log_file = get_object_or_404(LogFile, id=log_id, uploaded_by=request.user)
    
    # Get all entries for this log file
    entries = LogEntry.objects.filter(log_file=log_file).order_by('timestamp')
    
    # Create DataFrame
    data = []
    for entry in entries:
        data.append({
            'timestamp': entry.timestamp,
            'ip_address': entry.ip_address,
            'http_method': entry.http_method,
            'resource': entry.resource,
            'status_code': entry.status_code,
            'country': entry.country,
            'page_category': entry.page_category
        })
    
    df = pd.DataFrame(data)
    
    # Export to CSV
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    
    response = HttpResponse(csv_buffer.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{log_file.name}_processed.csv"'
    
    return response

def process_log_file(log_id):
    """Process a log file in the background
    
    In a production app, this would be a Celery task
    """
    log_file = LogFile.objects.get(id=log_id)
    
    try:
        # Update status to processing
        log_file.status = 'processing'
        log_file.save()
        
        # Open and parse the log file
        log_file.file.open('rb')
        entries = parse_log_file(log_file.file)
        log_file.file.close()
        
        # Enrich the data
        enriched_entries = enrich_log_data(entries)
        
        # Update log file with total entries
        log_file.total_entries = len(enriched_entries)
        log_file.save()
        
        # Create LogEntry objects
        for i, entry in enumerate(enriched_entries):
            LogEntry.objects.create(
                log_file=log_file,
                timestamp=entry['timestamp'],
                ip_address=entry['ip_address'],
                http_method=entry['http_method'],
                resource=entry['resource'],
                status_code=entry['status_code'],
                country=entry['country'],
                page_category=entry['page_category']
            )
            
            # Update progress every 10 entries
            if i % 10 == 0:
                log_file.entries_processed = i + 1
                log_file.save()
                
                # Simulate slower processing for demonstration
                time.sleep(0.01)
        
        # Update status to completed
        log_file.status = 'completed'
        log_file.processed_at = timezone.now()
        log_file.entries_processed = log_file.total_entries
        log_file.save()
        
    except Exception as e:
        # Update status to failed
        log_file.status = 'failed'
        log_file.error_message = str(e)
        log_file.save()
        
        



# External database connection
@login_required
def external_connections(request):
    """View to list all external data connections"""
    connections = ExternalDataSource.objects.filter(created_by=request.user)
    
    context = {
        'connections': connections,
    }
    return render(request, 'log_analyzer/external_connections.html', context)

@login_required
def add_connection(request):
    """View to add a new external data connection"""
    if request.method == 'POST':
        form = ExternalDataSourceForm(request.POST)
        if form.is_valid():
            connection = form.save(commit=False)
            connection.created_by = request.user
            connection.save()
            
            messages.success(request, f'External data source "{connection.name}" created successfully.')
            return redirect('log_analyzer:external_connections')
    else:
        form = ExternalDataSourceForm()
    
    context = {
        'form': form,
        'source_types': ExternalDataSource.SOURCE_TYPES,
    }
    return render(request, 'log_analyzer/add_connection.html', context)

@login_required
def edit_connection(request, connection_id):
    """View to edit an external data connection"""
    connection = get_object_or_404(ExternalDataSource, id=connection_id, created_by=request.user)
    
    if request.method == 'POST':
        form = ExternalDataSourceForm(request.POST, instance=connection)
        if form.is_valid():
            form.save()
            messages.success(request, f'External data source "{connection.name}" updated successfully.')
            return redirect('log_analyzer:external_connections')
    else:
        form = ExternalDataSourceForm(instance=connection)
    
    context = {
        'form': form,
        'connection': connection,
        'source_types': ExternalDataSource.SOURCE_TYPES,
    }
    return render(request, 'log_analyzer/edit_connection.html', context)

@login_required
def delete_connection(request, connection_id):
    """View to delete an external data connection"""
    if request.method == 'POST':
        connection = get_object_or_404(ExternalDataSource, id=connection_id, created_by=request.user)
        name = connection.name
        connection.delete()
        
        messages.success(request, f'External data source "{name}" deleted successfully.')
    return redirect('log_analyzer:external_connections')

@login_required
def test_connection(request, connection_id):
    """View to test an external data connection"""
    connection = get_object_or_404(ExternalDataSource, id=connection_id, created_by=request.user)
    
    try:
        result = test_external_connection(connection)
        if result['success']:
            messages.success(request, f'Successfully connected to "{connection.name}".')
            
            # Update last used timestamp
            connection.last_used = timezone.now()
            connection.save()
        else:
            messages.error(request, f'Failed to connect to "{connection.name}": {result["error"]}')
    except Exception as e:
        messages.error(request, f'Error testing connection: {str(e)}')
    
    return redirect('log_analyzer:external_connections')

@login_required
def import_from_connection(request, connection_id):
    """View to import data from an external connection"""
    connection = get_object_or_404(ExternalDataSource, id=connection_id, created_by=request.user)
    
    if request.method == 'POST':
        try:
            # Create a log file entry
            log_file = LogFile.objects.create(
                name=f"Import from {connection.name} - {timezone.now().strftime('%Y-%m-%d %H:%M')}",
                uploaded_by=request.user,
                status='processing'
            )
            
            # Start import in background
            threading.Thread(target=import_from_external_source, args=(log_file.id, connection.id)).start()
            
            messages.success(request, f'Data import from "{connection.name}" started. This may take a few moments.')
            return redirect('log_analyzer:log_detail', log_id=log_file.id)
        except Exception as e:
            messages.error(request, f'Error starting import: {str(e)}')
    
    return redirect('log_analyzer:external_connections')