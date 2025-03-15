from django.urls import path
from . import views

app_name = 'log_analyzer'

urlpatterns = [
    path('', views.log_list, name='log_list'),
    path('upload/', views.upload_log, name='upload_log'),
    path('<int:log_id>/', views.log_detail, name='log_detail'),
    path('<int:log_id>/status/', views.check_log_status, name='check_log_status'),
    path('<int:log_id>/export/', views.export_log_data, name='export_log_data'),
    path('generate-test/', views.generate_test_log, name='generate_test_log'),
]