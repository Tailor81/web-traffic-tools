from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import DashboardPreference

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