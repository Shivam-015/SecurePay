from django.urls import path

from . import views

app_name = 'api'

urlpatterns = [
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/verify-email/', views.verify_email_api, name='verify-email'),
    path('auth/verify-email/resend/', views.resend_email_verification_api, name='resend-verify-email'),
    path('me/', views.MeView.as_view(), name='me'),
    path('contracts/', views.ContractListCreateView.as_view(), name='contracts'),
    path('contracts/<int:pk>/', views.ContractDetailView.as_view(), name='contract-detail'),
    path('contracts/<int:pk>/evidence/', views.ContractEvidenceView.as_view(), name='contract-evidence'),
    path('contracts/<int:contract_id>/action/', views.contract_action, name='contract-action'),
    path('contracts/<int:contract_id>/messages/', views.ContractMessagesView.as_view(), name='contract-messages'),
    path('milestones/<int:milestone_id>/fund/', views.milestone_fund, name='milestone-fund'),
    path('milestones/<int:milestone_id>/submit/', views.milestone_submit, name='milestone-submit'),
    path('milestones/<int:milestone_id>/revision/', views.milestone_revision, name='milestone-revision'),
    path('milestones/<int:milestone_id>/release/', views.milestone_release, name='milestone-release'),
    path('notifications/', views.NotificationListView.as_view(), name='notifications'),
    path('notifications/<int:notification_id>/read/', views.notification_mark_read, name='notification-read'),
    path('invoices/', views.InvoiceListView.as_view(), name='invoices'),
    path('disputes/', views.DisputeListCreateView.as_view(), name='disputes'),
    path('disputes/<int:pk>/', views.DisputeDetailView.as_view(), name='dispute-detail'),
    path('disputes/<int:dispute_id>/messages/', views.dispute_add_message, name='dispute-messages'),
    path('disputes/<int:dispute_id>/resolve/', views.dispute_resolve_api, name='dispute-resolve'),
    path('reviews/', views.review_create, name='reviews'),
]
