from django.urls import path

from . import views

app_name = 'messaging'

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('<int:contract_id>/', views.conversation_detail, name='conversation'),
]
