from django.urls import path

from . import views

app_name = 'invoices'

urlpatterns = [
    path('', views.invoice_list, name='invoice_list'),
    path('<str:number>/', views.invoice_detail, name='invoice_detail'),
]
