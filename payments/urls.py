from django.urls import path

from . import views

app_name = 'payments'

urlpatterns = [
    path('milestones/<int:milestone_id>/fund/', views.fund_milestone, name='fund_milestone'),
    path('milestones/<int:milestone_id>/release/', views.release_milestone, name='release_milestone'),
]
