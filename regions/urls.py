from django.urls import path
from . import views

app_name = 'regions'

urlpatterns = [
    path('', views.RegionListView.as_view(), name='region_list'),
    path('<str:code>/', views.RegionDetailView.as_view(), name='region_detail'),
    path('<str:code>/settings/', views.RegionSettingsView.as_view(), name='region_settings'),
]

