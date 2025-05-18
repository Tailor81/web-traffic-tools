# Add to log_analyzer/utils.py or create a new file log_analyzer/mongo_data_generator.py

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from urllib.parse import quote_plus
import random
import pandas as pd
from datetime import datetime, timedelta
import logging
import json

logger = logging.getLogger(__name__)

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
        
        # Connect to MongoDB
        uri = f"mongodb+srv://{quote_plus(connection_info['username'])}:{quote_plus(connection_info['password'])}@{connection_info['host']}/{connection_info['database']}"
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

def generate_log_entries(num_entries=1000):
    """Generate realistic log entries for web traffic analysis"""
    now = datetime.now()

    # Define possible values for various fields
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
            'returning_user': is_returning,
            
            # Revenue & Transaction Fields
            'transaction_id': None,
            'purchase_amount': None,
            'currency': 'USD',
            'product_id': None,
            'product_name': None,
            'product_category': None,
            'quantity': None,
            
            # Marketing Attribution Fields
            'attribution_channel': None,
            'attribution_campaign': None,
            'discount_code': None,
            'discount_amount': None,
            
            # Customer Value Fields
            'customer_segment': None,
            'customer_lifetime_value': None,
            'repeat_purchase': False,
            'days_since_last_purchase': None,
            
            # Financial Analysis Fields
            'cost_of_goods_sold': None,
            'profit_margin': None,
            'acquisition_cost': None,
            'roi': None
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
                'product_id': f"PROD-{random.randint(100, 999)}",
                'product_name': f"{random.choice(product_categories)} Item {random.randint(1, 100)}",
                'product_category': random.choice(product_categories),
                'quantity': random.randint(1, 5),
                'attribution_channel': random.choice(attribution_channels),
                'attribution_campaign': random.choice(utm_campaigns) if random.random() < 0.7 else None,
                'discount_code': discount_code,
                'discount_amount': discount_amount if discount_code else None,
                'customer_segment': random.choice(customer_segments),
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

def upload_to_mongodb(entries, connection_info):
    """Upload test data to MongoDB"""
    try:
        # Connect to MongoDB
        username = quote_plus(connection_info['username'])
        password = quote_plus(connection_info['password'])
        uri = f"mongodb+srv://{username}:{password}@{connection_info['host']}/{connection_info['database']}"
        
        client = MongoClient(uri)
        db = client[connection_info['database']]
        collection = db['logs']
        
        # Clear existing data if requested
        if connection_info.get('clear_existing', False):
            collection.delete_many({})
            logger.info("Cleared existing data")
        
        # Insert new data
        result = collection.insert_many(entries)
        client.close()
        
        return {
            'success': True,
            'message': f"Successfully inserted {len(result.inserted_ids)} documents"
        }
    except Exception as e:
        logger.error(f"Error uploading to MongoDB: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }