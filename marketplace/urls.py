from django.urls import path

from . import views

app_name = 'marketplace'

urlpatterns = [
    path('', views.gig_list, name='gig_list'),
    path('services/new/', views.gig_create, name='gig_create'),
    path('services/<slug:slug>/edit/', views.gig_edit, name='gig_edit'),
    path('services/<slug:slug>/', views.gig_detail, name='gig_detail'),
]
