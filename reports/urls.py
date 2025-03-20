from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.report_list, name='report_list'),
    path('create/', views.create_report, name='create_report'),
    path('<int:report_id>/', views.report_detail, name='report_detail'),
    path('<int:report_id>/download/', views.download_report, name='download_report'),
    path('<int:report_id>/delete/', views.delete_report, name='delete_report'),
    path('<int:report_id>/regenerate/', views.regenerate_report, name='regenerate_report'),
]