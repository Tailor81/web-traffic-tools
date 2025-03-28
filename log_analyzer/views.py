from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.contrib import messages

from .models import ExternalDataSource, LogFile, LogEntry
from .forms import ExternalDataSourceForm, LogFileUploadForm
from .utils import (
    import_from_external_source, parse_log_file, enrich_log_data, generate_test_data, 
    analyze_log_data, test_external_connection, sync_mongodb_data_realtime, stop_mongodb_sync, running_syncs
)




import pandas as pd
from io import StringIO, BytesIO
import csv
import threading
import time
from urllib.parse import quote_plus
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import random
from datetime import datetime, timedelta
import logging
import json

# Set up logging
logger = logging.getLogger(__name__)

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
    
    # Check if there are any active syncs
    active_syncs = {}
    if 'sync_connections' in request.session:
        active_syncs = request.session['sync_connections']
    
    context = {
        'connections': connections,
        'active_syncs': active_syncs
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

# MongoDB Test Data Generator
def generate_log_entries(num_entries=1000):
    """Generate realistic log entries for web traffic analysis"""
    now = datetime.now()
    
    # Define possible values for various fields
    methods = ['GET', 'POST', 'PUT', 'DELETE']
    status_codes = [200, 200, 200, 200, 301, 302, 304, 400, 401, 403, 404, 500]  # Weighted towards 200
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
    ]
    ip_ranges = [
        "192.168.1.", "10.0.0.", "172.16.0.", 
        "203.0.113.", "198.51.100.", "192.0.2.",  # TEST-NET ranges
        "8.8.8.", "1.1.1.", "9.9.9."  # Public DNS servers (for realism)
    ]
    urls = [
        "/", "/index.html", "/about.html", "/contact.html", "/products/", 
        "/services.html", "/blog/", "/blog/post1.html", "/blog/post2.html",
        "/api/data", "/api/users", "/api/auth", 
        "/static/css/main.css", "/static/js/app.js", "/static/images/logo.png",
        "/login", "/logout", "/register", "/account", "/cart", "/checkout"
    ]
    countries = [
        "United States", "United Kingdom", "Canada", "Germany", "France", 
        "Australia", "Japan", "Brazil", "India", "China", "Russia", "South Africa"
    ]
    referers = [
        "", "",  # Empty referers for direct traffic
        "https://www.google.com/", "https://www.bing.com/", "https://www.yahoo.com/",
        "https://www.facebook.com/", "https://twitter.com/", "https://www.linkedin.com/",
        "https://www.instagram.com/", "https://www.reddit.com/"
    ]
    
    entries = []
    
    # Generate entries
    for _ in range(num_entries):
        # Random time in the past 30 days
        timestamp = now - timedelta(
            days=random.randint(0, 30),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59)
        )
        
        # Generate IP with appropriate format
        ip = f"{random.choice(ip_ranges)}{random.randint(1, 254)}"
        
        # Get URL and categorize it
        url = random.choice(urls)
        if "/static/" in url:
            category = "static"
        elif "/api/" in url:
            category = "api"
        elif url in ["/", "/index.html"]:
            category = "home"
        elif "/blog/" in url:
            category = "blog"
        elif url in ["/login", "/logout", "/register", "/account"]:
            category = "account"
        elif url in ["/cart", "/checkout"]:
            category = "ecommerce"
        elif url in ["/about.html", "/contact.html"]:
            category = "info"
        else:
            category = "other"
        
        # Generate a realistic session ID
        session_id = ''.join(random.choices('0123456789abcdef', k=32))
        
        # Create the log entry
        entry = {
            "timestamp": timestamp,
            "ip_address": ip,
            "http_method": random.choice(methods),
            "resource": url,
            "status_code": random.choice(status_codes),
            "country": random.choice(countries),
            "page_category": category,
            "user_agent": random.choice(user_agents),
            "referer": random.choice(referers),
            "session_id": session_id,
            "response_time_ms": random.randint(50, 2000),
            "bytes_sent": random.randint(500, 150000)
        }
        
        # Add some random parameters to some requests
        if random.random() < 0.3:  # 30% of requests have parameters
            entry["query_params"] = {
                "utm_source": random.choice(["google", "facebook", "twitter", "email", "direct"]),
                "utm_medium": random.choice(["cpc", "social", "email", "organic"]),
                "utm_campaign": f"campaign_{random.randint(1, 5)}"
            }
        
        entries.append(entry)
    
    # Sort by timestamp
    entries.sort(key=lambda x: x["timestamp"])
    
    return entries

def generate_mongodb_test_data(connection_info, num_entries=1000):
    """
    Generate test data and upload it to MongoDB
    
    Args:
        connection_info: Dictionary with MongoDB connection info
        num_entries: Number of log entries to generate
    
    Returns:
        Dict with status info
    """
    try:
        # Generate test data
        entries = generate_log_entries(num_entries)
        
        # Connect to MongoDB - make sure username and password are properly escaped
        from urllib.parse import quote_plus
        
        # Properly escape username and password for the URI
        username = quote_plus(connection_info['username'])
        password = quote_plus(connection_info['password'])
        
        uri = f"mongodb+srv://{username}:{password}@{connection_info['host']}/{connection_info['database']}"
        client = MongoClient(uri, server_api=ServerApi('1'))
        
        # Get database and collection
        db = client[connection_info['database']]
        collection = db['logs']
        
        # Delete existing data if requested
        if connection_info.get('clear_existing', False):
            collection.delete_many({})
            logger.info(f"Cleared existing data from {connection_info['database']}.logs")
        
        # Insert the generated data
        result = collection.insert_many(entries)
        
        client.close()
        
        return {
            'success': True, 
            'message': f"Successfully inserted {len(result.inserted_ids)} documents",
            'sample': entries[0] if entries else None
        }
        
    except Exception as e:
        logger.error(f"Error generating MongoDB test data: {str(e)}")
        return {'success': False, 'error': str(e)}

@login_required
def generate_mongodb_data(request):
    """View to generate and upload test data to MongoDB"""
    if request.method == 'POST':
        try:
            # Get parameters from the form
            num_entries = int(request.POST.get('num_entries', 1000))
            host = request.POST.get('host', 'cluster0.pww30.mongodb.net')
            username = request.POST.get('username', 'aobakwempatane67')
            password = request.POST.get('password', 'Tecboy@1122')
            database = request.POST.get('database', 'Logs_Database')
            clear_existing = request.POST.get('clear_existing') == 'on'
            
            # Validate input
            if num_entries < 1:
                num_entries = 1000
            elif num_entries > 10000:
                num_entries = 10000  # Limit to 10,000 entries
            
            # Connection info
            connection_info = {
                'host': host,
                'username': username,
                'password': password,
                'database': database,
                'clear_existing': clear_existing
            }
            
            # Generate and upload data
            result = generate_mongodb_test_data(connection_info, num_entries)
            
            if result['success']:
                messages.success(request, f"{result['message']}")
                return redirect('log_analyzer:mongodb_data_status')
            else:
                messages.error(request, f"Error generating data: {result.get('error', 'Unknown error')}")
        
        except Exception as e:
            messages.error(request, f"Error processing request: {str(e)}")
    
    # Display the form
    return render(request, 'log_analyzer/generate_mongodb_data.html')

@login_required
def mongodb_data_status(request):
    """View to display status after generating MongoDB data"""
    return render(request, 'log_analyzer/mongodb_data_status.html')



@login_required
def test_mongodb_connection(request):
    """Comprehensive MongoDB connection test with detailed error reporting"""
    if request.method == 'POST':
        try:
            # Gather connection parameters
            host = request.POST.get('host', 'cluster0.pww30.mongodb.net')
            username = request.POST.get('username', 'aobakwempatane67')
            password = request.POST.get('password', 'Tecboy@1122')
            database = request.POST.get('database', 'Logs_Database')
            
            # URL encode credentials
            username_encoded = quote_plus(username)
            password_encoded = quote_plus(password)
            
            # Construct full connection URI with additional parameters
            uri = f"mongodb+srv://{username_encoded}:{password_encoded}@{host}/{database}?retryWrites=true&w=majority"
            
            # Create SSL context
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # Verbose connection attempt
            print(f"Attempting connection with URI: {uri}")
            
            # Create MongoDB client with extensive timeout and SSL options
            client = MongoClient(
                uri, 
                server_api=ServerApi('1'),
                ssl_context=ssl_context,
                connectTimeoutMS=30000,   # 30 second connection timeout
                socketTimeoutMS=30000,    # 30 second socket timeout
                serverSelectionTimeoutMS=30000  # 30 second server selection timeout
            )
            
            # Perform connection test
            result = client.admin.command('ping')
            print("MongoDB Ping Result:", result)
            
            # List available databases (for debugging)
            print("Available Databases:", client.list_database_names())
            
            client.close()
            
            messages.success(request, "✅ Successfully connected to MongoDB!")
            return redirect('log_analyzer:mongodb_data_status')
        
        except Exception as e:
            # Comprehensive error logging
            error_details = {
                'error_type': type(e).__name__,
                'error_message': str(e),
                'traceback': traceback.format_exc()
            }
            
            # Log full error details
            print("MongoDB Connection Error:")
            print(f"Type: {error_details['error_type']}")
            print(f"Message: {error_details['error_message']}")
            print("Full Traceback:")
            print(error_details['traceback'])
            
            messages.error(request, f"❌ Connection Error: {str(e)}")
    
    return render(request, 'log_analyzer/test_mongodb_connection.html')


@login_required
def start_realtime_sync(request, connection_id):
    """Start real-time sync"""
    connection = get_object_or_404(ExternalDataSource, id=connection_id, created_by=request.user)

    if running_syncs.get(connection_id, False):
        messages.warning(request, f"Sync already running for {connection.name}")
    else:
        result = sync_mongodb_data_realtime(connection_id)
        messages.success(request, f"Started real-time sync for {connection.name}")

    return redirect('log_analyzer:external_connections')


@login_required
def stop_realtime_sync(request, connection_id):
    """Stop real-time sync"""
    result = stop_mongodb_sync(connection_id)
    if result['success']:
        messages.success(request, result['message'])
    else:
        messages.warning(request, result['message'])

    return redirect('log_analyzer:external_connections')




@login_required
def sync_status(request, connection_id):
    """Check the current status of a sync for a specific connection."""
    status = check_sync_status(connection_id)
    return JsonResponse(status)
    """Stops real-time sync for a given connection"""
    if connection_id in running_syncs:
        stop_mongodb_sync(connection_id)
        messages.success(request, "Real-time sync stopped.")
    else:
        messages.warning(request, "No active sync found.")
    
    return redirect('log_analyzer:external_connections')

    """Stop real-time synchronization with MongoDB"""
    connection = get_object_or_404(ExternalDataSource, id=connection_id, created_by=request.user)
    
    if request.method == 'POST':
        try:
            # Check if sync is running for this connection
            if hasattr(request.session, 'sync_connections') and str(connection_id) in request.session.get('sync_connections', {}):
                # Get log file ID
                log_file_id = request.session['sync_connections'][str(connection_id)]['log_file_id']
                log_file = LogFile.objects.get(id=log_file_id)
                
                # Mark sync as completed
                log_file.status = 'completed'
                log_file.save()
                
                # Remove from session
                del request.session['sync_connections'][str(connection_id)]
                request.session.modified = True
                
                messages.success(request, f"Real-time sync stopped for {connection.name}")
                return redirect('log_analyzer:log_detail', log_id=log_file_id)
            else:
                messages.warning(request, f"No active sync found for {connection.name}")
        except Exception as e:
            messages.error(request, f"Error stopping sync: {str(e)}")
    
    return redirect('log_analyzer:external_connections')