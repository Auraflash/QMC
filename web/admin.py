from django.contrib import admin
from .models import Customer, Document, CylinderMovement

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'account_number', 'created_at')
    search_fields = ('name', 'account_number')

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('document_number', 'document_type', 'customer', 'document_date', 'created_by')
    list_filter = ('document_type', 'document_date', 'customer')
    search_fields = ('document_number', 'customer__name')

@admin.register(CylinderMovement)
class CylinderMovementAdmin(admin.ModelAdmin):
    list_display = ('document', 'movement_type', 'quantity')
    list_filter = ('movement_type', 'document__document_type')
