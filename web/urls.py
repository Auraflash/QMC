from django.urls import path
from web import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', auth_views.LoginView.as_view(template_name='registration/login.html'), name='landing'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('customers/', views.customer_management, name='customer_management'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='landing'), name='logout'),
    path('api/customer-info/', views.get_customer_info, name='get_customer_info'),
    path('api/save-document/', views.save_document, name='save_document'),
    path('api/customer-documents/', views.get_customer_documents, name='get_customer_documents'),
    path('api/check-document-number/', views.check_document_number, name='check_document_number'),
    path('api/document-details/<str:document_number>/', views.get_document_details, name='get_document_details'),
    path('api/update-document/<int:document_id>/', views.update_document, name='update_document'),
    path('api/delete-document/<int:document_id>/', views.delete_document, name='delete_document'),
    path('api/user-permissions/', views.get_user_permissions, name='get_user_permissions'),
    path('api/customer-details/<str:account_number>/', views.get_customer_details, name='get_customer_details'),
    path('api/monthly-holdings/', views.get_monthly_holdings, name='get_monthly_holdings'),
    path('api/monthly-holdings-report/', views.get_monthly_holdings_report, name='monthly_holdings_report'),
]