# dashboard/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import DashboardPreference

from django.http import JsonResponse
from log_analyzer.models import LogEntry, LogFile
from django.db.models import Count, Sum, Avg, Q, F
from django.utils import timezone
from datetime import timedelta
import json

from django.db import models
from django.db.models import Count, Q
from django.db.models.functions import ExtractHour, ExtractWeekDay
from django.db.models.functions import TruncDate, ExtractHour, ExtractWeekDay

@login_required
def dashboard_home(request):
    """Dashboard home view - redirect to default dashboard or traffic dashboard"""
    try:
        default_dashboard = DashboardPreference.objects.filter(
            user=request.user, 
            is_default=True
        ).first()
        
        if default_dashboard:
            return redirect(f'dashboard:{default_dashboard.dashboard_type}')
    except:
        pass
    
    # Default to traffic dashboard if no preference found
    return redirect('dashboard:marketing')

@login_required
def traffic_dashboard(request):
    """Traffic overview dashboard view"""
    context = {
        'dashboard_type': 'traffic',
        'dashboard_title': 'Traffic Overview',
    }
    return render(request, 'dashboard/traffic_dashboard.html', context)

@login_required
def geographic_dashboard(request):
    """Geographic analysis dashboard view"""
    context = {
        'dashboard_type': 'geo',
        'dashboard_title': 'Geographic Analysis',
    }
    return render(request, 'dashboard/geographic_dashboard.html', context)

@login_required
def conversion_dashboard(request):
    """Conversion metrics dashboard view"""
    context = {
        'dashboard_type': 'conversion',
        'dashboard_title': 'Conversion Metrics',
    }
    return render(request, 'dashboard/conversion_dashboard.html', context)

@login_required
def save_dashboard_preference(request):
    """API endpoint to save dashboard preferences"""
    if request.method == 'POST':
        dashboard_type = request.POST.get('dashboard_type')
        is_default = request.POST.get('is_default') == 'true'
        settings = request.POST.get('settings', '{}')
        
        if dashboard_type:
            # Get or create preference
            preference, created = DashboardPreference.objects.get_or_create(
                user=request.user,
                dashboard_type=dashboard_type,
                defaults={'settings': settings, 'is_default': is_default}
            )
            
            # Update if not created
            if not created:
                preference.settings = settings
                preference.is_default = is_default
                preference.save()
            
            # If this is set as default, clear other defaults
            if is_default:
                DashboardPreference.objects.filter(
                    user=request.user
                ).exclude(
                    id=preference.id
                ).update(is_default=False)
                
            return JsonResponse({'success': True})
            
    return JsonResponse({'success': False}, status=400)

# Add standalone dashboard views
@login_required
def standalone_traffic_dashboard(request):
    """Standalone traffic dashboard view"""
    return render(request, 'dashboard/standalone_traffic.html')

@login_required
def standalone_geographic_dashboard(request):
    """Standalone geographic dashboard view"""
    return render(request, 'dashboard/standalone_geographic.html')

@login_required
def standalone_conversion_dashboard(request):
    """Standalone conversion dashboard view"""
    return render(request, 'dashboard/standalone_conversion.html')









# Add these new API endpoints
@login_required
def traffic_data_api(request):
    """API endpoint to return traffic data for charts"""
    days = int(request.GET.get('days', 30))
    log_file_id = request.GET.get('log_file_id', None)
    
    # Calculate date range
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    # Base queryset
    query = LogEntry.objects.filter(timestamp__gte=start_date)
    
    # Filter by log file if specified
    if log_file_id and log_file_id != 'all':
        query = query.filter(log_file_id=int(log_file_id))
    
    # Calculate metrics
    total_visits = query.count()
    unique_visitors = query.values('ip_address').distinct().count()
    success_requests = query.filter(status_code__lt=400).count()
    error_requests = query.filter(status_code__gte=400).count()
    
    # Traffic over time
    daily_traffic = (
        query.extra({'date': "date(timestamp)"})
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )
    
    # Page categories
    category_counts = (
        query.values('page_category')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    # Status codes
    status_counts = (
        query.values('status_code')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    # Log files for dropdown
    log_files = list(LogFile.objects.filter(status='completed').values('id', 'name'))
    
    return JsonResponse({
        'total_visits': total_visits,
        'unique_visitors': unique_visitors,
        'success_rate': (success_requests / total_visits) * 100 if total_visits > 0 else 0,
        'error_rate': (error_requests / total_visits) * 100 if total_visits > 0 else 0,
        'daily_traffic': list(daily_traffic),
        'category_counts': list(category_counts),
        'status_counts': list(status_counts),
        'log_files': log_files
    })

@login_required
def geo_data_api(request):
    """API endpoint to return geographic data for charts"""
    days = int(request.GET.get('days', 30))
    log_file_id = request.GET.get('log_file_id', None)
    
    # Calculate date range
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    # Base queryset
    query = LogEntry.objects.filter(timestamp__gte=start_date)
    
    # Filter by log file if specified
    if log_file_id and log_file_id != 'all':
        query = query.filter(log_file_id=int(log_file_id))
    
    # Country counts
    country_counts = (
        query.values('country')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    # Country-category heatmap
    country_category_data = []
    top_countries = [item['country'] for item in country_counts[:10]]
    
    for country in top_countries:
        category_data = (
            query.filter(country=country)
            .values('page_category')
            .annotate(count=Count('id'))
        )
        for item in category_data:
            country_category_data.append({
                'country': country,
                'category': item['page_category'],
                'count': item['count']
            })
    
    # Log files for dropdown
    log_files = list(LogFile.objects.filter(status='completed').values('id', 'name'))
    
    return JsonResponse({
        'country_counts': list(country_counts),
        'country_category_data': country_category_data,
        'log_files': log_files
    })

@login_required
def conversion_data_api(request):
    """API endpoint to return conversion data for charts"""
    days = int(request.GET.get('days', 30))
    log_file_id = request.GET.get('log_file_id', None)
    
    # Calculate date range
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    # Base queryset
    query = LogEntry.objects.filter(timestamp__gte=start_date)
    
    # Filter by log file if specified
    if log_file_id and log_file_id != 'all':
        query = query.filter(log_file_id=int(log_file_id))
    
    # Define conversion resources
    conversion_resources = [
        '/scheduledemo.php',
        '/contact.php',
        '/virtual-assistant.php'
    ]
    
    # Calculate metrics
    total_visitors = query.values('ip_address').distinct().count()
    
    # Get conversion entries
    conversion_query = query.filter(resource__iregex=r'scheduledemo\.php|contact\.php|virtual-assistant\.php')
    converting_visitors = conversion_query.values('ip_address').distinct().count()
    
    # Conversion by page
    conversion_by_page = []
    for resource in conversion_resources:
        count = query.filter(resource__icontains=resource).count()
        conversion_by_page.append({
            'page': resource,
            'count': count
        })
    
    # Conversion by country
    conversion_by_country = (
        conversion_query.values('country')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    # Conversion by date
    conversion_by_date = []
    daily_data = (
        query.extra({'date': "date(timestamp)"})
        .values('date')
        .annotate(total=Count('id'))
        .order_by('date')
    )
    
    conversion_daily = (
        conversion_query.extra({'date': "date(timestamp)"})
        .values('date')
        .annotate(conv_count=Count('id'))
        .order_by('date')
    )
    
    # Convert to dict for easier lookup
    conv_dict = {item['date']: item['conv_count'] for item in conversion_daily}
    
    for day in daily_data:
        date_str = day['date']
        total = day['total']
        conv_count = conv_dict.get(date_str, 0)
        rate = (conv_count / total) * 100 if total > 0 else 0
        
        conversion_by_date.append({
            'date': date_str,
            'total': total,
            'conversions': conv_count,
            'rate': rate
        })
    
    # Log files for dropdown
    log_files = list(LogFile.objects.filter(status='completed').values('id', 'name'))
    
    return JsonResponse({
        'total_visitors': total_visitors,
        'converting_visitors': converting_visitors,
        'conversion_rate': (converting_visitors / total_visitors) * 100 if total_visitors > 0 else 0,
        'conversion_by_page': conversion_by_page,
        'conversion_by_country': list(conversion_by_country),
        'conversion_by_date': conversion_by_date,
        'log_files': log_files
    })
    

# Notes from the client






@login_required
def marketing_dashboard(request):
    """Render the redesigned marketing & sales insights dashboard."""
    return render(request, 'dashboard/marketing_dashboard.html')

@login_required
def marketing_data_api(request):
    """API endpoint for the redesigned marketing dashboard data."""
    try:
        from django.db import connection
        from django.db.models import Sum, Avg, Count
        from django.db.models.functions import TruncDate
        import json

        days = int(request.GET.get('days', 30))
        log_file_id = request.GET.get('log_file_id', None)
        
        print(f"\n[DEBUG] Marketing API Request - Days: {days}, Log File ID: {log_file_id}")

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        print(f"[DEBUG] Date Range: {start_date} to {end_date}")

        # Base query
        query = LogEntry.objects.filter(timestamp__gte=start_date)
        if log_file_id and log_file_id != 'all':
            query = query.filter(log_file_id=int(log_file_id))
        
        # Debug total records and sample data
        total_records = query.count()
        print(f"[DEBUG] Total records in date range: {total_records}")
        
        # Debug sample records with all relevant fields
        sample_records = query.values(
            'timestamp', 'purchase_amount', 'quantity', 'transaction_id',
            'converted', 'customer_lifetime_value', 'acquisition_cost',
            'product_category', 'product_name', 'customer_segment',
            'user_id', 'repeat_purchase'
        )[:5]
        print("[DEBUG] Sample records:")
        for record in sample_records:
            print(f"  {json.dumps(record, default=str)}")

        # Debug SQL queries
        def debug_query(qs):
            if hasattr(qs, 'query'):
                print(f"[DEBUG] SQL Query: {qs.query}")
            return qs

        # SECTION 1: Top-Level KPIs
        # Revenue calculations
        revenue_query = query.aggregate(total=Sum('purchase_amount'))
        print(f"[DEBUG] Revenue Query: {query.filter(purchase_amount__isnull=False).query}")
        total_revenue = revenue_query['total'] or 0
        print(f"[DEBUG] Revenue Query Result: {revenue_query}")

        # Units calculations
        units_query = query.aggregate(total=Sum('quantity'))
        print(f"[DEBUG] Units Query: {query.filter(quantity__isnull=False).query}")
        total_units = units_query['total'] or 0
        print(f"[DEBUG] Units Query Result: {units_query}")

        # Transaction calculations
        transaction_query = query.exclude(transaction_id__isnull=True).exclude(transaction_id__exact='')
        print(f"[DEBUG] Transaction Query: {transaction_query.query}")
        total_transactions = transaction_query.values('transaction_id').distinct().count()
        print(f"[DEBUG] Transaction Query Count: {total_transactions}")
        
        # Debug transaction sample
        transaction_sample = transaction_query.values('transaction_id', 'purchase_amount')[:5]
        print("[DEBUG] Sample transactions:")
        for trans in transaction_sample:
            print(f"  {json.dumps(trans, default=str)}")

        avg_order_value = (total_revenue / total_transactions) if total_transactions else 0
        
        # Conversion metrics
        session_query = query.values('session_id').distinct()
        print(f"[DEBUG] Session Query: {session_query.query}")
        total_sessions = session_query.count()
        
        conversions_query = query.filter(converted=True).values('session_id').distinct()
        print(f"[DEBUG] Conversions Query: {conversions_query.query}")
        conversions = conversions_query.count()
        
        conversion_rate = (conversions / total_sessions * 100) if total_sessions else 0
        print(f"[DEBUG] Sessions: {total_sessions}, Conversions: {conversions}, Rate: {conversion_rate}%")
        
        # ROI and CLV calculations
        acq_cost_query = query.aggregate(total=Sum('acquisition_cost'))
        print(f"[DEBUG] Acquisition Cost Query: {query.filter(acquisition_cost__isnull=False).query}")
        total_acquisition_cost = acq_cost_query['total'] or 0
        
        roi = ((total_revenue - total_acquisition_cost) / total_acquisition_cost * 100) if total_acquisition_cost else 0
        
        clv_query = query.aggregate(avg=Avg('customer_lifetime_value'))
        print(f"[DEBUG] CLV Query: {query.filter(customer_lifetime_value__isnull=False).query}")
        avg_clv = clv_query['avg'] or 0
        print(f"[DEBUG] Acquisition Cost: {total_acquisition_cost}, ROI: {roi}%, CLV: {avg_clv}")
        
        # Repeat purchase calculations
        customer_query = query.values('user_id').distinct()
        print(f"[DEBUG] Customer Query: {customer_query.query}")
        total_customers = customer_query.count()
        
        repeat_query = query.filter(repeat_purchase=True).values('user_id').distinct()
        print(f"[DEBUG] Repeat Purchase Query: {repeat_query.query}")
        repeat_customers = repeat_query.count()
        
        repeat_purchase_rate = (repeat_customers / total_customers * 100) if total_customers else 0
        print(f"[DEBUG] Total Customers: {total_customers}, Repeat Customers: {repeat_customers}, Rate: {repeat_purchase_rate}%")

        # SECTION 2: Revenue Analysis
        revenue_by_category = list(
            query.values('product_category')
                .annotate(revenue=Sum('purchase_amount'))
                .order_by('-revenue')
        )
        print(f"[DEBUG] Revenue by Category Query: {query.values('product_category').query}")
        print("[DEBUG] Revenue by Category:")
        for cat in revenue_by_category:
            print(f"  {json.dumps(cat, default=str)}")
        
        revenue_by_product = list(
            query.values('product_name')
                .annotate(revenue=Sum('purchase_amount'))
                .order_by('-revenue')
        )
        print(f"[DEBUG] Revenue by Product Query: {query.values('product_name').query}")
        print("[DEBUG] Revenue by Product:")
        for prod in revenue_by_product:
            print(f"  {json.dumps(prod, default=str)}")

        # SECTION 3: Customer Segmentation
        segment_breakdown = list(
            query.values('customer_segment')
                .annotate(count=Count('user_id', distinct=True))
                .order_by('-count')
        )
        print(f"[DEBUG] Segment Breakdown Query: {query.values('customer_segment').query}")
        print("[DEBUG] Segment Breakdown:")
        for seg in segment_breakdown:
            print(f"  {json.dumps(seg, default=str)}")

        # SECTION 4: CLV vs Acquisition Cost
        clv_vs_acq = list(
            query.values('user_id', 'customer_lifetime_value', 'acquisition_cost')
                .exclude(customer_lifetime_value__isnull=True)
                .exclude(acquisition_cost__isnull=True)
                .order_by('-customer_lifetime_value')[:100]
        )
        print(f"[DEBUG] CLV vs Acquisition Query: {query.filter(customer_lifetime_value__isnull=False, acquisition_cost__isnull=False).query}")
        print("[DEBUG] CLV vs Acquisition Cost Sample:")
        for clv in clv_vs_acq[:5]:
            print(f"  {json.dumps(clv, default=str)}")

        # SECTION 7: Log Files
        log_files = list(LogFile.objects.filter(status='completed').values(
            'id', 'name', 'status', 'total_entries', 'entries_processed', 'error_message'))
        print("[DEBUG] Log Files:")
        for log in log_files:
            print(f"  {json.dumps(log, default=str)}")

        response_data = {
            'total_revenue': float(total_revenue),
            'total_units': int(total_units),
            'total_transactions': int(total_transactions),
            'avg_order_value': float(avg_order_value),
            'conversion_rate': float(conversion_rate),
            'roi': float(roi),
            'clv': float(avg_clv),
            'repeat_purchase_rate': float(repeat_purchase_rate),
            'revenue_by_category': revenue_by_category,
            'revenue_by_product': revenue_by_product,
            'segment_breakdown': segment_breakdown,
            'clv_vs_acq': clv_vs_acq,
            'log_files': log_files,
        }

        print("\n[DEBUG] Final Response Data:")
        for key, value in response_data.items():
            if isinstance(value, (list, dict)):
                print(f"  {key}: {len(value)} items")
            else:
                print(f"  {key}: {value}")

        return JsonResponse(response_data)
    except Exception as e:
        print(f"[ERROR] API Error: {str(e)}")
        import traceback
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)