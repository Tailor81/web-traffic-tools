import csv
import re
from datetime import datetime, timezone
from io import StringIO
import pandas as pd
import numpy as np
import random
import time
import logging

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
            return parse_csv_file(content)
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

def save_test_data_to_csv(filename, num_entries=1000):
    """Generate test data and save to CSV file"""
    entries = generate_test_data(num_entries)
    
    df = pd.DataFrame(entries)
    df.to_csv(filename, index=False)
    
    logger.info(f"Saved {num_entries} test entries to {filename}")
    return filename

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

def process_log_file(log_id):
    """Process a log file in the background
    
    In a production app, this would be a Celery task
    """
    from .models import LogFile, LogEntry
    
    logger.info(f"Processing log file with ID: {log_id}")
    log_file = LogFile.objects.get(id=log_id)
    
    try:
        # Update status to processing
        log_file.status = 'processing'
        log_file.save()
        
        # Open and parse the log file
        log_file.file.open('rb')
        logger.info(f"Opened file: {log_file.name}")
        
        entries = parse_log_file(log_file.file)
        log_file.file.close()
        
        logger.info(f"Parsed {len(entries)} entries from file")
        
        # Enrich the data
        enriched_entries = enrich_log_data(entries)
        
        # Update log file with total entries
        log_file.total_entries = len(enriched_entries)
        log_file.save()
        
        # Create LogEntry objects
        for i, entry in enumerate(enriched_entries):
            try:
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
                
                # Log progress periodically
                if i % 100 == 0:
                    logger.info(f"Created {i+1}/{len(enriched_entries)} entries")
                
            except Exception as entry_error:
                logger.error(f"Error creating entry {i+1}: {entry_error}")
                continue
                
            # Update progress every 10 entries
            if i % 10 == 0:
                log_file.entries_processed = i + 1
                log_file.save()
                
                # Simulate slower processing for demonstration
                time.sleep(0.01)
        
        # Update status to completed
        log_file.status = 'completed'
        log_file.processed_at = datetime.now()
        log_file.entries_processed = log_file.total_entries
        log_file.save()
        
        logger.info(f"Successfully processed log file {log_id}")
        
    except Exception as e:
        # Update status to failed
        logger.error(f"Error processing log file {log_id}: {e}")
        log_file.status = 'failed'
        log_file.error_message = str(e)
        log_file.save()
        

# log_analyzer updates for live data external connection

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
        
        # Enrich and save the entries
        enriched_entries = enrich_log_data(entries)
        
        log_file.total_entries = len(enriched_entries)
        log_file.save()
        
        for i, entry in enumerate(enriched_entries):
            LogEntry.objects.create(
                log_file=log_file,
                timestamp=entry['timestamp'],
                ip_address=entry['ip_address'],
                http_method=entry['http_method'],
                resource=entry['resource'],
                status_code=entry['status_code'],
                country=entry.get('country', 'Unknown'),
                page_category=entry.get('page_category', 'other')
            )
            
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