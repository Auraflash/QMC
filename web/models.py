from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
import re

class Customer(models.Model):
    name = models.CharField(max_length=200)
    account_number = models.CharField(
        max_length=15,
        unique=True,
        help_text="Pastel account code format"
    )
    contact_person = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def clean(self):
        # Ensure account number follows pattern (e.g., 000000)
        if not re.match(r'^\d{6}$', self.account_number):
            raise ValidationError({'account_number': 'Account number must be exactly 6 digits'})

    def get_total_holdings(self):
        # Get all movements ordered by document date and document type
        movements = CylinderMovement.objects.filter(
            document__customer=self
        ).select_related('document').order_by(
            'document__document_date',  # Order by date first
            'document__document_type',  # Then by document type (IN before NR)
            'document__created_at'      # Finally by creation time
        )
        
        # Debug print
        print(f"\nCalculating holdings for {self.name}")
        print("Initial total: 0")
        
        running_total = 0
        for movement in movements:
            old_total = running_total
            doc = movement.document
            if movement.movement_type == 'R':
                running_total += movement.quantity
                print(f"+ Received {movement.quantity} from {doc.document_number} ({doc.document_date})")
                print(f"  New total: {old_total} + {movement.quantity} = {running_total}")
            else:  # 'E' for Empty Return
                running_total -= movement.quantity
                print(f"- Returned {movement.quantity} from {doc.document_number} ({doc.document_date})")
                print(f"  New total: {old_total} - {movement.quantity} = {running_total}")
        
        print(f"Final holdings: {running_total}")
        return running_total

    def get_monthly_movements(self, year, month):
        start_date = timezone.datetime(year, month, 1)
        if month == 12:
            end_date = timezone.datetime(year + 1, 1, 1)
        else:
            end_date = timezone.datetime(year, month + 1, 1)
        
        return self.documents.filter(
            document_date__range=(start_date, end_date)
        ).prefetch_related('movements')

    def __str__(self):
        return f"{self.name} ({self.account_number})"

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        # Remove any whitespace from account number
        if self.account_number:
            self.account_number = self.account_number.strip()
        
        # Ensure is_active is True for new customers
        if not self.pk:  # If this is a new customer
            self.is_active = True
        
        # Call the parent save method
        super().save(*args, **kwargs)
        
        # Force a refresh from DB after save
        self.refresh_from_db()

class Document(models.Model):
    DOCUMENT_TYPES = [
        ('IN', 'Tax Invoice'),
        ('NR', 'Empty Return Slip'),
    ]
    
    document_number = models.CharField(
        max_length=20, 
        unique=True,
        help_text="Format: IN/NR followed by number"
    )
    document_type = models.CharField(max_length=2, choices=DOCUMENT_TYPES)
    document_date = models.DateField()
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='documents')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @staticmethod
    def generate_next_number(doc_type):
        """Generate next document number based on type"""
        prefix = doc_type
        last_doc = Document.objects.filter(
            document_number__startswith=prefix
        ).order_by('-document_number').first()
        
        if not last_doc:
            return f"{prefix}000001"
            
        # Extract number part and increment
        num_part = ''.join(filter(str.isdigit, last_doc.document_number))
        next_num = str(int(num_part) + 1).zfill(6)
        return f"{prefix}{next_num}"

    def clean(self):
        # Auto-generate document number if not provided
        if not self.document_number:
            self.document_number = self.generate_next_number(self.document_type)

    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('VOID', 'Voided'),
        ('PENDING_SYNC', 'Pending Sync'),
        ('SYNCED', 'Synced with Pastel')
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE'
    )
    void_reason = models.TextField(blank=True)
    void_date = models.DateTimeField(null=True, blank=True)
    void_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='voided_documents'
    )

    def __str__(self):
        return f"{self.get_document_type_display()} - {self.document_number} - {self.customer.name}"

class CylinderMovement(models.Model):
    MOVEMENT_TYPES = [
        ('R', 'Received'),
        ('E', 'Empty Return'),
    ]
    
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=1, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField()
    
    # Add Pastel item reference
    pastel_item_code = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        help_text="Pastel inventory item code"
    )
    
    def clean(self):
        if self.document.document_type == 'NR' and self.movement_type != 'E':
            raise ValidationError("Return Slips can only receive empty cylinders.")
    
    def __str__(self):
        return f"{self.document.document_number} - {self.get_movement_type_display()}: {self.quantity}"

class DocumentAudit(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='audits')
    action = models.CharField(max_length=20, choices=[
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'),
        ('DELETE', 'Deleted')
    ])
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    changes = models.JSONField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.document.document_number} - {self.action} by {self.user}"
