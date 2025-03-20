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
    path('connections/', views.external_connections, name='external_connections'),
    path('connections/add/', views.add_connection, name='add_connection'),
    path('connections/<int:connection_id>/edit/', views.edit_connection, name='edit_connection'),
    path('connections/<int:connection_id>/delete/', views.delete_connection, name='delete_connection'),
    path('connections/<int:connection_id>/test/', views.test_connection, name='test_connection'),
    path('connections/<int:connection_id>/import/', views.import_from_connection, name='import_from_connection'),
]