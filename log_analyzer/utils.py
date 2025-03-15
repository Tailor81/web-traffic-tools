import csv
import re
from datetime import datetime
from io import StringIO
import pandas as pd
import random

def parse_log_line(line):
    """Parse a single line of IIS log format"""
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
    return None

def parse_log_file(file_object):
    """Parse an IIS log file and return a list of log entries"""
    content = file_object.read().decode('utf-8')
    lines = content.strip().split('\n')
    
    entries = []
    for line in lines:
        entry = parse_log_line(line)
        if entry:
            entries.append(entry)
    
    return entries

def enrich_log_data(entries):
    """Add geographical and categorical data to log entries"""
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
        'images/': 'static'
    }
    
    for entry in entries:
        # Add random country (in a real app, this would use IP geolocation)
        entry['country'] = random.choice(countries)
        
        # Categorize pages
        resource = entry['resource'].lower()
        category = 'other'
        
        for pattern, cat in page_categories.items():
            if pattern in resource:
                category = cat
                break
        
        entry['page_category'] = category
    
    return entries

def generate_test_data(num_entries=1000):
    """Generate sample log data for testing"""
    methods = ['GET', 'POST', 'PUT', 'DELETE']
    resources = [
        '/index.html',
        '/images/logo.png',
        '/event.php',
        '/scheduledemo.php',
        '/prototype.php',
        '/virtual-assistant.php',
        '/about.html',
        '/contact.php'
    ]
    statuses = [200, 301, 302, 404, 500]
    ip_ranges = [
        '192.168.1.',
        '10.0.0.',
        '172.16.0.',
        '157.20.0.',
        '128.1.0.'
    ]
    
    entries = []
    now = datetime.now()
    
    for _ in range(num_entries):
        hour = random.randint(0, 23)
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        
        time_str = f"{hour:02d}:{minute:02d}:{second:02d}"
        ip = f"{random.choice(ip_ranges)}{random.randint(1, 255)}"
        method = random.choice(methods)
        resource = random.choice(resources)
        status = random.choice(statuses)
        
        line = f"{time_str} {ip} {method} {resource} {status}"
        entry = parse_log_line(line)
        if entry:
            entries.append(entry)
    
    return enrich_log_data(entries)

def save_test_data_to_csv(filename, num_entries=1000):
    """Generate test data and save to CSV file"""
    entries = generate_test_data(num_entries)
    
    df = pd.DataFrame(entries)
    df.to_csv(filename, index=False)
    
    return filename

def analyze_log_data(entries):
    """Perform basic analysis on log entries"""
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
        'by_method': {}
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
    
    return result