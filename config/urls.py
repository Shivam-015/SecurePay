"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView
from api.views import GigViewSet
from core.views import health

api_router = DefaultRouter()
api_router.register('gigs', GigViewSet, basename='api-gig')

urlpatterns = [
    path('healthz/', health, name='health'),
    path('api/v1/auth/token/', TokenObtainPairView.as_view(), name='api-token-obtain'),
    path('api/v1/auth/token/refresh/', TokenRefreshView.as_view(), name='api-token-refresh'),
    path('api/v1/auth/token/verify/', TokenVerifyView.as_view(), name='api-token-verify'),
    path('api/v1/', include('api.urls')),
    path('api/v1/', include(api_router.urls)),
    path('contracts/', include('contracts.urls')),
    path('payments/', include('payments.urls')),
    path('notifications/', include('notifications.urls')),
    path('messages/', include('messaging.urls')),
    path('reviews/', include('reviews.urls')),
    path('invoices/', include('invoices.urls')),
    path('risk-review/', include('fraud.urls')),
    path('disputes/', include('disputes.urls')),
    path('marketplace/', include('marketplace.urls')),
    path('', include('accounts.urls')),
    path('admin/', admin.site.urls),
]
