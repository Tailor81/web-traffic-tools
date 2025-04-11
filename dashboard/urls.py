# Add to dashboard/urls.py
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_home, name='home'),
    # Marketing dashboard is now first - as requested by your lecturer
    path('marketing/', views.marketing_dashboard, name='marketing'),
    path('traffic/', views.traffic_dashboard, name='traffic'),
    path('geographic/', views.geographic_dashboard, name='geo'),
    path('conversion/', views.conversion_dashboard, name='conversion'),
    path('api/save-preference/', views.save_dashboard_preference, name='save_preference'),
    
    # API endpoints
    path('api/traffic-data/', views.traffic_data_api, name='traffic_data'),
    path('api/geo-data/', views.geo_data_api, name='geo_data'),
    path('api/conversion-data/', views.conversion_data_api, name='conversion_data'),
    path('api/marketing-data/', views.marketing_data_api, name='marketing_data'),
]