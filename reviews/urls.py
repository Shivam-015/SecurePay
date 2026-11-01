from django.urls import path

from . import views

app_name = 'reviews'

urlpatterns = [path('<int:contract_id>/', views.review_contract, name='review_contract')]
