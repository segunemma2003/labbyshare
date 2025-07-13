from django.urls import path
from . import views

urlpatterns = [
    path('', views.health_check, name='health_check'),
    path('detailed/', views.detailed_health_check, name='detailed_health_check'),
]