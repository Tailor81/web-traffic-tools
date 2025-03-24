import csv
import re
from datetime import datetime, timezone, timedelta
from io import StringIO
import pandas as pd
import numpy as np
import random
import time
import logging
from urllib.parse import quote_plus
# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_log_line(line):
    """Parse a single line of IIS log format"""
    try:
        # Match IIS log format: time IP method resource status
        pattern = r'(\d{2}:\d{2}:\d{2}) (\d+\.\d+\.\d+\.\d+) ([A-Z]+) (/[^\s]+) (\d+)'
        match = re.match(pattern, line)
        
        if match:
            time, ip, method, resource, status = match.groups()
            
            # Create timestamp (assuming current date)
            now = datetime.now()
            timestamp = datetime.combine(now.date(), datetime.strptime(time, '%H:%M:%S').time())
            
            return {
                'timestamp': timestamp,
                'ip_address': ip,
                'http_method': method,
                'resource': resource,
                'status_code': int(status)
            }
        else:
            logger.debug(f"Line did not match pattern: {line[:100]}")
            return None
    except Exception as e:
        logger.error(f"Error parsing log line: {e} - Line: {line[:100]}")
        return None

def parse_log_file(file_object):
    """Parse an IIS log file or CSV file and return a list of log entries"""
    try:
        # Get file content
        if hasattr(file_object, 'seek') and hasattr(file_object, 'read'):
            # File-like object
            file_object.seek(0)  # Reset position to beginning of file
            content = file_object.read().decode('utf-8')
        else:
            # String content
            content = file_object
        
        logger.info(f"File content sample: {content[:200]}")
        
        # Check if it's a CSV file (contains commas or has csv extension)
        if ',' in content.split('\n')[0] or (hasattr(file_object, 'name') and file_object.name.lower().endswith('.csv')):
            logger.info("Parsing as CSV file")
            return parse_csv_file(content)  # Fixed from recursive call
        else:
            logger.info("Parsing as IIS log file")
            return parse_iis_log(content)
    except Exception as e:
        logger.error(f"Error parsing log file: {e}")
        return []

def parse_iis_log(content):
    """Parse IIS log format"""
    lines = content.strip().split('\n')
    logger.info(f"Found {len(lines)} lines in IIS log")
    
    entries = []
    for i, line in enumerate(lines):
        if i < 5:  # Log a few sample lines for debugging
            logger.debug(f"Line {i}: {line[:100]}")
        
        # Skip comments and empty lines
        if line.startswith('#') or not line.strip():
            continue
            
        entry = parse_log_line(line)
        if entry:
            entries.append(entry)
    
    logger.info(f"Successfully parsed {len(entries)} entries from IIS log")
    return entries

def parse_csv_file(content):
    """Parse a CSV file with log data"""
    entries = []
    try:
        # Try using pandas for robust CSV parsing
        df = pd.read_csv(StringIO(content))
        logger.info(f"CSV columns: {df.columns.tolist()}")
        
        # Map common column names
        col_map = {
            'timestamp': ['timestamp', 'time', 'date', 'datetime'],
            'ip_address': ['ip_address', 'ip', 'client_ip', 'client'],
            'http_method': ['http_method', 'method', 'request_method'],
            'resource': ['resource', 'url', 'path', 'request'],
            'status_code': ['status_code', 'status', 'response_code', 'code']
        }
        
        # Try to find the actual column names in the CSV
        column_mapping = {}
        for target, possible_names in col_map.items():
            for name in possible_names:
                if name in df.columns:
                    column_mapping[target] = name
                    break
        
        logger.info(f"Column mapping: {column_mapping}")
        
        # Check if we have the minimum required columns
        required_cols = ['timestamp', 'ip_address', 'http_method', 'resource', 'status_code']
        missing_cols = [col for col in required_cols if col not in column_mapping]
        
        if missing_cols:
            logger.warning(f"Missing required columns: {missing_cols}")
            # If we're missing the timestamp, try to use the first date-like column
            if 'timestamp' in missing_cols:
                date_cols = df.select_dtypes(include=['datetime']).columns
                if not date_cols.empty:
                    column_mapping['timestamp'] = date_cols[0]
                    missing_cols.remove('timestamp')
            
            # For any still missing columns, try to guess based on data types or create defaults
            if missing_cols:
                logger.warning("Attempting to infer missing columns")
                for col in missing_cols:
                    if col == 'status_code' and df.select_dtypes(include=['number']).columns.any():
                        # Use the first numeric column for status_code
                        numeric_cols = df.select_dtypes(include=['number']).columns
                        column_mapping['status_code'] = numeric_cols[0]
                    else:
                        # For other columns, we'll use default values later
                        pass
        
        # Process each row
        row_count = len(df)
        logger.info(f"Processing {row_count} rows from CSV")
        
        for i, row in df.iterrows():
            try:
                entry = {}
                
                # Get values from mapped columns or use defaults
                for target in required_cols:
                    if target in column_mapping and column_mapping[target] in row:
                        value = row[column_mapping[target]]
                        
                        # Special handling for timestamp
                        if target == 'timestamp':
                            if pd.isna(value):
                                value = datetime.now()
                            elif isinstance(value, str):
                                try:
                                    value = pd.to_datetime(value)
                                except:
                                    value = datetime.now()
                        
                        # Special handling for status_code
                        if target == 'status_code':
                            try:
                                value = int(value)
                            except:
                                value = 200  # Default to 200 OK
                        
                        entry[target] = value
                    else:
                        # Use defaults for missing columns
                        if target == 'timestamp':
                            entry[target] = datetime.now()
                        elif target == 'ip_address':
                            entry[target] = f"192.168.1.{random.randint(1, 255)}"
                        elif target == 'http_method':
                            entry[target] = 'GET'
                        elif target == 'resource':
                            entry[target] = '/index.html'
                        elif target == 'status_code':
                            entry[target] = 200
                
                entries.append(entry)
                
                if i < 5 or i % 1000 == 0:  # Log a few samples and periodic progress
                    logger.debug(f"Processed row {i}: {entry}")
                
            except Exception as e:
                logger.error(f"Error processing row {i}: {e}")
                continue
        
        logger.info(f"Successfully extracted {len(entries)} entries from CSV")
        return entries
        
    except Exception as e:
        logger.error(f"Error parsing CSV with pandas: {e}")
        
        # Fallback to csv module
        logger.info("Falling back to csv module")
        try:
            reader = csv.DictReader(StringIO(content))
            
            for i, row in enumerate(reader):
                try:
                    # Handle different possible column names
                    timestamp = row.get('timestamp') or row.get('time') or row.get('date')
                    ip = row.get('ip_address') or row.get('ip') or row.get('client_ip')
                    method = row.get('http_method') or row.get('method') or row.get('request_method')
                    resource = row.get('resource') or row.get('url') or row.get('path')
                    status = row.get('status_code') or row.get('status') or row.get('response_code')
                    
                    # Set defaults for missing values
                    if not timestamp:
                        timestamp = datetime.now()
                    if not ip:
                        ip = f"192.168.1.{random.randint(1, 255)}"
                    if not method:
                        method = 'GET'
                    if not resource:
                        resource = '/index.html'
                    if not status:
                        status = 200
                    
                    # Convert timestamp if it's a string
                    if isinstance(timestamp, str):
                        try:
                            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        except:
                            try:
                                timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                            except:
                                timestamp = datetime.now()
                    
                    entry = {
                        'timestamp': timestamp,
                        'ip_address': ip,
                        'http_method': method,
                        'resource': resource,
                        'status_code': int(status) if isinstance(status, (int, str)) and str(status).isdigit() else 200
                    }
                    entries.append(entry)
                    
                except Exception as row_error:
                    logger.error(f"Error parsing CSV row {i}: {row_error}")
                    continue
            
            logger.info(f"Successfully parsed {len(entries)} entries using csv module")
            return entries
            
        except Exception as csv_error:
            logger.error(f"Error with csv fallback: {csv_error}")
            return []

def enrich_log_data(entries):
    """Add geographical and categorical data to log entries"""
    logger.info(f"Enriching {len(entries)} log entries with geo and category data")
    
    countries = ['United States', 'United Kingdom', 'Canada', 'Germany', 
                'France', 'Australia', 'Japan', 'Brazil', 'India', 'China']
    
    page_categories = {
        'index.html': 'home',
        'event.php': 'events',
        'scheduledemo.php': 'demo',
        'prototype.php': 'product',
        'virtual-assistant.php': 'product',
        'contact.php': 'contact',
        'about.html': 'about',
        'images/': 'static',
        'css/': 'static',
        'js/': 'static',
        'api/': 'api'
    }
    
    for entry in entries:
        # Add random country (in a real app, this would use IP geolocation)
        entry['country'] = random.choice(countries)
        
        # Categorize pages
        resource = entry.get('resource', '').lower()
        category = 'other'
        
        for pattern, cat in page_categories.items():
            if pattern in resource:
                category = cat
                break
        
        entry['page_category'] = category
    
    return entries

def generate_test_data(num_entries=1000):
    """Generate sample log data for testing"""
    logger.info(f"Generating {num_entries} test log entries")
    
    methods = ['GET', 'POST', 'PUT', 'DELETE']
    resources = [
        '/index.html',
        '/images/logo.png',
        '/event.php',
        '/scheduledemo.php',
        '/prototype.php',
        '/virtual-assistant.php',
        '/about.html',
        '/contact.php',
        '/api/data',
        '/css/style.css',
        '/js/main.js'
    ]
    statuses = [200, 200, 200, 200, 200, 301, 302, 404, 500]  # Weighted toward 200
    ip_ranges = [
        '192.168.1.',
        '10.0.0.',
        '172.16.0.',
        '157.20.0.',
        '128.1.0.'
    ]
    
    entries = []
    now = datetime.now()
    
    # Create entries directly rather than going through log parsing
    for _ in range(num_entries):
        # Generate random time in the past 7 days
        random_days = random.uniform(0, 7)
        random_seconds = random.randint(0, 86399)  # seconds in a day
        timestamp = now - pd.Timedelta(days=random_days) + pd.Timedelta(seconds=random_seconds)
        
        ip = f"{random.choice(ip_ranges)}{random.randint(1, 255)}"
        method = random.choice(methods)
        resource = random.choice(resources)
        status = random.choice(statuses)
        
        entry = {
            'timestamp': timestamp,
            'ip_address': ip,
            'http_method': method,
            'resource': resource,
            'status_code': status
        }
        entries.append(entry)
    
    # Sort by timestamp
    entries.sort(key=lambda x: x['timestamp'])
    
    # Enrich with geographical and categorical data
    return enrich_log_data(entries)

def analyze_log_data(entries):
    """Perform basic analysis on log entries"""
    logger.info(f"Analyzing {len(entries)} log entries")
    
    try:
        df = pd.DataFrame(entries)
        
        # Initialize result dictionary with default values
        result = {
            'total_entries': len(entries),
            'by_category': {},
            'by_country': {},
            'by_status': {
                200: 0,  # Success
                301: 0,  # Permanent redirect
                302: 0,  # Temporary redirect
                404: 0,  # Not found
                500: 0   # Server error
            },
            'by_method': {},
            'by_hour': {},
            'by_day': {}
        }
        
        # Count requests by page category (if exists)
        if 'page_category' in df.columns:
            result['by_category'] = df['page_category'].value_counts().to_dict()
        
        # Count requests by country (if exists)
        if 'country' in df.columns:
            result['by_country'] = df['country'].value_counts().to_dict()
        
        # Count requests by status code
        if 'status_code' in df.columns:
            status_counts = df['status_code'].value_counts().to_dict()
            # Update pre-initialized dictionary with actual counts
            result['by_status'].update(status_counts)
        
        # Count requests by HTTP method
        if 'http_method' in df.columns:
            result['by_method'] = df['http_method'].value_counts().to_dict()
        
        # Count by hour of day (for traffic patterns)
        if 'timestamp' in df.columns:
            df['hour'] = df['timestamp'].dt.hour
            result['by_hour'] = df['hour'].value_counts().sort_index().to_dict()
            
            # Count by day of week
            df['day'] = df['timestamp'].dt.day_name()
            result['by_day'] = df['day'].value_counts().to_dict()
        
        logger.info(f"Analysis complete: {len(result['by_category'])} categories, {len(result['by_country'])} countries")
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing log data: {e}")
        # Return a minimal result to avoid breaking the UI
        return {
            'total_entries': len(entries),
            'by_category': {},
            'by_country': {},
            'by_status': {200: 0, 301: 0, 302: 0, 404: 0, 500: 0},
            'by_method': {},
            'by_hour': {},
            'by_day': {}
        }

def test_external_connection(connection):
    """Test connection to an external data source"""
    source_type = connection.source_type
    
    try:
        if source_type == 'mysql':
            import mysql.connector
            
            conn = mysql.connector.connect(
                host=connection.host,
                port=connection.port,
                database=connection.database,
                user=connection.username,
                password=connection.password
            )
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            conn.close()
            
            return {'success': True}
            
        elif source_type == 'postgresql':
            import psycopg2
            
            conn = psycopg2.connect(
                host=connection.host,
                port=connection.port,
                dbname=connection.database,
                user=connection.username,
                password=connection.password
            )
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            conn.close()
            
            return {'success': True}
            
        elif source_type == 'mssql':
            import pyodbc
            
            conn_str = (
                f"DRIVER={{SQL Server}};"
                f"SERVER={connection.host},{connection.port};"
                f"DATABASE={connection.database};"
                f"UID={connection.username};"
                f"PWD={connection.password}"
            )
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            conn.close()
            
            return {'success': True}
            
        elif source_type == 'api':
            import requests
            
            headers = {}
            if connection.api_key:
                headers['Authorization'] = f"Bearer {connection.api_key}"
            
            response = requests.get(connection.api_url, headers=headers)
            response.raise_for_status()
            
            return {'success': True}
            
        elif source_type == 'mongodb':
            from pymongo.mongo_client import MongoClient
            from pymongo.server_api import ServerApi
            
            # Construct the connection URI with properly escaped username and password
            if connection.host.startswith('mongodb+'):
                # Full connection string provided
                uri = connection.host
                # Replace password placeholder if needed
                if '<db_password>' in uri:
                    uri = uri.replace('<db_password>', quote_plus(connection.password))
            else:
                # Construct from parts with escaped username and password
                uri = f"mongodb+srv://{quote_plus(connection.username)}:{quote_plus(connection.password)}@{connection.host}/{connection.database}"
            
            # Create a client with Server API version 1
            client = MongoClient(uri, server_api=ServerApi('1'))
            
            # Test connection with ping
            client.admin.command('ping')
            client.close()
            
            return {'success': True}
            
        else:
            return {'success': False, 'error': f"Unsupported source type: {source_type}"}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

def import_from_external_source(log_file_id, connection_id):
    """Import data from an external source and create log entries"""
    from .models import LogFile, LogEntry, ExternalDataSource
    
    log_file = LogFile.objects.get(id=log_file_id)
    connection = ExternalDataSource.objects.get(id=connection_id)
    
    try:
        entries = []
        
        if connection.source_type == 'mysql':
            import mysql.connector
            
            conn = mysql.connector.connect(
                host=connection.host,
                port=connection.port,
                database=connection.database,
                user=connection.username,
                password=connection.password
            )
            cursor = conn.cursor(dictionary=True)
            
            # This query needs to match your specific database schema
            cursor.execute("""
                SELECT 
                    timestamp, ip_address, http_method, resource, status_code
                FROM 
                    logs
                ORDER BY 
                    timestamp DESC
                LIMIT 1000
            """)
            
            for row in cursor:
                entries.append(row)
                
            cursor.close()
            conn.close()
            
        elif connection.source_type == 'postgresql':
            import psycopg2
            import psycopg2.extras
            
            conn = psycopg2.connect(
                host=connection.host,
                port=connection.port,
                dbname=connection.database,
                user=connection.username,
                password=connection.password
            )
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            
            # This query needs to match your specific database schema
            cursor.execute("""
                SELECT 
                    timestamp, ip_address, http_method, resource, status_code
                FROM 
                    logs
                ORDER BY 
                    timestamp DESC
                LIMIT 1000
            """)
            
            for row in cursor:
                entries.append(dict(row))
                
            cursor.close()
            conn.close()
            
        elif connection.source_type == 'api':
            import requests
            
            headers = {}
            if connection.api_key:
                headers['Authorization'] = f"Bearer {connection.api_key}"
            
            response = requests.get(connection.api_url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            
            # API response format will vary, adjust this as needed
            if isinstance(data, list):
                entries = data
            elif isinstance(data, dict) and 'data' in data:
                entries = data['data']
            else:
                raise ValueError("Unexpected API response format")
                
        elif connection.source_type == 'mongodb':
            from pymongo.mongo_client import MongoClient
            from pymongo.server_api import ServerApi
            
            # Construct the connection URI with proper URL encoding
            if connection.host.startswith('mongodb+'):
                # Full connection string provided
                uri = connection.host
                # Replace password placeholder if needed
                if '<db_password>' in uri:
                    uri = uri.replace('<db_password>', quote_plus(connection.password))
            else:
                # Construct from parts with URL encoding
                uri = f"mongodb+srv://{quote_plus(connection.username)}:{quote_plus(connection.password)}@{connection.host}/{connection.database}"
            
            # Create a client with Server API version 1
            client = MongoClient(uri, server_api=ServerApi('1'))
            
            # Replace this with your actual collection and query
            db = client[connection.database or 'logs']  # Use database name or default to 'logs'
            collection = db['logs']  # Adjust collection name as needed
            
            cursor = collection.find().sort('timestamp', -1).limit(1000)
            
            for doc in cursor:
                # Convert MongoDB _id to string and handle date fields
                entry = {}
                for key, value in doc.items():
                    if key == '_id':
                        # Store MongoDB ID for duplicate prevention
                        entry['mongodb_id'] = str(value)
                    elif isinstance(value, datetime):
                        entry[key] = value
                    else:
                        entry[key] = value
                
                # Ensure required fields exist
                if 'timestamp' not in entry:
                    entry['timestamp'] = datetime.now()
                if 'ip_address' not in entry:
                    entry['ip_address'] = '127.0.0.1'
                if 'http_method' not in entry:
                    entry['http_method'] = 'GET'
                if 'resource' not in entry:
                    entry['resource'] = '/'
                if 'status_code' not in entry:
                    entry['status_code'] = 200
                    
                entries.append(entry)
            
            client.close()
        
        # Enrich and save the entries
        enriched_entries = enrich_log_data(entries)
        
        log_file.total_entries = len(enriched_entries)
        log_file.save()
        
        for i, entry in enumerate(enriched_entries):
            log_entry = LogEntry.objects.create(
                log_file=log_file,
                timestamp=entry['timestamp'],
                ip_address=entry['ip_address'],
                http_method=entry['http_method'],
                resource=entry['resource'],
                status_code=entry['status_code'],
                country=entry.get('country', 'Unknown'),
                page_category=entry.get('page_category', 'other')
            )
            
            # Store MongoDB ID if available
            if 'mongodb_id' in entry and hasattr(log_entry, 'mongodb_id'):
                log_entry.mongodb_id = entry['mongodb_id']
                log_entry.save()
            
            if i % 10 == 0:
                log_file.entries_processed = i + 1
                log_file.save()
        
        log_file.status = 'completed'
        log_file.processed_at = timezone.now()
        log_file.entries_processed = log_file.total_entries
        log_file.save()
        
    except Exception as e:
        log_file.status = 'failed'
        log_file.error_message = str(e)
        log_file.save()

def sync_mongodb_data_realtime(connection_id, log_file_id=None, interval=1):
    """
    Continuously sync data from MongoDB in real-time
    
    Args:
        connection_id: ID of the ExternalDataSource connection
        log_file_id: Optional ID of an existing LogFile (creates new one if None)
        interval: Sync interval in seconds (default: 1)
    """
    from .models import LogFile, LogEntry, ExternalDataSource
    import time
    from pymongo.mongo_client import MongoClient
    from pymongo.server_api import ServerApi
    import threading
    from django.utils import timezone
    
    # Get or create log file
    connection = ExternalDataSource.objects.get(id=connection_id)
    if log_file_id:
        log_file = LogFile.objects.get(id=log_file_id)
    else:
        log_file = LogFile.objects.create(
            name=f"Real-time import from {connection.name} - {timezone.now().strftime('%Y-%m-%d %H:%M')}",
            uploaded_by=connection.created_by,
            status='processing'
        )
    
    # Track imported document IDs to prevent duplicates
    imported_ids = set()
    
    # Track if sync is running
    is_running = True
    
    def sync_worker():
        nonlocal imported_ids, is_running
        
        try:
            # Set up MongoDB connection
            uri = f"mongodb+srv://{quote_plus(connection.username)}:{quote_plus(connection.password)}@{connection.host}/{connection.database}"
            client = MongoClient(uri, server_api=ServerApi('1'))
            db = client[connection.database or 'logs']
            collection = db['logs']
            
            # Get timestamp of last imported entry or use current time as starting point
            latest_entry = LogEntry.objects.filter(log_file=log_file).order_by('-timestamp').first()
            last_timestamp = latest_entry.timestamp if latest_entry else timezone.now() - timedelta(hours=1)
            
            # Initial load of existing IDs to avoid duplicates
            for entry in LogEntry.objects.filter(log_file=log_file):
                if hasattr(entry, 'mongodb_id') and entry.mongodb_id:
                    imported_ids.add(entry.mongodb_id)
            
            logger.info(f"Starting real-time sync from MongoDB. Tracking {len(imported_ids)} existing entries.")
            
            # Main sync loop
            while is_running:
                start_time = time.time()
                
                # Query for new documents added since last sync
                query = {"timestamp": {"$gt": last_timestamp}}
                cursor = collection.find(query).sort("timestamp", 1).limit(100)
                
                # Process new documents
                new_entries = []
                new_entries_count = 0
                last_doc = None
                
                for doc in cursor:
                    doc_id = str(doc['_id'])
                    
                    # Skip if already imported
                    if doc_id in imported_ids:
                        continue
                    
                    # Create entry from document
                    entry = {}
                    for key, value in doc.items():
                        if key == '_id':
                            # Store MongoDB ID for duplicate prevention
                            entry['mongodb_id'] = doc_id
                        elif isinstance(value, datetime):
                            entry[key] = value
                        else:
                            entry[key] = value
                    
                    # Ensure required fields exist
                    if 'timestamp' not in entry:
                        entry['timestamp'] = timezone.now()
                    if 'ip_address' not in entry:
                        entry['ip_address'] = '127.0.0.1'
                    if 'http_method' not in entry:
                        entry['http_method'] = 'GET'
                    if 'resource' not in entry:
                        entry['resource'] = '/'
                    if 'status_code' not in entry:
                        entry['status_code'] = 200
                    
                    new_entries.append(entry)
                    last_doc = doc
                    new_entries_count += 1
                
                # Process new entries if any found
                if new_entries:
                    # Enrich data
                    enriched_entries = enrich_log_data(new_entries)
                    
                    # Update log file stats
                    current_count = LogEntry.objects.filter(log_file=log_file).count()
                    log_file.total_entries = current_count + len(enriched_entries)
                    log_file.save()
                    
                    # Save entries to database
                    for i, entry in enumerate(enriched_entries):
                        # Create log entry
                        log_entry = LogEntry.objects.create(
                            log_file=log_file,
                            timestamp=entry['timestamp'],
                            ip_address=entry['ip_address'],
                            http_method=entry['http_method'],
                            resource=entry['resource'],
                            status_code=entry['status_code'],
                            country=entry.get('country', 'Unknown'),
                            page_category=entry.get('page_category', 'other')
                        )
                        
                        # Store MongoDB ID as custom field for duplicate prevention
                        if 'mongodb_id' in entry:
                            # Add custom field to store MongoDB ID
                            if hasattr(log_entry, 'mongodb_id'):
                                log_entry.mongodb_id = entry['mongodb_id']
                                log_entry.save()
                            
                            # Track ID to prevent future duplicates
                            imported_ids.add(entry['mongodb_id'])
                        
                        # Update progress counter
                        log_file.entries_processed = current_count + i + 1
                        if i % 10 == 0:
                            log_file.save()
                    
# Update last timestamp for next query
                    if last_doc and 'timestamp' in last_doc:
                        last_timestamp = last_doc['timestamp']
                    
                    logger.info(f"Imported {new_entries_count} new entries. Total: {log_file.entries_processed}")
                
                # Calculate time to sleep to maintain desired interval
                elapsed = time.time() - start_time
                sleep_time = max(0, interval - elapsed)
                time.sleep(sleep_time)
            
            # Clean up
            client.close()
            
        except Exception as e:
            logger.error(f"Error in MongoDB real-time sync: {str(e)}")
            log_file.status = 'failed'
            log_file.error_message = str(e)
            log_file.save()
            is_running = False
    
    # Start sync in background thread
    sync_thread = threading.Thread(target=sync_worker)
    sync_thread.daemon = True
    sync_thread.start()
    
    return {
        'success': True,
        'log_file_id': log_file.id,
        'message': f"Real-time sync started with {connection.name}",
        'thread': sync_thread,
        'stop_sync': lambda: setattr(sync_thread, 'is_running', False)  # Function to stop the sync
    }