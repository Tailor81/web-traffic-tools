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

def generate_log_entries(num_entries=10000):
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