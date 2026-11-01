from django.urls import path

from . import views

app_name = 'disputes'

urlpatterns = [
    path('staff/queue/', views.dispute_queue, name='queue'),
    path('milestones/<int:milestone_id>/new/', views.create_dispute, name='create'),
    path('<int:dispute_id>/', views.dispute_detail, name='detail'),
    path('<int:dispute_id>/message/', views.dispute_message, name='message'),
    path('<int:dispute_id>/resolve/', views.dispute_resolve, name='resolve'),
]
