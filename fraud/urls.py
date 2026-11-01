from django.urls import path

from . import views

app_name = 'fraud'

urlpatterns = [
    path('', views.queue, name='queue'),
    path('<int:signal_id>/status/', views.update_status, name='update_status'),
]
