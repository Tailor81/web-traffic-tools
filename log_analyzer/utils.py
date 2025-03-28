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
from django.utils import timezone
import threading

from .models import LogFile, LogEntry, ExternalDataSource

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
            from mysql.connector import Error
            
            try:
                conn = mysql.connector.connect(
                    host=connection.host,
                    port=connection.port or 3306,  # Default MySQL port
                    database=connection.database,
                    user=connection.username,
                    password=connection.password,
                    connect_timeout=10
                )
                
                if conn.is_connected():
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.close()
                    conn.close()
                    return {'success': True, 'message': 'Successfully connected to MySQL database'}
                    
            except Error as e:
                return {'success': False, 'error': f'MySQL Error: {str(e)}'}
            
        elif source_type == 'postgresql':
            import psycopg2
            from psycopg2 import OperationalError
            
            try:
                conn = psycopg2.connect(
                    host=connection.host,
                    port=connection.port or 5432,  # Default PostgreSQL port
                    dbname=connection.database,
                    user=connection.username,
                    password=connection.password,
                    connect_timeout=10
                )
                
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                conn.close()
                return {'success': True, 'message': 'Successfully connected to PostgreSQL database'}
                
            except OperationalError as e:
                return {'success': False, 'error': f'PostgreSQL Error: {str(e)}'}
            
        elif source_type == 'mssql':
            import pyodbc
            
            try:
                conn_str = (
                    f"DRIVER={{SQL Server}};"
                    f"SERVER={connection.host},{connection.port or 1433};"  # Default MS SQL port
                    f"DATABASE={connection.database};"
                    f"UID={connection.username};"
                    f"PWD={connection.password};"
                    "TrustServerCertificate=yes;"
                    "timeout=10"
                )
                
                conn = pyodbc.connect(conn_str)
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                conn.close()
                return {'success': True, 'message': 'Successfully connected to MS SQL database'}
                
            except pyodbc.Error as e:
                return {'success': False, 'error': f'MS SQL Error: {str(e)}'}
            
        elif source_type == 'api':
            import requests
            from requests.exceptions import RequestException
            
            try:
                headers = {}
                if connection.api_key:
                    headers['Authorization'] = f"Bearer {connection.api_key}"
                
                response = requests.get(
                    connection.api_url,
                    headers=headers,
                    timeout=10
                )
                response.raise_for_status()
                return {'success': True, 'message': 'Successfully connected to API endpoint'}
                
            except RequestException as e:
                return {'success': False, 'error': f'API Error: {str(e)}'}
            
        elif source_type == 'mongodb':
            from pymongo.mongo_client import MongoClient
            from pymongo.server_api import ServerApi
            from pymongo.errors import OperationFailure, ServerSelectionTimeoutError
            import requests
            import json
            
            try:
                # Get current IP address
                ip_response = requests.get('https://api.ipify.org?format=json')
                current_ip = ip_response.json()['ip']
                
                # Construct the connection URI with proper URL encoding
                if connection.host.startswith('mongodb+'):
                    uri = connection.host
                    if '<db_password>' in uri:
                        uri = uri.replace('<db_password>', quote_plus(connection.password))
                else:
                    uri = f"mongodb+srv://{quote_plus(connection.username)}:{quote_plus(connection.password)}@{connection.host}/{connection.database}"
                
                # Create a client with Server API version 1 and timeout
                client = MongoClient(
                    uri,
                    server_api=ServerApi('1'),
                    serverSelectionTimeoutMS=10000  # 10 second timeout
                )
                
                # Test connection with ping
                client.admin.command('ping')
                
                # Get cluster information
                cluster_info = client.admin.command('getCmdLineOpts')
                cluster_name = cluster_info.get('parsed', {}).get('replication', {}).get('replSetName', 'Unknown')
                
                client.close()
                
                return {
                    'success': True, 
                    'message': f'Successfully connected to MongoDB cluster: {cluster_name}',
                    'ip': current_ip,
                    'cluster_info': {
                        'name': cluster_name,
                        'host': connection.host,
                        'database': connection.database
                    }
                }
                
            except (OperationFailure, ServerSelectionTimeoutError) as e:
                error_msg = str(e)
                if 'IP whitelist' in error_msg:
                    return {
                        'success': False, 
                        'error': f'MongoDB Error: IP {current_ip} not whitelisted. Please add this IP to your MongoDB Atlas whitelist.',
                        'ip': current_ip,
                        'requires_whitelist': True
                    }
                return {'success': False, 'error': f'MongoDB Error: {error_msg}'}
            
        else:
            return {'success': False, 'error': f"Unsupported source type: {source_type}"}
            
    except ImportError as e:
        return {'success': False, 'error': f"Required package not installed: {str(e)}"}
    except Exception as e:
        return {'success': False, 'error': f"Unexpected error: {str(e)}"}

def import_from_external_source(log_file, source_type, credentials):
    """
    Import log data from external sources (MongoDB, Elasticsearch, etc.)
    """
    try:
        if source_type == 'mongodb':
            # Parse MongoDB connection string
            if credentials.startswith('mongodb://'):
                connection_string = credentials
            else:
                # Handle credentials in the format: host:port,username,password,database,collection
                host, port, username, password, database, collection = credentials.split(',')
                connection_string = f"mongodb://{username}:{password}@{host}:{port}/{database}"
            
            # Connect to MongoDB
            client = MongoClient(connection_string)
            db = client[database]
            collection = db[collection]
            
            # Get the last synced timestamp from the log file
            last_synced = log_file.last_synced or datetime.min.replace(tzinfo=timezone.utc)
            
            # Query for new documents since last sync
            query = {
                'timestamp': {'$gt': last_synced}
            }
            
            # Get total count for progress tracking
            total_docs = collection.count_documents(query)
            processed = 0
            
            # Process documents in batches
            batch_size = 1000
            while True:
                # Get next batch of documents
                cursor = collection.find(query).skip(processed).limit(batch_size)
                batch = list(cursor)
                
                if not batch:
                    break
                
                # Create log entries in bulk
                log_entries = []
                for doc in batch:
                    # Check if entry already exists to prevent duplicates
                    existing_entry = LogEntry.objects.filter(
                        log_file=log_file,
                        timestamp=doc['timestamp'],
                        ip_address=doc['ip_address'],
                        http_method=doc['http_method'],
                        resource=doc['resource'],
                        status_code=doc['status_code']
                    ).exists()
                    
                    if not existing_entry:
                        log_entries.append(LogEntry(
                            log_file=log_file,
                            timestamp=doc['timestamp'],
                            ip_address=doc['ip_address'],
                            http_method=doc['http_method'],
                            resource=doc['resource'],
                            status_code=doc['status_code'],
                            country=doc.get('country', 'Unknown'),
                            page_category=doc.get('page_category', 'other'),
                            user_agent=doc.get('user_agent', ''),
                            referer=doc.get('referer', ''),
                            session_id=doc.get('session_id', ''),
                            response_time_ms=doc.get('response_time_ms', 0),
                            bytes_sent=doc.get('bytes_sent', 0),
                            query_params=doc.get('query_params', {})
                        ))
                
                # Bulk create new entries
                if log_entries:
                    LogEntry.objects.bulk_create(log_entries)
                
                # Update progress
                processed += len(batch)
                log_file.processed_entries = processed
                log_file.save()
                
                # Update last synced timestamp
                if batch:
                    log_file.last_synced = max(doc['timestamp'] for doc in batch)
                    log_file.save()
            
            # Mark sync as complete
            log_file.status = 'completed'
            log_file.save()
            
            # Close MongoDB connection
            client.close()
            
        elif source_type == 'elasticsearch':
            # Elasticsearch implementation
            pass
        else:
            raise ValueError(f"Unsupported source type: {source_type}")
            
    except Exception as e:
        log_file.status = 'error'
        log_file.error_message = str(e)
        log_file.save()
        raise

running_syncs = {}  # Track active syncs

def sync_mongodb_data_realtime(connection_id):
    """Function to sync MongoDB logs in real-time using threading."""
    connection = ExternalDataSource.objects.get(id=connection_id)

    log_file = LogFile.objects.create(
        name=f"Real-time import from {connection.name} - {timezone.now().strftime('%Y-%m-%d %H:%M')}",
        uploaded_by=connection.created_by,
        status='processing',
        total_entries=0,  # Will be updated dynamically
        entries_processed=0
    )

    running_syncs[connection_id] = {
        'status': True,
        'log_file_id': log_file.id
    }

    def sync_worker():
        try:
            entries_count = 0
            while running_syncs.get(connection_id, {}).get('status', False):
                # Simulate data sync (Replace with actual MongoDB query)
                time.sleep(1)  # Adjust sleep time as needed
                
                # Create log entry
                LogEntry.objects.create(
                    log_file=log_file,
                    timestamp=timezone.now(),
                    ip_address=f"192.168.1.{entries_count % 255}",
                    http_method="GET",
                    resource=f"/test-{entries_count}",
                    status_code=200,
                    country="USA",
                    page_category="home"
                )
                
                entries_count += 1
                
                # Update log file progress
                log_file.entries_processed = entries_count
                log_file.total_entries = entries_count
                log_file.save(update_fields=['entries_processed', 'total_entries'])

            log_file.status = 'completed'
        except Exception as e:
            log_file.status = 'failed'
            log_file.error_message = str(e)
        finally:
            log_file.save()
            running_syncs.pop(connection_id, None)  # Remove sync from active list

    thread = threading.Thread(target=sync_worker, daemon=True)
    thread.start()

    return {'success': True, 'log_file_id': log_file.id}

def stop_mongodb_sync(connection_id):
    """Stops a running MongoDB sync."""
    sync_info = running_syncs.get(connection_id, {})
    if sync_info:
        sync_info['status'] = False
        return {'success': True, 'message': 'Sync stopped'}
    return {'success': False, 'message': 'No active sync found'}

def check_sync_status(connection_id):
    """Check the status of an ongoing sync."""
    sync_info = running_syncs.get(connection_id, {})
    if sync_info:
        log_file = LogFile.objects.get(id=sync_info['log_file_id'])
        progress = (log_file.entries_processed / log_file.total_entries * 100) if log_file.total_entries > 0 else 0
        return {
            'status': 'processing',
            'progress': progress,
            'entries_processed': log_file.entries_processed,
            'total_entries': log_file.total_entries
        }
    return {'status': 'not_running'}