from django.urls import path
from . import views

app_name = 'services'

urlpatterns = [
    # Categories
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/<int:category_id>/services/', views.CategoryServicesView.as_view(), name='category_services'),
    path('categories/<int:category_id>/addons/', views.CategoryAddOnsView.as_view(), name='category_addons'),
    # Add-ons (standalone)
    path('addons/', views.AddOnListView.as_view(), name='addon_list'),
    
    # Services
    path('', views.ServiceListView.as_view(), name='service_list'),
    path('featured/', views.featured_services, name='featured_services'),
    path('search/', views.search_services, name='search_services'),
    path('<int:id>/', views.ServiceDetailView.as_view(), name='service_detail'),
    path('<int:service_id>/reviews/', views.ServiceReviewsView.as_view(), name='service_reviews'),
]