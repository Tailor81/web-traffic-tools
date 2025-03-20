# dashboard/urls.py
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_home, name='home'),
    path('traffic/', views.traffic_dashboard, name='traffic'),
    path('geographic/', views.geographic_dashboard, name='geo'),
    path('conversion/', views.conversion_dashboard, name='conversion'),
    path('api/save-preference/', views.save_dashboard_preference, name='save_preference'),
    
    # Add API endpoints
    path('api/traffic-data/', views.traffic_data_api, name='traffic_data'),
    path('api/geo-data/', views.geo_data_api, name='geo_data'),
    path('api/conversion-data/', views.conversion_data_api, name='conversion_data'),
]