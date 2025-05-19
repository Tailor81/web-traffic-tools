# dashboard/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
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
    if not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to access this dashboard.")
    """Traffic overview dashboard view"""
    context = {
        'dashboard_type': 'traffic',
        'dashboard_title': 'Traffic Overview',
    }
    return render(request, 'dashboard/traffic_dashboard.html', context)

@login_required
def geographic_dashboard(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to access this dashboard.")
    """Geographic analysis dashboard view"""
    context = {
        'dashboard_type': 'geo',
        'dashboard_title': 'Geographic Analysis',
    }
    return render(request, 'dashboard/geographic_dashboard.html', context)

@login_required
def conversion_dashboard(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to access this dashboard.")
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
    
    # Page categories - filter out null/empty values
    category_counts = (
        query.exclude(page_category__isnull=True)
        .exclude(page_category='')
        .values('page_category')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    # Status codes
    status_counts = (
        query.exclude(status_code__isnull=True)
        .values('status_code')
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
    
    # Country counts - filter out null/empty values and ensure we have data
    country_counts = list(
        query.exclude(country__isnull=True)
        .exclude(country='')
        .exclude(country='Unknown')
        .values('country')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    # If no country data, return empty response with log files
    if not country_counts:
        log_files = list(LogFile.objects.filter(status='completed').values('id', 'name'))
        return JsonResponse({
            'country_counts': [],
            'country_category_data': [],
            'log_files': log_files
        })
    
    # Country-category heatmap
    country_category_data = []
    top_countries = [item['country'] for item in country_counts[:10]]
    
    for country in top_countries:
        category_data = list(
            query.filter(country=country)
            .exclude(page_category__isnull=True)
            .exclude(page_category='')
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
        'country_counts': country_counts,
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
    
    # Conversion by country - filter out null/empty values
    conversion_by_country = list(
        conversion_query.exclude(country__isnull=True)
        .exclude(country='')
        .exclude(country='Unknown')
        .values('country')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    # Conversion by date
    conversion_by_date = []
    daily_data = list(
        query.extra({'date': "date(timestamp)"})
        .values('date')
        .annotate(total=Count('id'))
        .order_by('date')
    )
    
    conversion_daily = list(
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
    
    # If no conversion data, return empty response with log files
    if not conversion_by_country and not conversion_by_page:
        return JsonResponse({
            'total_visitors': total_visitors,
            'converting_visitors': converting_visitors,
            'conversion_rate': 0,
            'conversion_by_page': [],
            'conversion_by_country': [],
            'conversion_by_date': [],
            'log_files': log_files
        })
    
    return JsonResponse({
        'total_visitors': total_visitors,
        'converting_visitors': converting_visitors,
        'conversion_rate': (converting_visitors / total_visitors) * 100 if total_visitors > 0 else 0,
        'conversion_by_page': conversion_by_page,
        'conversion_by_country': conversion_by_country,
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

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Base query
        query = LogEntry.objects.filter(timestamp__gte=start_date)
        if log_file_id and log_file_id != 'all':
            query = query.filter(log_file_id=int(log_file_id))

        # SECTION 1: Top-Level KPIs
        # Revenue calculations
        revenue_query = query.aggregate(total=Sum('purchase_amount'))
        total_revenue = float(revenue_query['total'] or 0)

        # Units calculations
        units_query = query.aggregate(total=Sum('quantity'))
        total_units = int(units_query['total'] or 0)

        # Transaction calculations
        transaction_query = query.exclude(transaction_id__isnull=True).exclude(transaction_id__exact='')
        total_transactions = transaction_query.values('transaction_id').distinct().count()

        avg_order_value = (total_revenue / total_transactions) if total_transactions else 0
        
        # Conversion metrics
        session_query = query.values('session_id').distinct()
        total_sessions = session_query.count()
        
        conversions_query = query.filter(converted=True).values('session_id').distinct()
        conversions = conversions_query.count()
        
        conversion_rate = (conversions / total_sessions * 100) if total_sessions else 0
        
        # ROI and CLV calculations
        acq_cost_query = query.aggregate(total=Sum('acquisition_cost'))
        total_acquisition_cost = float(acq_cost_query['total'] or 0)
        
        roi = ((total_revenue - total_acquisition_cost) / total_acquisition_cost * 100) if total_acquisition_cost else 0
        
        clv_query = query.aggregate(avg=Avg('customer_lifetime_value'))
        avg_clv = float(clv_query['avg'] or 0)
        
        # Repeat purchase calculations
        customer_query = query.values('user_id').distinct()
        total_customers = customer_query.count()
        
        repeat_query = query.filter(repeat_purchase=True).values('user_id').distinct()
        repeat_customers = repeat_query.count()
        
        repeat_purchase_rate = (repeat_customers / total_customers * 100) if total_customers else 0

        # SECTION 2: Revenue Analysis
        revenue_by_category = list(
            query.exclude(product_category__isnull=True)
            .exclude(product_category='')
            .values('product_category')
                .annotate(revenue=Sum('purchase_amount'))
                .order_by('-revenue')
        )
        
        revenue_by_product = list(
            query.exclude(product_name__isnull=True)
            .exclude(product_name='')
            .values('product_name')
                .annotate(revenue=Sum('purchase_amount'))
                .order_by('-revenue')
        )

        # SECTION 3: Customer Segmentation
        segment_breakdown = list(
            query.exclude(customer_segment__isnull=True)
            .exclude(customer_segment='')
            .values('customer_segment')
                .annotate(count=Count('user_id', distinct=True))
                .order_by('-count')
        )

        # SECTION 4: CLV vs Acquisition Cost
        clv_vs_acq = list(
            query.values('user_id', 'customer_lifetime_value', 'acquisition_cost')
                .exclude(customer_lifetime_value__isnull=True)
                .exclude(acquisition_cost__isnull=True)
                .order_by('-customer_lifetime_value')[:100]
        )

        # SECTION 5: Revenue Over Time
        revenue_over_time = list(
            query.annotate(date=TruncDate('timestamp'))
            .values('date')
            .annotate(revenue=Sum('purchase_amount'))
            .order_by('date')
        )

        # SECTION 6: Campaign Performance
        campaign_performance = list(
            query.exclude(attribution_campaign__isnull=True)
            .exclude(attribution_campaign='')
            .values('attribution_campaign')
            .annotate(
                revenue=Sum('purchase_amount'),
                conversions=Count('id', filter=Q(converted=True)),
                cost=Sum('acquisition_cost')
            )
            .order_by('-revenue')
        )

        # SECTION 7: AI Insights
        # Revenue forecast (simple linear regression)
        if len(revenue_over_time) > 1:
            dates = [item['date'] for item in revenue_over_time]
            revenues = [float(item['revenue'] or 0) for item in revenue_over_time]
            forecast_change = ((revenues[-1] - revenues[0]) / revenues[0] * 100) if revenues[0] else 0
        else:
            forecast_change = 0

        # Top segment by CLV
        top_segment = segment_breakdown[0]['customer_segment'] if segment_breakdown else 'N/A'
        top_segment_clv = float(segment_breakdown[0]['count']) if segment_breakdown else 0

        # Top campaign by ROI
        if campaign_performance:
            top_campaign = campaign_performance[0]['attribution_campaign']
            campaign_revenue = float(campaign_performance[0]['revenue'] or 0)
            campaign_cost = float(campaign_performance[0]['cost'] or 0)
            top_campaign_roi = ((campaign_revenue - campaign_cost) / campaign_cost * 100) if campaign_cost else 0
        else:
            top_campaign = 'N/A'
            top_campaign_roi = 0

        # SECTION 8: Log Files
        log_files = list(LogFile.objects.filter(status='completed').values(
            'id', 'name', 'status', 'total_entries', 'entries_processed', 'error_message'))

        response_data = {
            'total_revenue': total_revenue,
            'total_units': total_units,
            'total_transactions': total_transactions,
            'avg_order_value': avg_order_value,
            'conversion_rate': conversion_rate,
            'roi': roi,
            'clv': avg_clv,
            'repeat_purchase_rate': repeat_purchase_rate,
            'revenue_by_category': revenue_by_category,
            'revenue_by_product': revenue_by_product,
            'segment_breakdown': segment_breakdown,
            'clv_vs_acq': clv_vs_acq,
            'revenue_over_time': revenue_over_time,
            'campaign_performance': campaign_performance,
            'ai_insights': {
                'forecast_change': forecast_change,
                'top_segment': top_segment,
                'top_segment_clv': top_segment_clv,
                'top_campaign': top_campaign,
                'top_campaign_roi': top_campaign_roi
            },
            'log_files': log_files,
        }

        return JsonResponse(response_data)
    except Exception as e:
        print(f"[ERROR] API Error: {str(e)}")
        import traceback
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)