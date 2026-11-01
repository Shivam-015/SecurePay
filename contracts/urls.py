from django.urls import path

from . import views

app_name = 'contracts'

urlpatterns = [
    path('', views.contract_list, name='contract_list'),
    path('new/<slug:gig_slug>/', views.contract_create, name='contract_create'),
    path('<int:pk>/', views.contract_detail, name='contract_detail'),
    path('<int:pk>/evidence.json', views.contract_evidence_export, name='contract_evidence_export'),
    path('<int:pk>/<str:action>/', views.contract_action, name='contract_action'),
    path('milestones/<int:milestone_id>/submit/', views.milestone_submit, name='milestone_submit'),
    path('milestones/<int:milestone_id>/revision/', views.milestone_revision, name='milestone_revision'),
    path('submissions/<int:submission_id>/download/', views.submission_download, name='submission_download'),
]
