from django import forms
from .models import Document, CylinderMovement, Customer
import re

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'account_number', 'contact_person', 'phone_number', 'email', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'account_number': forms.TextInput(attrs={
                'class': 'form-control',
                'pattern': '[0-9]{6}',
                'placeholder': '000000'
            }),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean_account_number(self):
        account_number = self.cleaned_data['account_number']
        if not re.match(r'^\d{6}$', account_number):
            raise forms.ValidationError('Account number must be exactly 6 digits')
        return account_number

class DocumentForm(forms.ModelForm):
    customer_account = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    cylinders_received = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    cylinders_returned = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Document
        fields = ['document_number', 'document_type', 'document_date', 'customer_account']
        widgets = {
            'document_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Document number'
            }),
            'document_type': forms.Select(attrs={'class': 'form-control'}),
            'document_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        doc_type = cleaned_data.get('document_type')
        received = cleaned_data.get('cylinders_received')
        returned = cleaned_data.get('cylinders_returned')
        
        # Validate movements based on document type
        if doc_type == 'NR':
            if received:
                raise forms.ValidationError("Return Slips cannot have received cylinders")
            if not returned:
                raise forms.ValidationError("Return Slips must have returned cylinders")
        elif doc_type == 'IN':
            if not (received or returned):
                raise forms.ValidationError("Tax Invoice must have either received or returned cylinders")

        # Handle document number formatting
        doc_num = cleaned_data.get('document_number', '')
        if doc_num:
            # Remove any spaces or special characters
            doc_num = ''.join(c for c in doc_num if c.isalnum()).upper()
            
            # Skip duplicate validation if we're editing an existing document
            if self.instance and self.instance.pk:
                if self.instance.document_number == doc_num:
                    cleaned_data['document_number'] = doc_num
                    return cleaned_data
            
            # For new documents or changed numbers
            if doc_num.isdigit():
                doc_num = f"{doc_type}{doc_num.zfill(6)}"
            else:
                # Validate prefix matches document type
                if not doc_num.startswith(doc_type):
                    raise forms.ValidationError(f"Document number must start with {doc_type}")
                
                # Extract and validate number part
                num_part = doc_num[2:]
                if not num_part.isdigit():
                    raise forms.ValidationError("Document number must end with digits")
                
                # Format with proper padding
                doc_num = f"{doc_type}{num_part.zfill(6)}"
            
            # Check for duplicates only for new documents or changed numbers
            if not self.instance or self.instance.document_number != doc_num:
                if Document.objects.filter(document_number=doc_num).exists():
                    raise forms.ValidationError("This document number already exists")

            cleaned_data['document_number'] = doc_num

        return cleaned_data

class CylinderMovementForm(forms.ModelForm):
    class Meta:
        model = CylinderMovement
        fields = ['movement_type', 'quantity']