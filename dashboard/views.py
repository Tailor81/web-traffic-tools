# dashboard/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import DashboardPreference

from django.http import JsonResponse
from log_analyzer.models import LogEntry, LogFile
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta
import json

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
    return redirect('dashboard:traffic')

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