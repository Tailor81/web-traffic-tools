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
from decimal import Decimal, InvalidOperation
from django.utils.timezone import make_aware

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
        
        seen_entries = set()  # Track unique entries to skip duplicates
        for i, row in df.iterrows():
            try:
                entry = {}
                
                # Get values from mapped columns or use defaults
                for target in required_cols:
                    if target in column_mapping:
                        entry[target] = row[column_mapping[target]]
                    else:
                        entry[target] = None  # Default to None if column is missing
                
                # Skip duplicate entries
                entry_tuple = tuple(entry.items())
                if entry_tuple in seen_entries:
                    continue
                seen_entries.add(entry_tuple)
                
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
                        ip = '0.0.0.0'
                    if not method:
                        method = 'GET'
                    if not resource:
                        resource = '/unknown'
                    if not status:
                        status = 200
                    
                    # Convert timestamp if it's a string
                    if isinstance(timestamp, str):
                        timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                    
                    entry = {
                        'timestamp': timestamp,
                        'ip_address': ip,
                        'http_method': method,
                        'resource': resource,
                        'status_code': int(status) if isinstance(status, (int, str)) and str(status).isdigit() else 200
                    }
                    
                    # Skip duplicate entries
                    entry_tuple = tuple(entry.items())
                    if entry_tuple in seen_entries:
                        continue
                    seen_entries.add(entry_tuple)
                    
                    entries.append(entry)
                    
                except Exception as row_error:
                    logger.error(f"Error processing row {i}: {row_error}")
                    continue
            
            logger.info(f"Successfully parsed {len(entries)} entries using csv module")
            return entries
            
        except Exception as csv_error:
            logger.error(f"Error with csv fallback: {csv_error}")
            return []

def enrich_log_data(entries):
    """Enrich log data with additional fields"""
    enriched_entries = []
    
    # Define possible values for marketing fields
    utm_sources = ['google', 'facebook', 'twitter', 'email', 'direct', 'referral', 'bing', 'linkedin']
    utm_campaigns = ['summer_sale', 'black_friday', 'product_launch', 'newsletter', 'social_promotion', 'holiday_special']
    device_types = ['mobile', 'desktop', 'tablet']
    action_types = ['page_view', 'add_to_cart', 'purchase', 'signup', 'login', 'search']
    product_categories = ['electronics', 'clothing', 'books', 'home_goods', 'sports', 'beauty']
    attribution_channels = ['organic_search', 'paid_search', 'social', 'email', 'direct', 'affiliate']
    customer_segments = ['new', 'returning', 'premium', 'vip', 'at_risk', 'inactive']
    discount_codes = ['SUMMER10', 'WELCOME20', 'FLASH50', 'SPECIAL25', 'HOLIDAY15', None, None, None]
    
    # Track user sessions and behavior
    user_sessions = {}
    
    for entry in entries:
        # Ensure timestamp is timezone-aware
        if isinstance(entry['timestamp'], datetime) and entry['timestamp'].tzinfo is None:
            entry['timestamp'] = make_aware(entry['timestamp'])

        # Get or create session info for this IP
        ip = entry['ip_address']
        if ip not in user_sessions:
            user_sessions[ip] = {
                'last_visit': entry['timestamp'],
                'session_id': entry.get('session_id') or ''.join(random.choices('0123456789abcdef', k=32)),
                'visit_count': 0
            }
        
        session_info = user_sessions[ip]
        session_info['visit_count'] += 1
        
        # Determine if this is a returning user (visited more than once)
        is_returning = session_info['visit_count'] > 1
        
        # Generate visit duration (between 10 seconds and 30 minutes)
        visit_duration = entry.get('visit_duration_sec') or random.randint(10, 1800)
        
        # Determine if this visit resulted in a conversion (10% chance if not already set)
        converted = entry.get('converted', False) or random.random() < 0.1
        
        # Create enriched entry with existing fields
        enriched_entry = {
            'timestamp': entry['timestamp'],
            'ip_address': entry['ip_address'],
            'http_method': entry['http_method'],
            'resource': entry['resource'],
            'status_code': entry['status_code'],
            'country': entry.get('country', 'Unknown'),
            'page_category': entry.get('page_category', 'other'),
            
            # Web Traffic & User Behavior - preserve existing values or generate new ones
            'utm_source': entry.get('utm_source') or (random.choice(utm_sources) if random.random() < 0.7 else None),
            'utm_campaign': entry.get('utm_campaign') or (random.choice(utm_campaigns) if random.random() < 0.7 else None),
            'session_id': entry.get('session_id') or session_info['session_id'],
            'user_id': entry.get('user_id') or (f"user_{random.randint(1, 1000)}" if random.random() < 0.6 else None),
            'product_interest': entry.get('product_interest') or (random.choice(product_categories) if random.random() < 0.5 else None),
            'interest_level': entry.get('interest_level') or (random.randint(1, 10) if random.random() < 0.5 else None),
            'action_type': entry.get('action_type') or random.choice(action_types),
            'converted': converted,
            'visit_duration_sec': visit_duration,
            'device_type': entry.get('device_type') or random.choice(device_types),
            'returning_user': entry.get('returning_user', is_returning)
        }
        
        # Add transaction data if converted
        if converted:
            try:
                # Safely convert and handle decimal values
                purchase_amount = entry.get('purchase_amount')
                if purchase_amount is None:
                    purchase_amount = round(random.uniform(10, 500), 2)
                else:
                    try:
                        purchase_amount = round(Decimal(purchase_amount), 2)
                    except (InvalidOperation, ValueError, TypeError):
                        purchase_amount = Decimal('0.00')

                discount_code = entry.get('discount_code') or random.choice(discount_codes)
                
                # Calculate discount amount safely
                if discount_code:
                    discount_amount = round(purchase_amount * Decimal('0.15'), 2)
                else:
                    discount_amount = Decimal('0.00')

                # Calculate cost of goods safely
                try:
                    cost_of_goods = round(purchase_amount * Decimal('0.6'), 2)
                except (InvalidOperation, ValueError, TypeError):
                    cost_of_goods = Decimal('0.00')

                enriched_entry.update({
                    'transaction_id': entry.get('transaction_id') or f"TRX-{random.randint(10000, 99999)}",
                    'purchase_amount': purchase_amount,
                    'currency': entry.get('currency', 'USD'),
                    'product_id': entry.get('product_id') or f"PROD-{random.randint(100, 999)}",
                    'product_name': entry.get('product_name') or f"{random.choice(product_categories)} Item {random.randint(1, 100)}",
                    'product_category': entry.get('product_category') or random.choice(product_categories),
                    'quantity': entry.get('quantity') or random.randint(1, 5),
                    'attribution_channel': entry.get('attribution_channel') or random.choice(attribution_channels),
                    'attribution_campaign': entry.get('attribution_campaign') or (random.choice(utm_campaigns) if random.random() < 0.7 else None),
                    'discount_code': discount_code,
                    'discount_amount': discount_amount if discount_code else None,
                    'customer_segment': entry.get('customer_segment') or random.choice(customer_segments),
                    'customer_lifetime_value': entry.get('customer_lifetime_value') or round(random.uniform(100, 2000), 2),
                    'repeat_purchase': entry.get('repeat_purchase', is_returning and random.random() < 0.3),
                    'days_since_last_purchase': entry.get('days_since_last_purchase') or (random.randint(1, 90) if is_returning else None),
                    'cost_of_goods_sold': cost_of_goods,
                    'profit_margin': round((purchase_amount - cost_of_goods) / purchase_amount * 100, 2) if purchase_amount > 0 else 0,
                    'acquisition_cost': entry.get('acquisition_cost') or round(random.uniform(5, 50), 2),
                    'roi': round((purchase_amount - cost_of_goods) / random.uniform(5, 50) * 100, 2) if purchase_amount > cost_of_goods else 0
                })
            except Exception as e:
                logger.error(f"Error processing transaction data: {str(e)}")
                # Continue without transaction data if there's an error
                pass
        
        enriched_entries.append(enriched_entry)
        
        # Update last visit time
        session_info['last_visit'] = entry['timestamp']
    
    return enriched_entries

def generate_test_data(num_entries=1000):
    """Generate sample log data for testing"""
    logger.info(f"Generating {num_entries} test log entries")
    
    methods = ['GET', 'POST', 'PUT', 'DELETE']
    resources = [
        '/index.html', '/products/category', '/cart', '/checkout',
        '/api/products', '/api/cart', '/api/orders',
        '/blog/post-1', '/blog/post-2',
        '/about-us', '/contact',
        '/static/css/main.css', '/static/js/app.js'
    ]
    statuses = [200, 200, 200, 200, 200, 301, 302, 404, 500]  # Weighted toward 200
    ip_ranges = [
        '192.168.1.', '10.0.0.', '172.16.0.',
        '157.20.0.', '128.1.0.'
    ]
    countries = [
        'United States', 'United Kingdom', 'Canada', 'Germany',
        'France', 'Japan', 'Australia', 'Brazil', 'India'
    ]
    page_categories = [
        'home', 'product', 'cart', 'checkout', 'blog',
        'api', 'static', 'about', 'contact'
    ]
    utm_sources = [
        'google', 'facebook', 'twitter', 'email',
        'direct', 'referral', 'bing', 'linkedin'
    ]
    utm_campaigns = [
        'summer_sale', 'black_friday', 'product_launch',
        'newsletter', 'social_promotion', 'holiday_special'
    ]
    device_types = ['mobile', 'desktop', 'tablet']
    action_types = [
        'page_view', 'add_to_cart', 'purchase',
        'signup', 'login', 'search'
    ]
    product_categories = [
        'electronics', 'clothing', 'books',
        'home_goods', 'sports', 'beauty'
    ]
    attribution_channels = [
        'organic_search', 'paid_search', 'social',
        'email', 'direct', 'affiliate'
    ]
    customer_segments = [
        'new', 'returning', 'premium',
        'vip', 'at_risk', 'inactive'
    ]
    discount_codes = [
        'SUMMER10', 'WELCOME20', 'FLASH50',
        'SPECIAL25', 'HOLIDAY15', None, None, None  # Make some entries have no discount
    ]
    
    entries = []
    now = datetime.now()
    
    # Create entries with all fields
    for _ in range(num_entries):
        # Basic timestamp and time-based calculations
        random_days = random.uniform(0, 30)  # Last 30 days
        random_seconds = random.randint(0, 86399)
        timestamp = now - timedelta(days=random_days, seconds=random_seconds)
        
        # Sometimes make it a returning user
        is_returning = random.random() < 0.4  # 40% chance of returning user
        
        # Generate visit duration (between 10 seconds and 30 minutes)
        visit_duration = random.randint(10, 1800)
        
        # Determine if this visit resulted in a conversion
        converted = random.random() < 0.1  # 10% conversion rate
        
        # Basic entry data
        entry = {
            'timestamp': timestamp,
            'ip_address': f"{random.choice(ip_ranges)}{random.randint(1, 255)}",
            'http_method': random.choice(methods),
            'resource': random.choice(resources),
            'status_code': random.choice(statuses),
            'country': random.choice(countries),
            'page_category': random.choice(page_categories),
            
            # Web Traffic & User Behavior
            'utm_source': random.choice(utm_sources) if random.random() < 0.7 else None,
            'utm_campaign': random.choice(utm_campaigns) if random.random() < 0.7 else None,
            'session_id': ''.join(random.choices('0123456789abcdef', k=32)),
            'user_id': f"user_{random.randint(1, 1000)}" if random.random() < 0.6 else None,
            'product_interest': random.choice(product_categories) if random.random() < 0.5 else None,
            'interest_level': random.randint(1, 10) if random.random() < 0.5 else None,
            'action_type': random.choice(action_types),
            'converted': converted,
            'visit_duration_sec': visit_duration,
            'device_type': random.choice(device_types),
            'returning_user': is_returning
        }
        
        # Add transaction data if converted
        if converted:
            purchase_amount = round(random.uniform(10, 500), 2)
            discount_code = random.choice(discount_codes)
            discount_amount = round(purchase_amount * 0.15, 2) if discount_code else 0
            cost_of_goods = round(purchase_amount * 0.6, 2)  # 60% COGS
            
            entry.update({
                'transaction_id': f"TRX-{random.randint(10000, 99999)}",
                'purchase_amount': purchase_amount,
                'currency': 'USD',
                'product_id': f"PROD-{random.randint(100, 999)}",
                'product_name': f"{random.choice(product_categories)} Item {random.randint(1, 100)}",
                'product_category': random.choice(product_categories),
                'quantity': random.randint(1, 5),
                'attribution_channel': random.choice(attribution_channels),
                'attribution_campaign': random.choice(utm_campaigns) if random.random() < 0.7 else None,
                'discount_code': discount_code,
                'discount_amount': discount_amount if discount_code else None,
                'customer_segment': round(random.uniform(100, 2000), 2),
                'customer_lifetime_value': round(random.uniform(100, 2000), 2),
                'repeat_purchase': is_returning and random.random() < 0.3,
                'days_since_last_purchase': random.randint(1, 90) if is_returning else None,
                'cost_of_goods_sold': cost_of_goods,
                'profit_margin': round((purchase_amount - cost_of_goods) / purchase_amount * 100, 2),
                'acquisition_cost': round(random.uniform(5, 50), 2),
                'roi': round((purchase_amount - cost_of_goods) / random.uniform(5, 50) * 100, 2)
            })
        
        entries.append(entry)
    
    # Sort by timestamp
    entries.sort(key=lambda x: x['timestamp'])
    return entries

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